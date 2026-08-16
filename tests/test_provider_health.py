"""
Diagnóstico de saúde dos providers: distinguir 'configurado' de 'funcionando'.

Ter SDK e chave não garante resposta — a conta pode estar sem crédito. Estes
testes travam essa distinção e a classificação do motivo real da falha.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.core import llm_factory
from src.core.llm_factory import (
    CHAVE_INVALIDA,
    DESCONHECIDO,
    GEMINI,
    GROK,
    LIMITE_TAXA,
    MODELO_INEXISTENTE,
    OLLAMA,
    REDE,
    SEM_CREDITO,
    classificar_falha,
    describe_provider,
    probe_provider,
    registrar_falha,
    registrar_sucesso,
    ultima_falha,
)


@pytest.fixture(autouse=True)
def limpar_registro():
    """Cada teste começa sem falhas nem verificações herdadas."""
    llm_factory._ultima_falha.clear()
    llm_factory._verificados.clear()
    yield
    llm_factory._ultima_falha.clear()
    llm_factory._verificados.clear()


# ── Classificação da falha ────────────────────────────────────────────────

# O erro real devolvido pela xAI quando a conta não tem crédito.
ERRO_XAI_SEM_CREDITO = (
    "Error code: 403 - {'code': 'permission-denied', 'error': \"Your newly "
    "created team doesn't have any credits or licenses yet. You can purchase "
    "those on https://console.x.ai/team/...\"}"
)


def test_falta_de_credito_nao_e_confundida_com_chave_invalida():
    """
    O erro de crédito da xAI chega como 403 permission-denied — exatamente o
    formato de uma chave inválida. Classificar errado manda o usuário trocar
    uma chave que está correta.
    """
    assert classificar_falha(Exception(ERRO_XAI_SEM_CREDITO)) == SEM_CREDITO


@pytest.mark.parametrize("mensagem,esperado", [
    ("Error code: 429 - rate limit exceeded", LIMITE_TAXA),
    ("You exceeded your current quota, please check your billing", SEM_CREDITO),
    ("Error code: 401 - invalid api key provided", CHAVE_INVALIDA),
    ("Error code: 404 - model not found: gpt-9", MODELO_INEXISTENTE),
    ("Connection refused: failed to establish a new connection", REDE),
    ("Something entirely unexpected happened", DESCONHECIDO),
])
def test_categorias_de_falha(mensagem, esperado):
    assert classificar_falha(Exception(mensagem)) == esperado


def test_limite_de_taxa_tem_prioridade_sobre_403():
    """429 com texto de permissão não pode virar 'chave inválida'."""
    erro = Exception("Error code: 429 - too many requests, permission denied temporarily")
    assert classificar_falha(erro) == LIMITE_TAXA


def test_quota_do_gemini_e_limite_de_taxa_nao_falta_de_credito():
    """
    O Google devolve o limite por minuto do free tier como 429 falando em
    'quota' e 'billing'. Classificar como falta de crédito mandaria comprar
    crédito quando bastava esperar alguns segundos.
    """
    erro = Exception(
        "429 You exceeded your current quota, please check your plan and "
        "billing details. For more information on this error, head to: ..."
    )
    assert classificar_falha(erro) == LIMITE_TAXA


# ── Falha de infraestrutura não é culpa do provider ───────────────────────

class _ErroRedis(Exception):
    """Imita redis.exceptions.ConnectionError (o que importa é o módulo)."""
    __module__ = "redis.exceptions"


class _ErroChroma(Exception):
    __module__ = "chromadb.errors"


def test_redis_fora_do_ar_nao_e_atribuido_ao_provider():
    """
    Um Redis caído derrubava o status do provider e sugeria comprar crédito.
    O diagnóstico errado é pior que nenhum: manda caçar o problema no lugar errado.
    """
    erro = _ErroRedis("Error 61 connecting to localhost:6380. Connection refused.")

    assert llm_factory.falha_e_do_provider(erro) is False
    assert registrar_falha(GROK, erro) is None
    assert ultima_falha(GROK) is None


def test_erro_do_banco_vetorial_tambem_e_ignorado():
    assert registrar_falha(GEMINI, _ErroChroma("collection not found")) is None
    assert ultima_falha(GEMINI) is None


def test_erro_de_infra_embrulhado_pelo_langchain_e_ignorado():
    """O LangChain embrulha a exceção original: a causa é quem denuncia."""
    try:
        try:
            raise _ErroRedis("Connection refused")
        except _ErroRedis as origem:
            raise RuntimeError("Erro ao executar a chain") from origem
    except RuntimeError as embrulhado:
        assert llm_factory.falha_e_do_provider(embrulhado) is False
        assert registrar_falha(GROK, embrulhado) is None


def test_erro_do_sdk_do_provider_continua_sendo_registrado():
    """Regressão: o filtro não pode engolir a falha que realmente importa."""
    assert registrar_falha(GROK, Exception(ERRO_XAI_SEM_CREDITO)) == SEM_CREDITO
    assert ultima_falha(GROK)[0] == SEM_CREDITO


# ── Configurado != verificado ─────────────────────────────────────────────

def test_configurado_nao_e_anunciado_como_pronto(monkeypatch):
    """
    O ponto do exercício: com chave e SDK presentes mas nenhuma chamada feita,
    o status não pode afirmar que está pronto.
    """
    monkeypatch.setenv("XAI_API_KEY", "chave-qualquer")
    with patch.dict("sys.modules", {"langchain_xai": MagicMock()}):
        status = describe_provider(GROK)

    assert status.available is True          # configuração completa
    assert status.verified is None           # ninguém provou que responde
    assert "não verificado" in status.reason.lower()


def test_falha_real_derruba_o_status_para_nao_verificado(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "chave-qualquer")
    registrar_falha(GROK, Exception(ERRO_XAI_SEM_CREDITO))

    with patch.dict("sys.modules", {"langchain_xai": MagicMock()}):
        status = describe_provider(GROK)

    assert status.verified is False
    assert status.categoria == SEM_CREDITO
    assert "crédito" in status.reason.lower()
    # A configuração continua correta: o problema não é chave nem pacote.
    assert status.available is True


def test_sucesso_posterior_limpa_a_falha(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "chave-qualquer")
    registrar_falha(GROK, Exception(ERRO_XAI_SEM_CREDITO))
    assert ultima_falha(GROK) is not None

    registrar_sucesso(GROK)

    assert ultima_falha(GROK) is None
    with patch.dict("sys.modules", {"langchain_xai": MagicMock()}):
        assert describe_provider(GROK).verified is None


def test_chave_ausente_continua_indisponivel(monkeypatch):
    """Regressão: a novidade não pode mascarar o caso básico de falta de chave."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    status = describe_provider(GEMINI)

    assert status.available is False
    assert "GEMINI_API_KEY" in status.reason


