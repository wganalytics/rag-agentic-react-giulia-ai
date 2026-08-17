import os
import streamlit as st
import requests
import time
import uuid

# Configuração da página
st.set_page_config(
    page_title="Investigador Autônomo (Agentic RAG)",
    page_icon="🔍",
    layout="wide"
)

# Estilização Glassmorphism
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #f8fafc;
    }
    
    .thought-pill {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 15px;
        margin: 10px 0;
        backdrop-filter: blur(10px);
        border-left: 4px solid #3b82f6;
    }
    
    .action-badge {
        background: #3b82f6;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8em;
        font-weight: bold;
        text-transform: uppercase;
    }
    
    .observation-box {
        background: rgba(0, 0, 0, 0.2);
        border-radius: 8px;
        padding: 10px;
        font-family: monospace;
        font-size: 0.9em;
        margin-top: 10px;
        color: #94a3b8;
        max-height: 200px;
        overflow-y: auto;
    }
    
    .final-answer {
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.2);
        border-radius: 12px;
        padding: 20px;
        margin-top: 20px;
        border-left: 6px solid #10b981;
    }
    
    .not-found-warning {
        background: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.3);
        border-radius: 12px;
        padding: 16px 20px;
        margin-top: 10px;
        border-left: 6px solid #f59e0b;
        color: #fbbf24;
        font-size: 1em;
    }
    
    .web-permission-box {
        background: rgba(59, 130, 246, 0.08);
        border: 1px solid rgba(59, 130, 246, 0.25);
        border-radius: 12px;
        padding: 16px 20px;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Em container a API vive noutro host: o padrao preserva o uso local.
API_URL = os.getenv("API_URL", "http://localhost:8002")

# Inicialização de estado
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar
with st.sidebar:
    st.title("🕵️ Investigador")
    st.subheader("Configurações")

    # ── Seleção do LLM de raciocínio ──────────────────────────────
    # A lista vem da API (/providers), que sabe quais estão prontos.
    SUGESTOES = {
        "sem_credito": "Adicione crédito no painel do provider — a chave está correta.",
        "chave_invalida": "Gere uma nova chave e atualize o .env.",
        "limite_taxa": "Aguarde um pouco antes de tentar de novo.",
        "modelo_inexistente": "Confira o nome do modelo no .env.",
    }

    def icone_de(p):
        """✅ respondeu · ⚙️ configurado mas não testado · ⛔ falhou ou incompleto."""
        if not p["available"]:
            return "⛔"
        if p.get("verified") is True:
            return "✅"
        if p.get("verified") is False:
            return "⛔"
        return "⚙️"

    @st.cache_resource(show_spinner="Testando os motores de LLM...")
    def motores_testados():
        """
        Pede à API um teste real de cada motor, uma vez por processo.

        Feito no carregamento para que o seletor já ofereça só o que funciona —
        exigir um clique antes significaria oferecer motores quebrados na
        primeira tela, que é justamente o que se quer evitar.
        """
        try:
            r = requests.get(f"{API_URL}/providers", params={"probe": "true"}, timeout=180)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None

    info_providers = motores_testados()

    if info_providers:
        todos = info_providers["providers"]
        rotulos = {p["provider"]: p["label"] for p in todos}
        por_nome = {p["provider"]: p for p in todos}
        funcionais = [p["provider"] for p in todos if p.get("verified") is True]
        quebrados = [p["provider"] for p in todos if p.get("verified") is not True]

        mostrar_todos = st.checkbox(
            "Mostrar motores indisponíveis",
            value=not funcionais,
            help="Por padrão o seletor lista apenas os motores que responderam ao teste.",
        )
        ofertados = list(rotulos.keys()) if mostrar_todos else funcionais

        if not ofertados:
            st.error("Nenhum motor de LLM está funcionando.")
            for p in todos:
                st.write(f"{icone_de(p)} **{p['provider']}** — {p['reason']}")
                if p.get("categoria") in SUGESTOES:
                    st.caption(SUGESTOES[p["categoria"]])
            st.stop()

        padrao = info_providers.get("default", ofertados[0])
        escolhido = st.selectbox(
            "🧠 Motor de LLM",
            options=ofertados,
            index=ofertados.index(padrao) if padrao in ofertados else 0,
            format_func=lambda p: rotulos[p],
            help="Ollama roda local, sem custo. Gemini, Grok e Groq são APIs externas.",
        )
        st.session_state.provider = escolhido

        status_escolhido = por_nome[escolhido]

        # No Ollama a máquina sabe quais modelos existem: oferecer a lista
        # evita errar o nome e só descobrir na primeira pergunta.
        locais = info_providers.get("ollama_models", []) if escolhido == "ollama" else []
        padrao_modelo = status_escolhido["model"]
        if locais:
            if padrao_modelo not in locais:
                locais = [padrao_modelo] + locais
            modelo = st.selectbox(
                "Modelo",
                options=locais,
                index=locais.index(padrao_modelo),
                help="Modelos instalados no Ollama desta máquina.",
            )
        else:
            modelo = st.text_input("Modelo", value=padrao_modelo)
        st.session_state.modelo = modelo

        if status_escolhido.get("verified") is True:
            st.success("Respondeu ao teste")
        elif not status_escolhido["available"]:
            st.error(f"Indisponível: {status_escolhido['reason']}")
        else:
            st.error(status_escolhido["reason"])
            if status_escolhido.get("categoria") in SUGESTOES:
                st.caption(SUGESTOES[status_escolhido["categoria"]])

        if quebrados:
            st.caption(f"Fora do seletor: {', '.join(quebrados)}")

        if st.button("🔄 Testar motores de novo", use_container_width=True):
            motores_testados.clear()
            st.rerun()

        with st.expander("Status de todos os motores"):
            for p in todos:
                st.write(f"{icone_de(p)} **{p['provider']}** — `{p['model']}` — {p['reason']}")
                if p.get("detail"):
                    st.caption(p["detail"][:180])
                if p.get("categoria") in SUGESTOES:
                    st.caption(SUGESTOES[p["categoria"]])
    else:
        st.session_state.provider = None
        st.warning("API offline: não foi possível listar os motores de LLM.")

    st.caption("Embeddings permanecem locais (Ollama) em qualquer provider.")
    st.divider()

    st.info(f"Sessão ID: `{st.session_state.session_id}`")
    
    if st.button("Limpar Histórico de Chat"):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

    st.divider()
    st.markdown("### 📄 Alimentar Base")
    uploaded_file = st.file_uploader("Novo PDF", type=["pdf"], label_visibility="collapsed")
    if uploaded_file:
        if st.button("🚀 Processar PDF", use_container_width=True):
            with st.spinner("Vetorizando..."):
                try:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    response = requests.post(f"{API_URL}/upload_pdf", files=files)
                    if response.status_code == 200:
                        st.toast("✅ Documento processado!", icon="🧠")
                        st.rerun()
                    else:
                        st.error("Erro no processamento.")
                except Exception as e:
                    st.error(f"Offline: {e}")

    st.divider()
    st.markdown("### 📚 Documentos na Base")
    try:
        l_resp = requests.get(f"{API_URL}/list_docs")
        if l_resp.status_code == 200:
            docs = l_resp.json().get("documents", [])
            if docs:
                for doc in docs:
                    c1, c2 = st.columns([0.8, 0.2])
                    c1.caption(f"📄 {doc}")
                    if c2.button("🗑️", key=f"del_{doc}"):
                        try:
                            d_resp = requests.delete(f"{API_URL}/remove_doc?filename={doc}")
                            if d_resp.status_code == 200:
                                st.toast(f"Removido: {doc}")
                                st.rerun()
                        except: st.error("Erro")
            else:
                st.info("Base vazia.")
    except:
        st.error("Erro ao listar docs.")

    st.divider()
    st.markdown("### 🛠️ Ferramentas Ativas")
    st.markdown("- 📚 **doc_retriever**: Busca no VectorDB")
    st.markdown("- 🧮 **math_tool**: Calculadora NumExpr")
    st.markdown("- 🌐 **web_search**: Busca externa (DuckDuckGo)")

# Área Principal
st.title("🔍 Investigador Autônomo")
st.caption("Agentic RAG com Loop ReAct e Memória Redis")

# Chat Container
chat_container = st.container()

with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if "steps" in message:
                for step in message["steps"]:
                    with st.expander(f"💭 Pensamento: {step['action']}", expanded=False):
                        st.markdown(f"<span class='action-badge'>{step['action']}</span>", unsafe_allow_html=True)
                        st.markdown(f"**Input:** `{step['action_input']}`")
                        st.markdown("**Observação:**")
                        st.markdown(f"<div class='observation-box'>{step['observation']}</div>", unsafe_allow_html=True)
            
            st.markdown(message["content"])

# Input do Usuário
if prompt := st.chat_input("O que deseja investigar hoje?"):
    st.session_state.last_question = prompt # Salva a pergunta original
    # Adiciona mensagem do usuário
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Processamento do Agente
    with st.chat_message("assistant"):
        data = None  # preenchido dentro do status, consumido fora dele
        with st.status("🕵️ Investigando...", expanded=True) as status:
            try:
                response = requests.post(
                    f"{API_URL}/investigate",
                    json={
                        "question": prompt,
                        "session_id": st.session_state.session_id,
                        "provider": st.session_state.get("provider"),
                        "model": st.session_state.get("modelo")
                    },
                    timeout=120
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Exibe os passos de raciocínio.
                    # Sem st.expander aqui: já estamos dentro de st.status, e o
                    # Streamlit proíbe expander aninhado em expander.
                    for step in data.get("reasoning_steps", []):
                        st.write(f"⚙️ Usando: **{step['action']}**")
                        with st.container(border=True):
                            st.markdown(f"**Thought:** {step.get('thought', 'Processando...')}")
                            st.markdown(f"**Input:** `{step['action_input']}`")
                            st.markdown(f"<div class='observation-box'>{step['observation']}</div>", unsafe_allow_html=True)
                    
                    status.update(label="✅ Investigação concluída!", state="complete", expanded=False)

                else:
                    st.error(f"Erro na API: {response.status_code} — {response.text[:300]}")
                    status.update(label="❌ Erro na investigação", state="error")

            except Exception as e:
                st.error(f"Falha ao processar a investigação: {e}")
                status.update(label="❌ Erro", state="error")

        # A resposta é renderizada FORA do st.status: o status acabou de ser
        # recolhido (expanded=False) e qualquer coisa escrita dentro dele
        # ficaria invisível para o usuário.
        if data:
            # --- GUARDRAIL: detecta sinal de busca web ---
            WEB_SIGNAL = "__SOLICITAR_BUSCA_WEB__"
            needs_web = WEB_SIGNAL in data["answer"]

            # Remove o token interno antes de exibir ao usuário
            clean_answer = data["answer"].replace(WEB_SIGNAL, "").strip()

            if needs_web:
                # Exibe mensagem limpa sem o token técnico
                st.markdown(f"""
<div class='not-found-warning'>
🔍 {clean_answer}
</div>
""", unsafe_allow_html=True)
                st.session_state.pending_web_permission = True
                st.session_state.last_question = st.session_state.get("last_question", prompt)
            else:
                # Exibe resposta normal
                st.markdown(clean_answer)

            # Rodapé de rastreabilidade: qual motor produziu esta resposta
            if data.get("provider"):
                st.caption(f"🧠 {data['provider']} · `{data.get('model', '')}`")

            # Salva no histórico
            st.session_state.messages.append({
                "role": "assistant",
                "content": clean_answer,
                "steps": data.get("reasoning_steps", []),
                "needs_web": needs_web
            })

# --- Painel de Permissão de Busca Web ---
if st.session_state.get("pending_web_permission", False):
    st.markdown("""
    <div class='web-permission-box'>
        <strong>🌐 Consultar a internet?</strong><br/>
        Não encontrei isso na base interna. Deseja que eu faça uma busca na web?
    </div>
    """, unsafe_allow_html=True)
    
    c1, c2, _ = st.columns([0.18, 0.22, 0.6])
    
    if c1.button("✅ Sim, pesquise", use_container_width=True, type="primary"):
        st.session_state.pending_web_permission = False
        original = st.session_state.get("last_question", "o assunto anterior")
        st.session_state.automated_prompt = f"Sim, por favor realize a pesquisa na internet especificamente sobre: {original}"
        st.rerun()

    if c2.button("❌ Não, apenas encerre", use_container_width=True):
        st.session_state.pending_web_permission = False
        st.session_state.messages.append({
            "role": "assistant",
            "content": "Tudo bem! Investigação encerrada com base apenas nos documentos internos.",
            "steps": []
        })
        st.rerun()

# Fluxo automatizado (após clicar em Sim)
if "automated_prompt" in st.session_state and st.session_state.automated_prompt:
    p = st.session_state.automated_prompt
    st.session_state.automated_prompt = None # Limpa para não entrar em loop
    
    # Adiciona mensagem do usuário e processa
    st.session_state.messages.append({"role": "user", "content": p})
    # O Streamlit vai reler o script e, como agora há uma nova mensagem no histórico, 
    # precisamos forçar a chamada da API. 
    # Melhor forma no Streamlit para evitar duplicação é envolver o processamento em função, 
    # mas aqui para simplicidade, vamos usar o chat_input natural se possível.
    # Na verdade, o st.rerun() fará o script rodar do topo.
    # Se injetarmos no final do histórico, podemos rodar o bloco de requisição.
    
    with st.chat_message("assistant"):
        with st.status("🌐 Realizando busca externa...", expanded=True) as status:
            try:
                response = requests.post(
                    f"{API_URL}/investigate",
                    json={
                        "question": p,
                        "session_id": st.session_state.session_id,
                        "provider": st.session_state.get("provider"),
                        "model": st.session_state.get("modelo")
                    },
                    timeout=120
                )
                if response.status_code == 200:
                    data = response.json()
                    st.markdown(data["answer"])
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": data["answer"],
                        "steps": data.get("reasoning_steps", [])
                    })
                    status.update(label="✅ Busca concluída!", state="complete", expanded=False)
                else:
                    st.error("Erro na busca.")
            except Exception as e:
                st.error(f"Erro: {e}")
    st.rerun()

