"""
Fábrica de LLMs multi-provider do Agentic RAG.

Único ponto do projeto que sabe qual classe concreta de chat model instanciar.
O AgenticEngine pede um LLM e recebe um BaseChatModel pronto, sem conhecer
Ollama, Gemini, Grok ou Groq.

NOTA: isto vale só para o LLM de raciocínio (loop ReAct). Os *embeddings*
continuam locais no Ollama de propósito — trocar o modelo de embedding
invalidaria o ChromaDB já indexado, que teria de ser reconstruído do zero.

Providers suportados:
    ollama  -> LLM local via Ollama (padrão, sem custo, sem chave)
    gemini  -> Google Gemini (langchain-google-genai, GEMINI_API_KEY)
    grok    -> xAI Grok (langchain-xai, XAI_API_KEY)
    groq    -> Groq Cloud (langchain-groq, GROQ_API_KEY)

ATENÇÃO: 'grok' (xAI) e 'groq' (Groq Cloud) são empresas diferentes e uma letra
separa os dois. Cada um tem sua própria chave e seu próprio SDK.

As importações dos SDKs são preguiçosas: um provider que não está instalado
não quebra os outros.
"""

import os
from dataclasses import dataclass
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

OLLAMA = "ollama"
GEMINI = "gemini"
GROK = "grok"
GROQ = "groq"

PROVIDERS = (OLLAMA, GEMINI, GROK, GROQ)

# Rótulos amigáveis para a interface. Grok e Groq são deliberadamente
# distintos no texto para não serem confundidos na hora de escolher.
PROVIDER_LABELS = {
    OLLAMA: "🖥️  Ollama (local)",
    GEMINI: "☁️  Google Gemini",
    GROK: "🛰️  xAI Grok",
    GROQ: "⚡  Groq Cloud",
}

DEFAULT_MODELS = {
    OLLAMA: "llama3.2:3b",
    GEMINI: "gemini-2.5-flash",
    GROK: "grok-4-latest",
    GROQ: "llama-3.3-70b-versatile",
}

# Variável de ambiente que guarda o nome do modelo de cada provider.
# MODEL_NAME é o nome histórico usado no .env deste projeto.
MODEL_ENV_VARS = {
    OLLAMA: ("OLLAMA_MODEL_NAME", "MODEL_NAME"),
    GEMINI: ("GEMINI_MODEL_NAME",),
    GROK: ("GROK_MODEL_NAME",),
    GROQ: ("GROQ_MODEL_NAME",),
}

# Chaves aceitas por provider. A primeira encontrada vence.
# GROK_API_KEY não é aceito como alias do xAI: seria colisão com o Groq.
API_KEY_ENV_VARS = {
    GEMINI: ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    GROK: ("XAI_API_KEY",),
    GROQ: ("GROQ_API_KEY",),
}


class LLMConfigError(RuntimeError):
    """Configuração inválida ou incompleta para o provider solicitado."""


# ── Categorias de falha em chamada real ────────────────────────────────────
# Ter chave e SDK não significa que o provider responde: a conta pode estar
# sem crédito, a chave pode ter sido revogada, o modelo pode não existir.
SEM_CREDITO = "sem_credito"
CHAVE_INVALIDA = "chave_invalida"
LIMITE_TAXA = "limite_taxa"
MODELO_INEXISTENTE = "modelo_inexistente"
REDE = "rede"
DESCONHECIDO = "desconhecido"

CATEGORIA_LABELS = {
    SEM_CREDITO: "Conta sem crédito/licença",
    CHAVE_INVALIDA: "Chave inválida ou revogada",
    LIMITE_TAXA: "Limite de requisições atingido",
    MODELO_INEXISTENTE: "Modelo inexistente para esta conta",
    REDE: "Falha de rede ao alcançar o provider",
    DESCONHECIDO: "Falha não classificada",
}

