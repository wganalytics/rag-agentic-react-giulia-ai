"""
PRJ-03: Agentic RAG — Servidor API FastAPI
Expõe o endpoint /investigate para interação com o Agente Investigador.
"""

import os
import shutil
from fastapi import FastAPI, HTTPException, Body, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .core.agent_engine import get_engine
from .core.llm_factory import (
    LLMConfigError,
    PROVIDERS,
    describe_provider,
    list_provider_status,
    modelos_ollama,
    probe_provider,
    resolve_provider,
)
from .core.tools import list_documents, remove_document, process_pdf, UPLOADS_DIR
from .api.schemas import (
    InvestigateRequest,
    InvestigateResponse,
    HealthResponse,
    ProvidersResponse,
    ReasoningStep
)

load_dotenv()

app = FastAPI(
    title="PRJ-03: Investigador Autônomo (Agentic RAG)",
    description="API para interação com agente ReAct capaz de usar ferramentas (RAG, Calculadora, Busca)",
    version="1.0.0"
)

# Configuração de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar engine no startup
engine = None

@app.on_event("startup")
async def startup_event():
    global engine
    engine = get_engine()

@app.get("/", response_model=HealthResponse)
async def root():
    """Endpoint de saúde do sistema."""
    if engine is None:
         return {
            "status": "starting",
            "engine": "AgenticEngine",
            "model": os.getenv("MODEL_NAME", "unknown"),
            "tools": []
        }
    
    return {
        "status": "ready",
        "engine": "AgenticEngine",
        "model": f"{engine.provider}/{engine.model_name}",
        "tools": [t.name for t in engine.tools]
    }


@app.get("/providers", response_model=ProvidersResponse, tags=["LLM"])
async def providers(probe: bool = False):
    """
    Lista os providers de LLM e o estado de cada um.

    Por padrão devolve só o estado de configuração (rápido, sem rede). Com
    `?probe=true` faz uma chamada real a cada provider — é a única forma de
    detectar conta sem crédito ou chave revogada.
    """
    if probe:
        status = []
        for nome in PROVIDERS:
            try:
                status.append(probe_provider(nome))
            except LLMConfigError:
                status.append(describe_provider(nome))
    else:
        status = list_provider_status()

    return {
        "default": resolve_provider(),
        "providers": [vars(s) for s in status],
        "ollama_models": modelos_ollama(),
    }

@app.post("/upload_pdf", tags=["Document Management"])
async def upload_document(file: UploadFile = File(...)):
    """Faz o upload de um PDF e processa para o VectorDB."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas PDFs são aceitos.")
    
    try:
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        file_path = os.path.join(UPLOADS_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        chunks = process_pdf(file_path)
        return {"filename": file.filename, "chunks": chunks, "message": "Processado com sucesso."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/list_docs", tags=["Document Management"])
async def list_docs():
    """Lista documentos na base."""
    return {"documents": list_documents()}

@app.delete("/remove_doc", tags=["Document Management"])
async def remove_doc(filename: str):
    """Remove um documento da base."""
    if remove_document(filename):
        return {"message": f"Documento {filename} removido."}
    raise HTTPException(status_code=500, detail="Erro ao remover documento.")

@app.post("/investigate", response_model=InvestigateResponse)
async def investigate(request: InvestigateRequest):
    """
    Endpoint principal para enviar perguntas ao agente investigador.
    O agente usará o loop ReAct para decidir quais ferramentas usar.
    """
    if engine is None:
        raise HTTPException(status_code=503, detail="Agent engine not initialized")

    # Sem provider no request, usa o motor do startup (padrão do .env).
    # Com provider, resolve o motor daquela combinação — cacheado por chave.
    try:
        alvo = engine if not (request.provider or request.model) else get_engine(
            provider=request.provider, model=request.model
        )
    except LLMConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        result = alvo.investigate(
            question=request.question,
            session_id=request.session_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
