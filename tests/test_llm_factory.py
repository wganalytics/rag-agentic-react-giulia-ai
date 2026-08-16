import pytest
from unittest.mock import MagicMock, patch

from src.core import llm_factory
from src.core.llm_factory import (
    GEMINI,
    GROK,
    GROQ,
    OLLAMA,
    LLMConfigError,
    describe_provider,
    get_llm,
    list_provider_status,
    resolve_model,
    resolve_provider,
)


# ---------------------------------------------------------------------------
# Resolução de provider
# ---------------------------------------------------------------------------

def test_provider_padrao_e_ollama(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert resolve_provider() == OLLAMA


def test_provider_vem_do_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert resolve_provider() == GEMINI


def test_argumento_explicito_vence_o_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert resolve_provider("grok") == GROK


def test_provider_e_normalizado(monkeypatch):
    assert resolve_provider("  GEMINI ") == GEMINI


def test_provider_desconhecido_falha():
    with pytest.raises(LLMConfigError, match="desconhecido"):
        resolve_provider("chatgpt-do-zap")


# ---------------------------------------------------------------------------
# Resolução de modelo
# ---------------------------------------------------------------------------

def test_modelo_explicito_vence(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL_NAME", "do-env")
    assert resolve_model(GEMINI, "explicito") == "explicito"


def test_modelo_cai_no_padrao_quando_env_vazio(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL_NAME", raising=False)
    assert resolve_model(GEMINI, None) == llm_factory.DEFAULT_MODELS[GEMINI]


def test_ollama_mantem_retrocompatibilidade_com_model_name(monkeypatch):
    """O .env antigo do projeto usa MODEL_NAME — não pode quebrar."""
    monkeypatch.delenv("OLLAMA_MODEL_NAME", raising=False)
    monkeypatch.setenv("MODEL_NAME", "llama3.2:3b")
    assert resolve_model(OLLAMA, None) == "llama3.2:3b"


def test_ollama_model_name_tem_precedencia_sobre_engine_model_name(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL_NAME", "novo")
    monkeypatch.setenv("MODEL_NAME", "antigo")
    assert resolve_model(OLLAMA, None) == "novo"


# ---------------------------------------------------------------------------
# Construção dos clientes
# ---------------------------------------------------------------------------

def test_ollama_nao_exige_chave(monkeypatch):
    """Ollama é local: nenhuma chave no ambiente e ainda assim constrói o cliente."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_HOST", "http://meu-ollama:11434")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://meu-ollama:11434")
    fake_cls = MagicMock()

    with patch.dict("sys.modules", {"langchain_ollama": MagicMock(ChatOllama=fake_cls)}):
        get_llm(OLLAMA, "llama3.2:3b")

    fake_cls.assert_called_once_with(
        model="llama3.2:3b",
        base_url="http://meu-ollama:11434",
        temperature=0.0,
    )


def test_gemini_sem_chave_falha_com_mensagem_util(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(LLMConfigError, match="GEMINI_API_KEY"):
        get_llm(GEMINI, "gemini-2.5-flash")


def test_grok_sem_chave_falha_com_mensagem_util(monkeypatch):
    # SDK simulado: o teste é sobre a chave ausente, não sobre o pacote.
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    with patch.dict("sys.modules", {"langchain_xai": MagicMock(ChatXAI=MagicMock())}):
        with pytest.raises(LLMConfigError, match="XAI_API_KEY"):
            get_llm(GROK, "grok-4-latest")


def test_gemini_recebe_chave_e_modelo(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "chave-de-teste")
    fake_cls = MagicMock()
    fake_module = MagicMock(ChatGoogleGenerativeAI=fake_cls)

    with patch.dict("sys.modules", {"langchain_google_genai": fake_module}):
        get_llm(GEMINI, "gemini-2.5-pro", temperature=0.3)

    fake_cls.assert_called_once_with(
        model="gemini-2.5-pro",
        temperature=0.3,
        google_api_key="chave-de-teste",
    )


def test_grok_recebe_chave_e_modelo(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "chave-xai")
    fake_cls = MagicMock()
    fake_module = MagicMock(ChatXAI=fake_cls)

    with patch.dict("sys.modules", {"langchain_xai": fake_module}):
        get_llm(GROK, "grok-4-latest")

    fake_cls.assert_called_once_with(
        model="grok-4-latest",
        temperature=0.0,
        xai_api_key="chave-xai",
    )


def test_groq_sem_chave_falha_com_mensagem_util(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(LLMConfigError, match="GROQ_API_KEY"):
        get_llm(GROQ, "llama-3.3-70b-versatile")


def test_groq_recebe_chave_e_modelo(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "chave-groq")
    fake_cls = MagicMock()

    with patch.dict("sys.modules", {"langchain_groq": MagicMock(ChatGroq=fake_cls)}):
        get_llm(GROQ, "llama-3.3-70b-versatile")

    fake_cls.assert_called_once_with(
        model="llama-3.3-70b-versatile",
        temperature=0.0,
        api_key="chave-groq",
    )


# --- Grok (xAI) e Groq (Groq Cloud) são coisas diferentes -------------------

def test_grok_e_groq_nao_se_misturam(monkeypatch):
    """Uma letra separa os dois providers: nada pode vazar de um para o outro."""
    monkeypatch.setenv("XAI_API_KEY", "chave-do-xai")
    monkeypatch.setenv("GROQ_API_KEY", "chave-do-groq")
    monkeypatch.setenv("GROK_MODEL_NAME", "grok-4-latest")
    monkeypatch.setenv("GROQ_MODEL_NAME", "llama-3.3-70b-versatile")

    assert llm_factory.resolve_api_key(GROK) == "chave-do-xai"
    assert llm_factory.resolve_api_key(GROQ) == "chave-do-groq"
    assert resolve_model(GROK, None) == "grok-4-latest"
    assert resolve_model(GROQ, None) == "llama-3.3-70b-versatile"


def test_chave_do_groq_nao_habilita_o_grok(monkeypatch):
    """Ter GROQ_API_KEY não pode fazer o xAI Grok parecer configurado."""
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "chave-do-groq")

    assert llm_factory.resolve_api_key(GROK) is None
    assert describe_provider(GROK).available is False


def test_google_api_key_serve_como_alternativa(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "chave-alternativa")
    fake_cls = MagicMock()

    with patch.dict("sys.modules", {"langchain_google_genai": MagicMock(ChatGoogleGenerativeAI=fake_cls)}):
        get_llm(GEMINI, "gemini-2.5-flash")

    assert fake_cls.call_args.kwargs["google_api_key"] == "chave-alternativa"


# ---------------------------------------------------------------------------
# Diagnóstico
# ---------------------------------------------------------------------------

def test_diagnostico_aponta_chave_faltando(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    status = describe_provider(GEMINI)
    assert status.available is False
    assert "GEMINI_API_KEY" in status.reason


def test_diagnostico_cobre_todos_os_providers():
    status = list_provider_status()
    assert [s.provider for s in status] == list(llm_factory.PROVIDERS)
