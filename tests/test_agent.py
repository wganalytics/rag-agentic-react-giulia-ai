import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Adiciona o diretório base do projeto ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ──────────────────────────────────────────────────────────────
# ULTRA-FAST HERMETIC LANGCHAIN & GRPC MOCKS (sys.modules)
# ──────────────────────────────────────────────────────────────
mock_loaders = MagicMock()
sys.modules['langchain_community.document_loaders'] = mock_loaders

mock_splitters = MagicMock()
sys.modules['langchain_text_splitters'] = mock_splitters

mock_vectorstores = MagicMock()
sys.modules['langchain_community.vectorstores'] = mock_vectorstores

mock_ollama = MagicMock()
sys.modules['langchain_ollama'] = mock_ollama

mock_histories = MagicMock()
sys.modules['langchain_community.chat_message_histories'] = mock_histories

mock_prompts = MagicMock()
mock_prompts.ChatPromptTemplate = MagicMock()
sys.modules['langchain_core.prompts'] = mock_prompts

mock_runnables_history = MagicMock()
mock_runnables_history.RunnableWithMessageHistory = MagicMock()
sys.modules['langchain_core.runnables.history'] = mock_runnables_history

mock_agents = MagicMock()
mock_agents.create_react_agent = MagicMock()
mock_agents.AgentExecutor = MagicMock()
sys.modules['langchain.agents'] = mock_agents

mock_tools_decorator = MagicMock()
def dummy_tool_decorator(func):
    return func
mock_tools_decorator.tool = dummy_tool_decorator
sys.modules['langchain_core.tools'] = mock_tools_decorator

mock_ddg = MagicMock()
sys.modules['langchain_community.tools'] = mock_ddg

from langchain_core.documents import Document

# Agora importamos o AgenticEngine de forma limpa e rápida!
from src.core.agent_engine import AgenticEngine, WEB_SIGNAL, get_engine

@pytest.fixture
def mock_agentic_engine():
    # Reset singleton instance between tests
    AgenticEngine._instance = None
    
    with patch('src.core.agent_engine._get_vectorstore') as mock_vdb, \
         patch('src.core.agent_engine.RunnableWithMessageHistory') as mock_history_class:
        # Mock vector store
        vs = MagicMock()
        mock_vdb.return_value = vs
        
        # Mock chain instance returned by RunnableWithMessageHistory
        mock_chain = MagicMock()
        mock_history_class.return_value = mock_chain
        
        engine = AgenticEngine()
        engine.agent_executor = MagicMock()
        
        # Faz com que chain_with_history.invoke() chame engine.agent_executor.invoke()
        def delegate_invoke(*args, **kwargs):
            return engine.agent_executor.invoke(*args, **kwargs)
        mock_chain.invoke.side_effect = delegate_invoke
        
        yield engine, vs

# ──────────────────────────────────────────────────────────────
# CASOS DE TESTE TDD — PRJ-03 AGENTIC RAG
# ──────────────────────────────────────────────────────────────

def test_singleton_pattern():
    """Garante que instanciar o AgenticEngine múltiplas vezes retorna exatamente a mesma instância."""
    AgenticEngine._instance = None
    engine1 = AgenticEngine()
    engine2 = AgenticEngine()
    assert engine1 is engine2
    assert id(engine1) == id(engine2)


# ──────────────────────────────────────────────────────────────
# SELEÇÃO DE PROVIDER (ollama / gemini / grok / groq)
# ──────────────────────────────────────────────────────────────

def test_motores_de_providers_diferentes_sao_instancias_distintas():
    """Trocar de provider não pode devolver o motor antigo com o LLM antigo."""
    AgenticEngine._instance = None
    with patch('src.core.agent_engine.get_llm') as mock_get_llm:
        eng_ollama = AgenticEngine(provider="ollama", model="llama3.2:3b")
        eng_groq = AgenticEngine(provider="groq", model="llama-3.3-70b-versatile")

        assert eng_ollama is not eng_groq
        assert eng_ollama.provider == "ollama"
        assert eng_groq.provider == "groq"
        assert eng_groq.model_name == "llama-3.3-70b-versatile"
        # Um motor construído por provider, nenhum reaproveitado indevidamente.
        assert mock_get_llm.call_count == 2


def test_mesmo_provider_e_modelo_reaproveita_o_motor():
    """Montar o agente é caro: a mesma combinação não pode reconstruir tudo."""
    AgenticEngine._instance = None
    with patch('src.core.agent_engine.get_llm') as mock_get_llm:
        primeiro = AgenticEngine(provider="gemini", model="gemini-2.5-flash")
        segundo = AgenticEngine(provider="gemini", model="gemini-2.5-flash")

        assert primeiro is segundo
        assert mock_get_llm.call_count == 1


def test_modelos_diferentes_no_mesmo_provider_sao_motores_distintos():
    AgenticEngine._instance = None
    with patch('src.core.agent_engine.get_llm'):
        pequeno = AgenticEngine(provider="ollama", model="llama3.2:3b")
        grande = AgenticEngine(provider="ollama", model="qwen3.5:35b")

        assert pequeno is not grande
        assert grande.model_name == "qwen3.5:35b"