# Assinaturas de texto por categoria, checadas em minúsculas na ordem abaixo.
#
# A ORDEM IMPORTA e não é arbitrária:
# - 429 vem primeiro porque o Google devolve "429 ... exceeded your current
#   quota ... billing details" para um limite por minuto do free tier. Sem
#   essa precedência isso viraria "sem crédito", e a orientação seria comprar
#   crédito quando bastava esperar.
# - 'sem crédito' vem antes de 'chave inválida' porque a xAI devolve o erro de
#   falta de crédito como 403 permission-denied, idêntico a uma chave revogada.
_ASSINATURAS = (
    (LIMITE_TAXA, ("rate limit", "rate_limit", "429", "too many requests",
                   "resource_exhausted", "resource exhausted")),
    (SEM_CREDITO, (
        "credit", "crédito", "billing", "quota", "licenses", "license",
        "insufficient_quota", "payment", "plano gratuito", "free tier",
    )),
    (CHAVE_INVALIDA, (
        "invalid api key", "invalid_api_key", "api key not valid",
        "unauthorized", "401", "authentication", "permission denied",
        "permission-denied", "403",
    )),
    (MODELO_INEXISTENTE, (
        "model not found", "does not exist", "unknown model",
        "decommissioned", "404",
    )),
    (REDE, (
        "connection", "timeout", "timed out", "unreachable",
        "name or service not known", "failed to establish",
    )),
)


def classificar_falha(erro: Exception) -> str:
    """
    Traduz a exceção do SDK numa categoria acionável.

    O objetivo é responder 'o que eu faço agora?': comprar crédito, trocar a
    chave, esperar, ou corrigir o nome do modelo.
    """
    texto = f"{type(erro).__name__} {erro}".lower()
    for categoria, marcas in _ASSINATURAS:
        if any(m in texto for m in marcas):
            return categoria
    return DESCONHECIDO


@dataclass
class ProviderStatus:
    """
    Diagnóstico de um provider.

    `available` = a *configuração* está completa (SDK instalado + chave presente).
    `verified`  = uma chamada real já foi feita: None = nunca testado,
                  True = respondeu, False = falhou.
    Os dois são coisas diferentes: um provider pode estar perfeitamente
    configurado e ainda assim recusar toda chamada por falta de crédito.
    """
    provider: str
    label: str
    model: str
    available: bool
    reason: str
    verified: Optional[bool] = None
    categoria: str = ""
    detail: str = ""


# Última falha real observada por provider, alimentada tanto pelo probe
# explícito quanto pelo uso normal da aplicação.
_ultima_falha: dict = {}

# Providers que já responderam a uma chamada real nesta execução.
_verificados: dict = {}


# Módulos cuja exceção NÃO é culpa do provider de LLM. Um Redis fora do ar ou
# um erro do banco vetorial não podem ser reportados como "provider falhou":
# isso mandaria o usuário procurar crédito ou trocar chave à toa.
_MODULOS_DE_INFRA = (
    "redis", "chromadb", "chroma", "neo4j", "sqlite3", "psycopg",
    "pymongo", "fitz", "pymupdf",
)


def falha_e_do_provider(erro: Exception) -> bool:
    """
    Decide se a exceção pode ser atribuída ao provider de LLM.

    Percorre a cadeia de causas: o LangChain frequentemente embrulha o erro
    original, e é na causa que aparece quem realmente quebrou.
    """
    vistos = set()
    atual = erro
    while atual is not None and id(atual) not in vistos:
        vistos.add(id(atual))
        modulo = (type(atual).__module__ or "").lower()
        if any(modulo.startswith(m) for m in _MODULOS_DE_INFRA):
            return False
        atual = atual.__cause__ or atual.__context__
    return True


def registrar_falha(provider: str, erro: Exception) -> Optional[str]:
    """
    Guarda a falha de uma chamada real, se ela for atribuível ao provider.

    Retorna a categoria classificada, ou None se a falha foi de infraestrutura
    (Redis, banco vetorial, grafo) e portanto não diz nada sobre o provider.
    """
    if not falha_e_do_provider(erro):
        return None
    categoria = classificar_falha(erro)
    _ultima_falha[provider] = (categoria, str(erro)[:300])
    return categoria


