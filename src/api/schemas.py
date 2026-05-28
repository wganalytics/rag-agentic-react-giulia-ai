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


class ReasoningStep(BaseModel):
    """Um passo do raciocínio do agente (Thought → Action → Observation)."""
    thought: str = Field(default="", description="Pensamento do agente")
    action: str = Field(..., description="Nome da ferramenta utilizada")
    action_input: str = Field(default="", description="Input passado à ferramenta")
    observation: str = Field(default="", description="Resultado da ferramenta")


class InvestigateResponse(BaseModel):
    """Response completa do agente investigador."""
    answer: str = Field(..., description="Resposta final sintetizada")
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
