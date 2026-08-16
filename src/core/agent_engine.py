import os
import re
from typing import Optional
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_react_agent, AgentExecutor
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

# Import local tools
from .tools import get_tools, _get_vectorstore
from .llm_factory import (
    get_llm,
    registrar_falha,
    registrar_sucesso,
    resolve_provider,
    resolve_model,
)

# Load environment variables
load_dotenv()

# Carrega ferramentas
tools = get_tools()

# Sinal interno: contrato entre backend e frontend para pedir permissão de busca web
WEB_SIGNAL = "__SOLICITAR_BUSCA_WEB__"

# Prompt ReAct Customizado com Guardrails
# Nota: a verificação de "termo não encontrado" é feita em Python antes de invocar o LLM.
# Este prompt assume que o agente JÁ sabe que o termo foi encontrado nos documentos.
AGENT_SYSTEM_PROMPT = """Você é um Investigador Autônomo Sênior.

## REGRAS:
1. Use doc_retriever para buscar informações nos documentos.
2. Cite SEMPRE a fonte: **📚 Fonte(s):** [arquivo.pdf, Pág: X]
3. NÃO invente informações.
4. Se não encontrar nos docs, use web_search.
5. Assim que a Observation contiver a informação pedida, PARE de usar ferramentas
   e responda imediatamente com "Final Answer:".
6. "Action:" só pode conter um destes nomes: {tool_names}. NUNCA escreva
   "Action: None", "Action: nenhuma" nem deixe a ação vazia — se você não vai
   chamar uma ferramenta, a linha seguinte tem de ser "Final Answer:".
7. Nunca repita o mesmo Thought duas vezes seguidas. Se já tem a resposta,
   encerre com "Final Answer:".

## FORMATO EXATO (NÃO adicione nada além):

Thought: [raciocínio]
Action: doc_retriever
Action Input: [busca]
Observation: [resultado]

Thought: [raciocínio]
Action: web_search
Action Input: [busca]
Observation: [resultado]

Thought: Eu sei a resposta
Final Answer: [resposta com fontes]

IMPORTANTE: no passo final NÃO existe linha "Action:". Vá direto de "Thought:"
para "Final Answer:" na mesma resposta.

Ferramentas: {tool_names}
{tools}

Pergunta: {input}
Scratchpad: {agent_scratchpad}
"""