def registrar_sucesso(provider: str) -> None:
    """Limpa a falha registrada: o provider voltou a responder."""
    _ultima_falha.pop(provider, None)


def ultima_falha(provider: str):
    """(categoria, mensagem) da última falha real, ou None."""
    return _ultima_falha.get(provider)


def _first_env(*names: str) -> Optional[str]:
    """Retorna o valor da primeira variável de ambiente preenchida."""
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    return None


def resolve_provider(provider: Optional[str] = None) -> str:
    """
    Decide qual provider usar: argumento explícito > LLM_PROVIDER (.env) > ollama.
    """
    chosen = (provider or os.getenv("LLM_PROVIDER") or OLLAMA).strip().lower()
    if chosen not in PROVIDERS:
        raise LLMConfigError(
            f"Provider '{chosen}' desconhecido. Use um destes: {', '.join(PROVIDERS)}."
        )
    return chosen


def resolve_model(provider: str, model: Optional[str] = None) -> str:
    """
    Decide qual modelo usar: argumento explícito > variável do provider > padrão.
    """
    if model:
        return model.strip()
    return _first_env(*MODEL_ENV_VARS[provider]) or DEFAULT_MODELS[provider]


def resolve_api_key(provider: str) -> Optional[str]:
    """Retorna a chave de API do provider, ou None se ele não exigir chave."""
    if provider not in API_KEY_ENV_VARS:
        return None
    return _first_env(*API_KEY_ENV_VARS[provider])


def _require_api_key(provider: str) -> str:
    key = resolve_api_key(provider)
    if not key:
        aceitas = " ou ".join(API_KEY_ENV_VARS[provider])
        raise LLMConfigError(
            f"Provider '{provider}' exige chave de API. Defina {aceitas} no .env."
        )
    return key


def _build_ollama(model: str, temperature: float, max_retries: Optional[int] = None):
    try:
        from langchain_ollama import ChatOllama
    except ImportError as e:  # pragma: no cover - depende do ambiente
        raise LLMConfigError(
            "Pacote 'langchain-ollama' não instalado. Rode: pip install langchain-ollama"
        ) from e

    base_url = _first_env("OLLAMA_HOST", "OLLAMA_BASE_URL") or "http://localhost:11434"
    return ChatOllama(model=model, base_url=base_url, temperature=temperature)


def _build_gemini(model: str, temperature: float, max_retries: Optional[int] = None):
    # A chave é checada ANTES do import: faltar chave é o erro mais comum
    # e o mais acionável. Importar primeiro faria uma falha de ambiente
    # mascarar a mensagem útil.
    chave = _require_api_key(GEMINI)

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as e:  # pragma: no cover - depende do ambiente
        raise LLMConfigError(
            "Pacote 'langchain-google-genai' não instalado. "
            "Rode: pip install langchain-google-genai"
        ) from e

    extra = {} if max_retries is None else {"max_retries": max_retries}
    return ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        google_api_key=chave,
        **extra,
    )


def _build_grok(model: str, temperature: float, max_retries: Optional[int] = None):
    # A chave é checada ANTES do import: faltar chave é o erro mais comum
    # e o mais acionável. Importar primeiro faria uma falha de ambiente
    # mascarar a mensagem útil.
    chave = _require_api_key(GROK)

    try:
        from langchain_xai import ChatXAI
    except ImportError as e:  # pragma: no cover - depende do ambiente
        raise LLMConfigError(
            "Pacote 'langchain-xai' não instalado. Rode: pip install langchain-xai"
        ) from e

    extra = {} if max_retries is None else {"max_retries": max_retries}
    return ChatXAI(
        model=model,
        temperature=temperature,
        xai_api_key=chave,
        **extra,
    )


