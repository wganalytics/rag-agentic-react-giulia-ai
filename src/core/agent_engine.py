import os
import re
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_react_agent, AgentExecutor
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

# Import local tools
from .tools import get_tools, _get_vectorstore

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

Ferramentas: {tool_names}
{tools}

Pergunta: {input}
Scratchpad: {agent_scratchpad}
"""

class AgenticEngine:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(AgenticEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        print("[AGENT] 🚀 Inicializando AgenticEngine (Motor ReAct)...")
        
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        model_name = os.getenv("MODEL_NAME", "llama3.2:3b")
        
        self.llm = ChatOllama(
            model=model_name,
            temperature=0,
            base_url=ollama_host
        )

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
        print("[AGENT] ✅ AgenticEngine ReAct pronto!")

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
                    "session_id": session_id
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
                
            return {
                "answer": answer,
                "reasoning_steps": steps,
                "tools_used": list(set([s["action"] for s in steps])),
                "session_id": session_id
            }

        except Exception as e:
            print(f"[AGENT] ❌ Erro na investigação: {e}")
            return {
                "answer": f"Erro durante a investigação (ReAct): {e}",
                "reasoning_steps": [],
                "tools_used": [],
                "session_id": session_id
            }

def get_engine():
    return AgenticEngine()
