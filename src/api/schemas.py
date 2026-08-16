"""
PRJ-03: Agentic RAG — Schemas Pydantic para a API
Modelos de request/response do endpoint /investigate.
"""

from pydantic import BaseModel, Field
from typing import Optional


class InvestigateRequest(BaseModel):
    """Request para o endpoint /investigate."""
    question: str = Field(..., description="Pergunta do investigador", min_length=3)
    session_id: str = Field(default="default", description="ID da sessão para memória")
    provider: Optional[str] = Field(
        default=None,
        description="LLM a usar: ollama | gemini | grok | groq. Omitido = padrão do .env"
    )
    model: Optional[str] = Field(
        default=None,
        description="Modelo dentro do provider. Omitido = padrão do provider"
    )


class ReasoningStep(BaseModel):
    """Um passo do raciocínio do agente (Thought → Action → Observation)."""
    thought: str = Field(default="", description="Pensamento do agente")
    action: str = Field(..., description="Nome da ferramenta utilizada")
    action_input: str = Field(default="", description="Input passado à ferramenta")
    observation: str = Field(default="", description="Resultado da ferramenta")


class ProviderStatus(BaseModel):
    """
    Situação de um provider de LLM.

    'available' é configuração (SDK + chave); 'verified' é comportamento real.
    Um provider pode estar configurado e mesmo assim recusar toda chamada —
    conta sem crédito é o caso típico, e só aparece numa chamada de verdade.
    """
    provider: str = Field(..., description="Identificador: ollama | gemini | grok | groq")
    label: str = Field(..., description="Nome amigável para exibição")
    model: str = Field(..., description="Modelo que será usado por padrão")
    available: bool = Field(..., description="SDK instalado e chave presente")
    reason: str = Field(..., description="Resumo legível do estado atual")
    verified: Optional[bool] = Field(
        default=None,
        description="None = nunca testado; True = respondeu; False = falhou numa chamada real"
    )
    categoria: str = Field(default="", description="Categoria da falha, quando houver")
    detail: str = Field(default="", description="Mensagem original da última falha")


class ProvidersResponse(BaseModel):
    """Lista de providers e qual é o padrão atual."""
    default: str = Field(..., description="Provider usado quando nenhum é informado")
    providers: list[ProviderStatus] = Field(default_factory=list)
    ollama_models: list[str] = Field(
        default_factory=list,
        description="Modelos de chat instalados no Ollama desta máquina"
    )


class InvestigateResponse(BaseModel):
    """Response completa do agente investigador."""
    answer: str = Field(..., description="Resposta final sintetizada")
    provider: str = Field(default="", description="Provider que respondeu")
    model: str = Field(default="", description="Modelo que respondeu")
    reasoning_steps: list[ReasoningStep] = Field(
        default_factory=list,
        description="Trace completo do raciocínio (Thought/Action/Observation)"
    )
    tools_used: list[str] = Field(
        default_factory=list,
        description="Lista de ferramentas utilizadas"
    )
    session_id: str = Field(default="default", description="ID da sessão utilizada")


class UploadResponse(BaseModel):
    """Response do upload de PDFs."""
    filename: str
    chunks_created: int
    message: str


class HealthResponse(BaseModel):
    """Response do health check."""
    status: str
    engine: str
    model: str
    tools: list[str]
