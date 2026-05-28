# 🏗️ Architecture Log: PRJ-03

## Architecture Overview
Implementação baseada no padrão GIULIA RAG Ecosystem, utilizando Clean Architecture e isolamento por domínio.

## Core Components
- **Engine**: Core logic (LLM/Search).
- **Retriever**: Vector database interface.
- **Observatory**: Telemetria e métricas.
- **Frontend**: Streamlit UI.

## Key Architecture Decisions
1. **Local-First Execution**: Priorização do Ollama local para privacidade total de dados.
2. **Standard Vector Search**: Uso de ChromaDB por simplicidade e performance em ambientes locais.

## Trade-offs
- **Performance vs Accuracy**: O uso de modelos menores (`llama3.2:3b`) reduz latência mas exige prompts mais robustos.

## ❌ Rejected Alternatives (Mandatory)
- **Query Expansion Only**: Rejeitado em favor do HyDE pois o HyDE lida melhor com queries muito curtas/vagas.
- **Neo4j for Semantic Search**: Rejeitado neste projeto para manter simplicidade; grafos reservados para PRJ-06.

## Risks and Mitigations
- **Model Hallucination**: Mitigado via RAG Guardrails e post-processing filters.

## Future Evolution
- Migração para agentes agentic (PRJ-03) integrados ao core do HyDE.