class AgenticEngine:
    """
    Motor ReAct do investigador autônomo.

    Instância única *por combinação provider+modelo*: montar o agente é caro
    (prompt, tools, executor), então cada motor é reaproveitado. Trocar de
    provider cria um motor novo em vez de reconfigurar o existente, e o motor
    anterior continua válido — o histórico de sessão vive no Redis, fora daqui.
    """
    # Cache de instâncias: {(provider, model): AgenticEngine}
    _instances: dict = {}

    # Mantido para compatibilidade com testes/código que zeram o singleton.
    _instance = None

    def __new__(cls, provider: Optional[str] = None, model: Optional[str] = None):
        chave = (resolve_provider(provider), resolve_model(resolve_provider(provider), model))

        # Reset externo (`AgenticEngine._instance = None`) limpa o cache todo,
        # preservando o contrato antigo usado pelos testes.
        if cls._instance is None:
            cls._instances = {}

        if chave not in cls._instances:
            instancia = super(AgenticEngine, cls).__new__(cls)
            instancia._initialized = False
            cls._instances[chave] = instancia
            cls._instance = instancia

        return cls._instances[chave]

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        if self._initialized:
            return

        self.provider = resolve_provider(provider)
        self.model_name = resolve_model(self.provider, model)

        print(f"[AGENT] 🚀 Inicializando AgenticEngine (ReAct) — {self.provider}/{self.model_name}...")

        self.llm = get_llm(self.provider, self.model_name, temperature=0)

        prompt = ChatPromptTemplate.from_template(AGENT_SYSTEM_PROMPT)
        
        # Cria o agente ReAct
        agent = create_react_agent(self.llm, tools, prompt)
        
        self.tools = tools
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5,
            return_intermediate_steps=True
        )
        
        self._initialized = True
        print(f"[AGENT] ✅ AgenticEngine ReAct pronto! ({self.provider}/{self.model_name})")

    def _check_term_in_docs(self, query: str) -> tuple[bool, str]:
        """
        Guardrail em Python: verifica se algum token significativo da query
        aparece literalmente nos documentos recuperados pelo vector store.
        Retorna (encontrado: bool, trechos: str)
        """
        try:
            vs = _get_vectorstore()
            if vs._collection.count() == 0:
                print("[GUARDRAIL] Base vazia.")
                return False, ""
            
            retriever = vs.as_retriever(search_type="mmr", search_kwargs={"k": 4, "fetch_k": 8})
            docs = retriever.invoke(query)
            
            if not docs:
                return False, ""
            
            # Extrai tokens significativos da query (remove stopwords PT)
            stopwords = {"o", "a", "os", "as", "um", "uma", "de", "do", "da", "dos",
                         "das", "em", "no", "na", "nos", "nas", "que", "é", "para",
                         "com", "por", "como", "qual", "quais", "me", "se", "que", "o", "é"}
            tokens = [
                t.lower() for t in re.findall(r'\w+', query)
                if t.lower() not in stopwords and len(t) > 2
            ]
            
            combined_text = " ".join(doc.page_content for doc in docs).lower()
            
            # Verifica se pelo menos um token significativo aparece nos trechos
            found = any(token in combined_text for token in tokens)
            return found, combined_text
        except Exception as e:
            print(f"[GUARDRAIL] Erro na verificação: {e}")
            return True, ""  # Em caso de erro, deixa o agente tentar

    def investigate(self, question: str, session_id: str):
        """Executa a investigação com memória persistente via Redis."""
        print(f"\n[AGENT] 🔍 Investigando ReAct: '{question}' (sessão: {session_id})")
        
        # ── GUARDRAIL PYTHON (pré-LLM) ────────────────────────────────────────
        # Se a pergunta for sobre busca na web (usuário deu permissão),
        # pula o guardrail e deixa o agente correr normalmente
        permission_phrases = ["sim", "pode pesquisar", "sim, por favor", "pesquise", "pode", "ok"]
        is_web_permission = any(p in question.lower() for p in permission_phrases)
        
        if not is_web_permission:
            found, _ = self._check_term_in_docs(question)
            if not found:
                term = question.strip()
                print(f"[GUARDRAIL] 🛑 Termo não encontrado nos docs. Bloqueando alucinação.")
                return {
                    "answer": f"Não encontrei informações sobre **'{term}'** na base de documentos internos. {WEB_SIGNAL}",
                    "reasoning_steps": [],
                    "tools_used": ["doc_retriever"],
                    "session_id": session_id,
                    "provider": self.provider,
                    "model": self.model_name
                }
        # ── FIM DO GUARDRAIL ───────────────────────────────────────────────────

        # Configura a chain com histórico
        chain_with_history = RunnableWithMessageHistory(
            self.agent_executor,
            lambda sid: RedisChatMessageHistory(session_id=sid, url=os.getenv("REDIS_URL", "redis://localhost:6380")),
            input_messages_key="input",
            history_messages_key="chat_history", 
        )

        try:
            full_response = chain_with_history.invoke(
                {"input": question},
                config={"configurable": {"session_id": session_id}}
            )
            registrar_sucesso(self.provider)

            # Formata a resposta para o schema da API
            answer = full_response.get("output", "Sem resposta.")
            
            # Limpa resposta crua
            import re
            # Remove [Trecho N]...
            answer = re.sub(r'\[Trecho \d+\].*?(?=\[Trecho|\Z)', '', answer, flags=re.DOTALL)
            # Remove múltiplos espaços
            answer = re.sub(r'\s+', ' ', answer).strip()
            # Adiciona alerta se resposta veio de busca externa ou documento
            if 'websearch' in answer.lower() or 'snippet:' in answer.lower():
                answer = "[BUSCA EXTERNA]\n" + answer
            elif 'trecho' in answer.lower() or 'fonte:' in answer.lower():
                answer = "[BUSCA EM DOCUMENTO - não é resposta final]\n" + answer
            
            steps = []
            
            for action, observation in full_response.get("intermediate_steps", []):
                steps.append({
                    "thought": getattr(action, "log", ""),
                    "action": getattr(action, "tool", "Unknown"),
                    "action_input": str(getattr(action, "tool_input", "")),
                    "observation": str(observation)
                })
                
            # '_Exception' não é ferramenta: é como o LangChain registra um erro
            # de parsing do formato ReAct. Não deve aparecer como tool usada.
            return {
                "answer": answer,
                "reasoning_steps": steps,
                "tools_used": sorted({s["action"] for s in steps if s["action"] != "_Exception"}),
                "session_id": session_id,
                "provider": self.provider,
                "model": self.model_name
            }

        except Exception as e:
            # Alimenta o diagnóstico: a interface deixa de anunciar como
            # utilizável um provider que está recusando de fato.
            registrar_falha(self.provider, e)
            print(f"[AGENT] ❌ Erro na investigação: {e}")
            return {
                "answer": f"Erro durante a investigação (ReAct): {e}",
                "reasoning_steps": [],
                "tools_used": [],
                "session_id": session_id,
                "provider": self.provider,
                "model": self.model_name
            }

def get_engine(provider: Optional[str] = None, model: Optional[str] = None):
    """
    Devolve o motor da combinação provider+modelo pedida.
    Sem argumentos, usa LLM_PROVIDER do .env (padrão: ollama).
    """
    return AgenticEngine(provider=provider, model=model)