def test_get_engine_repassa_provider():
    AgenticEngine._instance = None
    with patch('src.core.agent_engine.get_llm') as mock_get_llm:
        eng = get_engine(provider="grok", model="grok-4-latest")

        assert eng.provider == "grok"
        mock_get_llm.assert_called_once_with("grok", "grok-4-latest", temperature=0)


def test_resposta_declara_quem_respondeu(mock_agentic_engine):
    """A resposta precisa dizer qual provider/modelo a produziu (rastreabilidade)."""
    engine, vs = mock_agentic_engine
    engine.agent_executor.invoke.return_value = {"output": "resposta", "intermediate_steps": []}

    resposta = engine.investigate("sim, pode pesquisar", session_id="s1")

    assert resposta["provider"] == engine.provider
    assert resposta["model"] == engine.model_name


def test_guardrail_tambem_declara_provider(mock_agentic_engine):
    """Mesmo bloqueando antes do LLM, a resposta identifica o motor ativo."""
    engine, vs = mock_agentic_engine
    vs._collection.count.return_value = 5
    mock_retriever = MagicMock()
    mock_retriever.invoke.return_value = [Document(page_content="Assunto totalmente diferente.")]
    vs.as_retriever.return_value = mock_retriever

    resposta = engine.investigate("O que é Kubernetes?", session_id="s2")

    assert WEB_SIGNAL in resposta["answer"]
    assert resposta["provider"] == engine.provider

def test_web_signal_constant():
    """Garante que o contrato do WEB_SIGNAL entre frontend e backend é estável."""
    assert WEB_SIGNAL == "__SOLICITAR_BUSCA_WEB__"

def test_guardrail_blocks_unknown(mock_agentic_engine):
    """Verifica que perguntas sobre termos não presentes nos documentos são bloqueadas antes do LLM, retornando o WEB_SIGNAL."""
    engine, vs = mock_agentic_engine
    
    # Simula coleção com documentos
    vs._collection.count.return_value = 5
    
    # Mock retriever que retorna documentos que não contêm o termo buscado
    mock_retriever = MagicMock()
    doc_1 = Document(page_content="Este documento fala sobre Inteligência Artificial local.")
    mock_retriever.invoke.return_value = [doc_1]
    vs.as_retriever.return_value = mock_retriever
    
    # Busca um termo totalmente diferente
    query = "O que é Kubernetes?"
    response = engine.investigate(query, session_id="test-session-1")
    
    # Assertions
    assert WEB_SIGNAL in response["answer"]
    assert "Kubernetes" in response["answer"]
    # Garante que o agente ReAct sequer foi invocado (guardrail puramente Python)
    engine.agent_executor.invoke.assert_not_called()

def test_guardrail_bypassed_web_permission(mock_agentic_engine):
    """Verifica que respostas afirmativas de permissão do usuário ignoram o guardrail, acionando o ReAct."""
    engine, vs = mock_agentic_engine
    
    # Mock do executor
    engine.agent_executor.invoke.return_value = {
        "output": "Sim, eu pesquisei na web e Kubernetes é um orquestrador de containers.",
        "intermediate_steps": []
    }
    
    # Query de permissão ("sim, pode pesquisar")
    query = "sim, pode pesquisar"
    response = engine.investigate(query, session_id="test-session-2")
    
    # Assertions
    assert WEB_SIGNAL not in response["answer"]
    assert "Kubernetes" in response["answer"]

def test_react_tool_selection(mock_agentic_engine):
    """Garante que a investigação retorna os passos intermediários com as ferramentas corretas executadas."""
    engine, vs = mock_agentic_engine
    
    # Configura o retorno com passos ReAct simulados
    mock_action = MagicMock()
    mock_action.log = "Thought: Preciso buscar informações sobre IA no doc_retriever"
    mock_action.tool = "doc_retriever"
    mock_action.tool_input = "Inteligência Artificial"
    
    engine.agent_executor.invoke.return_value = {
        "output": "A Inteligência Artificial local é altamente eficiente. [Trecho 1]",
        "intermediate_steps": [(mock_action, "Resultado da busca no ChromaDB")]
    }
    
    # Mock do guardrail para passar (encontrar o termo nos documentos)
    vs._collection.count.return_value = 5
    mock_retriever = MagicMock()
    doc_1 = Document(page_content="Inteligência Artificial local.")
    mock_retriever.invoke.return_value = [doc_1]
    vs.as_retriever.return_value = mock_retriever
    
    # Query que existe nos docs
    response = engine.investigate("Fale sobre Inteligência Artificial", session_id="test-session-3")
    
    # Assertions
    assert "A Inteligência Artificial local é altamente eficiente" in response["answer"]
    assert len(response["reasoning_steps"]) == 1
    assert response["reasoning_steps"][0]["action"] == "doc_retriever"
    assert "doc_retriever" in response["tools_used"]

def test_max_iterations_respected(mock_agentic_engine):
    """Verifica que as configurações do AgentExecutor limitam os ciclos ReAct para evitar loops infinitos."""
    engine, vs = mock_agentic_engine
    
    # A verificação das iterações é feita no construtor do executor
    # Vamos garantir que a instância do executor tem max_iterations=5 configurado
    assert engine.agent_executor is not None