def _build_groq(model: str, temperature: float, max_retries: Optional[int] = None):
    # A chave é checada ANTES do import: faltar chave é o erro mais comum
    # e o mais acionável. Importar primeiro faria uma falha de ambiente
    # mascarar a mensagem útil.
    chave = _require_api_key(GROQ)

    try:
        from langchain_groq import ChatGroq
    except ImportError as e:  # pragma: no cover - depende do ambiente
        raise LLMConfigError(
            "Pacote 'langchain-groq' não instalado. Rode: pip install 'langchain-groq<1.0'"
        ) from e

    extra = {} if max_retries is None else {"max_retries": max_retries}
    return ChatGroq(
        model=model,
        temperature=temperature,
        api_key=chave,
        **extra,
    )


_BUILDERS = {
    OLLAMA: _build_ollama,
    GEMINI: _build_gemini,
    GROK: _build_grok,
    GROQ: _build_groq,
}


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_retries: Optional[int] = None,
):
    """
    Instancia o chat model do provider escolhido.

    Args:
        provider: 'ollama', 'gemini' ou 'grok'. None usa LLM_PROVIDER do .env.
        model: nome do modelo. None usa a variável do provider ou o padrão.
        temperature: 0.0 por padrão — geração de Cypher precisa ser determinística.
        max_retries: None mantém o padrão do SDK. 0 desliga o retry — usado pelo
            probe, onde esperar o backoff de um 429 travaria a tela por mais de
            um minuto.

    Raises:
        LLMConfigError: provider inválido, SDK ausente ou chave de API faltando.
    """
    chosen = resolve_provider(provider)
    model_name = resolve_model(chosen, model)
    return _BUILDERS[chosen](model_name, temperature, max_retries)


def describe_provider(provider: str) -> ProviderStatus:
    """
    Estado de configuração do provider (SDK + chave), sem abrir conexão.

    Se uma chamada real já falhou antes, o motivo aparece aqui — é o que evita
    exibir "Pronto" para um provider que recusa toda requisição por falta de
    crédito. Use probe_provider() para confirmar ao vivo.
    """
    model = resolve_model(provider, None)
    label = PROVIDER_LABELS[provider]

    if provider in API_KEY_ENV_VARS and not resolve_api_key(provider):
        aceitas = " ou ".join(API_KEY_ENV_VARS[provider])
        return ProviderStatus(provider, label, model, False, f"Falta {aceitas} no .env")

    module = {
        OLLAMA: "langchain_ollama",
        GEMINI: "langchain_google_genai",
        GROK: "langchain_xai",
        GROQ: "langchain_groq",
    }[provider]

    try:
        __import__(module)
    except Exception:
        # Qualquer falha ao importar o SDK — ausente, versão incompatível ou
        # conflito de dependência — significa provider inutilizável. Capturar
        # só ImportError deixava o diagnóstico estourar em vez de informar.
        return ProviderStatus(provider, label, model, False,
                              f"Pacote '{module}' não pôde ser importado")

    falha = ultima_falha(provider)
    if falha:
        categoria, detalhe = falha
        return ProviderStatus(
            provider, label, model,
            available=True,
            reason=CATEGORIA_LABELS.get(categoria, CATEGORIA_LABELS[DESCONHECIDO]),
            verified=False,
            categoria=categoria,
            detail=detalhe,
        )

    if _verificados.get(provider):
        return ProviderStatus(provider, label, model, True, "Verificado", verified=True)

    # Configurado, mas ninguém provou que responde.
    return ProviderStatus(provider, label, model, True, "Configurado (não verificado)")


# Prompt mínimo do probe: barato em token e determinístico.
_PING = "Responda apenas com a palavra: OK"