# ── Probe ao vivo ─────────────────────────────────────────────────────────

def test_probe_marca_verificado_quando_responde(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "chave")
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="OK")

    with patch.dict("sys.modules", {"langchain_google_genai": MagicMock()}), \
         patch.object(llm_factory, "get_llm", return_value=llm):
        status = probe_provider(GEMINI)

    assert status.verified is True
    assert status.reason == "Verificado"
    assert llm.invoke.called


def test_probe_classifica_falta_de_credito(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "chave")
    llm = MagicMock()
    llm.invoke.side_effect = Exception(ERRO_XAI_SEM_CREDITO)

    with patch.dict("sys.modules", {"langchain_xai": MagicMock()}), \
         patch.object(llm_factory, "get_llm", return_value=llm):
        status = probe_provider(GROK)

    assert status.verified is False
    assert status.categoria == SEM_CREDITO
    assert status.available is True
    # A falha fica registrada para quem consultar o status depois.
    assert ultima_falha(GROK)[0] == SEM_CREDITO


def test_probe_nao_tenta_chamada_sem_configuracao(monkeypatch):
    """Sem chave não há o que testar: não gasta rede nem confunde o diagnóstico."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with patch.object(llm_factory, "get_llm") as construtor:
        status = probe_provider(GEMINI)

    assert status.available is False
    assert construtor.called is False


# ── Probe do Ollama: consulta o daemon, não gera texto ────────────────────

class _RespostaFake:
    """Imita o objeto de urlopen usado como context manager."""
    def __init__(self, payload):
        self._payload = payload.encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _com_daemon(payload):
    return patch("urllib.request.urlopen", return_value=_RespostaFake(payload))


def test_ollama_verificado_sem_carregar_o_modelo(monkeypatch):
    """
    Gerar texto obrigaria a carregar dezenas de GB só para abrir a tela.
    Consultar o daemon prova o necessário: está no ar e o modelo existe.
    """
    monkeypatch.setenv("MODEL_NAME", "qwen3.5:35b")
    payload = '{"models": [{"name": "qwen3.5:35b"}, {"name": "llama3.2:3b"}]}'

    with patch.dict("sys.modules", {"langchain_ollama": MagicMock()}), \
         _com_daemon(payload), \
         patch.object(llm_factory, "get_llm") as construtor:
        status = probe_provider(OLLAMA)

    assert status.verified is True
    # O ponto do teste: nenhum modelo foi instanciado nem invocado.
    assert construtor.called is False


def test_ollama_com_modelo_ausente_e_reprovado(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "modelo-que-nao-existe")
    payload = '{"models": [{"name": "llama3.2:3b"}]}'

    with patch.dict("sys.modules", {"langchain_ollama": MagicMock()}), _com_daemon(payload):
        status = probe_provider(OLLAMA)

    assert status.verified is False
    assert status.categoria == MODELO_INEXISTENTE
    assert "ollama pull" in status.detail


def test_ollama_aceita_nome_sem_tag(monkeypatch):
    """'llama3.2' e 'llama3.2:latest' são o mesmo modelo para o Ollama."""
    monkeypatch.setenv("MODEL_NAME", "llama3.2")
    payload = '{"models": [{"name": "llama3.2:latest"}]}'

    with patch.dict("sys.modules", {"langchain_ollama": MagicMock()}), _com_daemon(payload):
        assert probe_provider(OLLAMA).verified is True


def test_modelos_ollama_exclui_embedding():
    """
    Modelo de embedding não gera texto. Oferecê-lo no seletor de LLM só
    produziria erro na primeira pergunta.
    """
    payload = ('{"models": [{"name": "llama3.2:3b"}, {"name": "nomic-embed-text:latest"},'
               ' {"name": "qwen3.5:35b"}, {"name": "bge-m3:latest"}]}')
    with _com_daemon(payload):
        modelos = llm_factory.modelos_ollama()

    assert modelos == ["llama3.2:3b", "qwen3.5:35b"]


def test_modelos_ollama_vazio_se_daemon_fora_do_ar():
    """A tela precisa degradar para campo livre, não quebrar."""
    with patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
        assert llm_factory.modelos_ollama() == []


def test_ollama_fora_do_ar_e_reprovado(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "llama3.2:3b")

    with patch.dict("sys.modules", {"langchain_ollama": MagicMock()}), \
         patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
        status = probe_provider(OLLAMA)

    assert status.verified is False
    assert status.categoria == REDE
