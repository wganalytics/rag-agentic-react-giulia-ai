"""
PRJ-03: Agentic RAG — Ferramentas do Investigador Autônomo
Cada tool é uma ação que o agente pode escolher executar durante o loop ReAct.
"""

import os
import numexpr
import shutil
from langchain_core.tools import tool
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List, Optional, Any
from dotenv import load_dotenv

load_dotenv()

# ── Configurações ──────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "nomic-embed-text")

# Caminhos para o VectorDB e Uploads — reutiliza infra do ecossistema
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_DIR = os.path.join(PROJECT_ROOT, "data", "vector_db")
UPLOADS_DIR = os.path.join(PROJECT_ROOT, "data", "uploads")

# ── Inicialização lazy do VectorDB ─────────────────────────────
_vectorstore = None

def _get_vectorstore():
    """Inicializa o VectorDB uma única vez (singleton)."""
    global _vectorstore
    if _vectorstore is None:
        os.makedirs(DB_DIR, exist_ok=True)
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        embeddings = OllamaEmbeddings(
            model=EMBEDDING_MODEL,
            base_url=OLLAMA_BASE_URL
        )
        _vectorstore = Chroma(
            persist_directory=DB_DIR,
            embedding_function=embeddings
        )
    return _vectorstore


# ── Funções de Gerenciamento de Documentos ────────────────────

def process_pdf(file_path: str):
    """Lê um PDF, divide em chunks e salva no VectorDB."""
    vs = _get_vectorstore()
    
    loader = PyMuPDFLoader(file_path)
    docs = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, 
        chunk_overlap=100
    )
    splits = text_splitter.split_documents(docs)

    vs.add_documents(documents=splits)
    return len(splits)

def list_documents():
    """Lista todos os nomes de arquivos PDF que foram processados."""
    try:
        vs = _get_vectorstore()
        all_data = vs._collection.get()
        sources = set()
        for metadata in all_data['metadatas']:
            source_path = metadata.get('source', '')
            if source_path:
                sources.add(os.path.basename(source_path))
        return sorted(list(sources))
    except Exception as e:
        print(f"[TOOLS] Erro ao listar documentos: {e}")
        return []

def remove_document(filename: str):
    """Remove um documento específico do VectorDB e apaga o arquivo físico."""
    try:
        vs = _get_vectorstore()
        full_path = os.path.join(UPLOADS_DIR, filename)
        
        all_data = vs._collection.get()
        ids_to_delete = [
            all_data['ids'][i] 
            for i, metadata in enumerate(all_data['metadatas']) 
            if metadata.get('source', '').endswith(filename)
        ]
        
        if ids_to_delete:
            vs._collection.delete(ids=ids_to_delete)
        
        if os.path.exists(full_path):
            os.remove(full_path)
        
        return True
    except Exception as e:
        print(f"[TOOLS] Erro ao remover documento: {e}")
        return False


# ── Tool 1: Document Retriever (ChromaDB) ─────────────────────
@tool
def doc_retriever(query: Any) -> str:
    """Busca informações relevantes nos documentos PDF indexados no banco vetorial.
    Use esta ferramenta sempre como o primeiro passo para qualquer pergunta factual.
    Input: a pergunta ou termos de busca.
    Output: trechos relevantes dos documentos encontrados."""
    try:
        # Extração ultra-robusta da query, independentemente do que o LLM envie
        search_query = ""
        if isinstance(query, str):
            search_query = query
        elif isinstance(query, dict):
            search_query = query.get("query", query.get("value", query.get("action_input", str(query))))
        else:
            search_query = str(query)
            
        vs = _get_vectorstore()
        if vs._collection.count() == 0:
            return "Nenhum documento encontrado na base. Faça upload de PDFs primeiro."

        retriever = vs.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 4, "fetch_k": 8}
        )
        docs = retriever.invoke(query)

        if not docs:
            return "[NÃO LOCALIZADO] Nenhum trecho relevante encontrado para: '" + search_query + "' nos documentos indexados."

        results = []
        for i, doc in enumerate(docs, 1):
            source = os.path.basename(doc.metadata.get("source", "desconhecido"))
            page = doc.metadata.get("page", "N/A")
            results.append(
                f"[Trecho {i}] (Fonte: {source}, Pág: {page})\n{doc.page_content}"
            )
        return "\n\n---\n\n".join(results)
    except Exception as e:
        return f"Erro ao buscar documentos: {e}"


# ── Tool 2: Calculadora Matemática ────────────────────────────
@tool
def math_tool(expression: str) -> str:
    """Calculadora matemática para resolver expressões numéricas.
    Use esta ferramenta quando precisar calcular algo:
    somas, subtrações, multiplicações, divisões, porcentagens, etc.
    Input: expressão matemática válida (ex: '25 * 34', '100 / 3', '2**10').
    Output: resultado numérico."""
    try:
        # Limpar a expressão
        expr = expression.strip().replace("^", "**")
        # Remover caracteres não-matemáticos por segurança
        allowed = set("0123456789+-*/.() %eE")
        cleaned = "".join(c for c in expr if c in allowed)
        if not cleaned:
            return "Expressão inválida. Forneça uma expressão matemática como '25 * 34'."
        result = numexpr.evaluate(cleaned).item()
        return f"{cleaned} = {result}"
    except Exception as e:
        return f"Erro ao calcular '{expression}': {e}"


# ── Tool 3: Web Search (Real via DuckDuckGo com Links) ─────────
from langchain_community.tools import DuckDuckGoSearchResults

@tool
def web_search(query: str) -> str:
    """Busca informações na internet e retorna resultados COM LINKS. 
    Use esta ferramenta APENAS quando o usuário der permissão explícita
    após uma busca frustrada nos documentos internos.
    Input: termos de busca.
    Output: Lista de resultados com snippets e URLs de onde a informação veio."""
    try:
        search = DuckDuckGoSearchResults()
        return search.run(query)
    except Exception as e:
        return f"Erro ao realizar busca na web: {e}"


# ── Exportação ─────────────────────────────────────────────────
ALL_TOOLS = [doc_retriever, math_tool, web_search]

def get_tools():
    """Retorna a lista de ferramentas disponíveis para o agente."""
    return ALL_TOOLS