def _consultar_ollama(caminho: str, timeout: int = 5):
    """GET no daemon do Ollama. Devolve o JSON ou levanta a exceção original."""
    import json as _json
    import urllib.request

    base = (_first_env("OLLAMA_HOST", "OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
    with urllib.request.urlopen(f"{base}{caminho}", timeout=timeout) as resposta:
        return _json.load(resposta)


# Modelos de embedding não geram texto: oferecê-los como LLM de chat só
# produz erro na primeira pergunta.
_MARCAS_DE_EMBEDDING = ("embed", "bge-", "gte-", "e5-")


def modelos_ollama() -> List[str]:
    """
    Modelos de chat instalados no Ollama, em ordem alfabética.

    Serve para a tela oferecer os modelos que a máquina realmente tem, em vez
    de um campo de texto livre onde errar o nome só aparece na hora de usar.
    Lista vazia = daemon fora do ar ou sem modelos.
    """
    try:
        dados = _consultar_ollama("/api/tags")
    except Exception:
        return []

    nomes = [m.get("name", "") for m in dados.get("models", [])]
    return sorted(
        n for n in nomes
        if n and not any(marca in n.lower() for marca in _MARCAS_DE_EMBEDDING)
    )


def _probe_ollama(modelo: str) -> ProviderStatus:
    """
    Verifica o Ollama sem gerar texto.

    Gerar uma resposta obrigaria a carregar o modelo na memória — dezenas de
    segundos para um modelo de 35B, o que tornaria a abertura da tela lenta
    demais. Consultar o daemon prova o que interessa aqui: ele está no ar e o
    modelo pedido está instalado.
    """
    base = (_first_env("OLLAMA_HOST", "OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
    label = PROVIDER_LABELS[OLLAMA]

    try:
        dados = _consultar_ollama("/api/tags")
    except Exception as e:
        registrar_falha(OLLAMA, e)
        return ProviderStatus(
            OLLAMA, label, modelo, available=True,
            reason="Ollama não está respondendo", verified=False,
            categoria=REDE, detail=f"{base}: {e}"[:300],
        )

    instalados = [m.get("name", "") for m in dados.get("models", [])]
    # 'llama3.2' e 'llama3.2:latest' são o mesmo modelo para o Ollama.
    alvo = modelo if ":" in modelo else f"{modelo}:latest"
    if alvo not in instalados and modelo not in instalados:
        erro = Exception(f"modelo '{modelo}' não instalado no Ollama")
        registrar_falha(OLLAMA, erro)
        return ProviderStatus(
            OLLAMA, label, modelo, available=True,
            reason="Modelo não instalado no Ollama", verified=False,
            categoria=MODELO_INEXISTENTE,
            detail=f"Rode: ollama pull {modelo}",
        )

    registrar_sucesso(OLLAMA)
    _verificados[OLLAMA] = True
    return ProviderStatus(OLLAMA, label, modelo, available=True,
                          reason="Verificado", verified=True)


def probe_provider(provider: str, model: Optional[str] = None) -> ProviderStatus:
    """
    Faz uma chamada real e mínima ao provider e devolve o status resultante.

    É a única forma de distinguir "configurado" de "funcionando": problemas de
    crédito, chave revogada e modelo inexistente só aparecem no primeiro uso.
    """
    estado = describe_provider(provider)
    if not estado.available:
        return estado  # nem dá para tentar: falta chave ou SDK

    modelo = resolve_model(provider, model)

    if provider == OLLAMA:
        return _probe_ollama(modelo)

    try:
        llm = get_llm(provider, modelo)
        llm.invoke(_PING)
    except LLMConfigError:
        raise
    except Exception as e:
        categoria = registrar_falha(provider, e)
        _verificados.pop(provider, None)
        return ProviderStatus(
            provider, PROVIDER_LABELS[provider], modelo,
            available=True,
            reason=CATEGORIA_LABELS.get(categoria, CATEGORIA_LABELS[DESCONHECIDO]),
            verified=False,
            categoria=categoria,
            detail=str(e)[:300],
        )

    registrar_sucesso(provider)
    _verificados[provider] = True
    return ProviderStatus(
        provider, PROVIDER_LABELS[provider], modelo,
        available=True, reason="Verificado", verified=True,
    )


def list_provider_status() -> List[ProviderStatus]:
    """Diagnóstico de todos os providers, na ordem de PROVIDERS."""
    return [describe_provider(p) for p in PROVIDERS]
