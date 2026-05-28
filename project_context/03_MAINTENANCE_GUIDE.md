# 🔧 Maintenance Guide: PRJ-03

## How to Run
```bash
source venv/bin/activate
streamlit run frontend/app.py
```

## How to Test
```bash
python -m pytest tests/
python tests/test_*.py
```

## Common Fixes
- **Ollama Offline**: Reiniciar o serviço Ollama local.
- **ChromaDB Corrupt**: Remover `data/vector_db` e re-rodar scripts de ingestão.

## ⚠️ Emergency Recovery (Mandatory)
1. **Corrupted Vector DB**: `rm -rf data/vector_db && python scripts/ingestion.py`
2. **Missing Environment**: Recuperar de `.env.template`.
3. **Snapshot Desatualizado**: Rodar `python INFRA/start_project.py --snapshot PRJ-03`.

## Debugging Checklist
- [ ] O serviço Ollama está rodando?
- [ ] O banco ChromaDB foi populado?
- [ ] O arquivo `.env` contém as chaves corretas?

## Maintenance Risks
- Mudança de esquema no ChromaDB pode exigir re-indexação total.

## Safe Refactoring Notes
- Não alterar a interface do `Retriever` sem atualizar os scripts de teste TDD.
