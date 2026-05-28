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

API_URL = "http://localhost:8002"

# Inicialização de estado
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar
with st.sidebar:
    st.title("🕵️ Investigador")
    st.subheader("Configurações")
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
    st.markdown("- 🌐 **web_search**: Busca externa (Tavily)")

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
        with st.status("🕵️ Investigando...", expanded=True) as status:
            try:
                response = requests.post(
                    f"{API_URL}/investigate",
                    json={
                        "question": prompt,
                        "session_id": st.session_state.session_id
                    },
                    timeout=60
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Exibe os passos de raciocínio
                    for step in data.get("reasoning_steps", []):
                        st.write(f"⚙️ Usando: **{step['action']}**")
                        with st.expander("Ver detalhes do raciocínio"):
                            st.markdown(f"**Thought:** {step.get('thought', 'Processando...')}")
                            st.markdown(f"**Input:** `{step['action_input']}`")
                            st.markdown(f"<div class='observation-box'>{step['observation']}</div>", unsafe_allow_html=True)
                    
                    status.update(label="✅ Investigação concluída!", state="complete", expanded=False)
                    
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
                    
                    # Salva no histórico
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": clean_answer,
                        "steps": data.get("reasoning_steps", []),
                        "needs_web": needs_web
                    })
                    
                else:
                    st.error(f"Erro na API: {response.status_code}")
                    status.update(label="❌ Erro na investigação", state="error")
            
            except Exception as e:
                st.error(f"Erro ao conectar na API: {e}")
                status.update(label="❌ Erro de Conexão", state="error")

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
                        "session_id": st.session_state.session_id
                    },
                    timeout=60
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

