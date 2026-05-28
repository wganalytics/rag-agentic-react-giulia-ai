# 🧠 Operational Memory: PRJ-03

## 🚀 Project Milestones
- [x] Initial Planning (SDD)
- [x] Core Implementation
- [x] TDD Validation
- [x] Final Governance Snapshot

## 📓 Relevant Sessions (Filtered)
# 📓 Diário de Bordo do Ecossistema RAG

> **Propósito:** Este documento é o registro cronológico de todas as sessões de desenvolvimento, decisões técnicas e progresso do projeto. Ele existe para garantir **continuidade entre diferentes agentes de IA (LLMs)**, permitindo que qualquer modelo que entre no projeto possa ler este arquivo e compreender imediatamente o estado atual, as convenções adotadas e o que falta fazer.
>
> **Regra:** Toda sessão de trabalho relevante deve gerar uma nova entrada neste diário. Ao final de cada sessão, o agente ativo deve adicionar um bloco resumindo o que foi feito e quais são os próximos passos.

---

## 🔑 Leitura Obrigatória para Novos Agentes

Se você é um agente de IA lendo este documento pela primeira vez, siga estes passos **antes de fazer qualquer coisa**:

1. **Leia o Manual:** [MANUAL_DO_ECOSSISTEMA.md](./MANUAL_DO_ECOSSISTEMA.md) — contém toda a estrutura de pastas, convenções, ferramentas e regras do projeto.
2. **Leia o Workflow:** O arquivo `.agents/workflows/padrao_desenvolvimento_jira.md` na raiz do projeto define como você deve interagir com o Jira automaticamente.
3. **Leia a última entrada deste diário** para entender o estado atual do projeto.
4. **Verifique `ideia.md` e o `implementation_plan.md`** do projeto ativo em `PLANNING_DOCS/PRJ-XX_*/`.

---

## 📊 Status Geral do Portfólio

| Projeto | Status | Última Atualização |
|---------|--------|--------------------|
| PRJ-01: Vanilla RAG | 🟢 Concluído | 2026-04-27 |
| PRJ-02: RAG com Memória | 🟢 Concluído | 2026-04-27 |
| PRJ-03: Agentic RAG | 🟢 Concluído | 2026-04-29 |
| PRJ-04: Corrective RAG | 🟢 Concluído | 2026-05-07 |
| PRJ-05: Adaptive RAG | 🟢 Concluído | 2026-05-07 |
| PRJ-06: GraphRAG | 🟢 Concluído | 2026-05-08 |
| PRJ-07: Hybrid RAG | 🟢 Concluído | 2026-05-08 |
| PRJ-08: HyDE RAG | 🟢 Concluído | 2026-05-08 |
| PRJ-09: Deploy Cloud | 🟡 Em Desenvolvimento | 2026-05-10 |

**Legenda:** ⚪ Backlog | 🟡 Em Desenvolvimento | 🟢 Concluído

---

## 📝 Registro de Sessões

---


---
### Sessão #018 — 2026-05-10
**Agente:** Antigravity (Opus)  
**Foco:** Correção Estrutural — Auditoria Pós-Análise

**O que foi feito:**
- **Jira — Subtasks duplicadas**: Auditados todos os épicos GARE. Encontradas e removidas 29 subtasks duplicadas do PRJ-01 (GARE-96 a GARE-124 eram cópias de GARE-4 a GARE-38).
- **Jira — Estimativas zeradas**: Corrigidas 49 tasks com `Original Estimate: 0m` usando `projetos.yaml` como fonte de verdade.
- **Documentação sincronizada**: Atualizados STATUS.md, CONTEXTO_RLM.md e DIARIO_DE_BORDO.md para refletir os 8 projetos concluídos com keys GARE corretas.
- **ideia.md PRJ-08**: Preenchido com dados reais pós-conclusão (tecnologias, resultados, arquitetura).
- **README.md**: Atualizado com status corretos e modelo LLM correto.
- **Prevenção**: Scripts `fix_duplicate_subtasks.py` e `fix_estimates.py` criados. Validação remota adicionada no `jira_sync.py`. Numeração anti-colisão no `atualizar_diario.py`.

**Scripts criados:**
- `INFRA/core/fix_duplicate_subtasks.py` — Audita e remove subtasks duplicadas
- `INFRA/core/fix_estimates.py` — Corrige estimativas zeradas via YAML

**Decisões tomadas:**
- Keys reais confirmadas via API: GARE-1 (PRJ-01), GARE-39 (PRJ-02), GARE-46 (PRJ-03), GARE-53 (PRJ-04), GARE-60 (PRJ-05), GARE-67 (PRJ-06), GARE-74 (PRJ-07), GARE-81 (PRJ-08), GARE-88 (PRJ-09).
- GARE-2 é um épico duplicado do PRJ-01 (mantido por histórico).

---


---
### Sessão #007 — 2026-04-16
**Agente:** Claude  
**Foco:** Jira Manager + Sincronização de Todos os Projetos

**O que foi feito:**
- Identificado que a API do Jira usada estava desatualizada (ERA /rest/api/2/search que retornava 410 Gone)
- Corrigido o endpoint para `/rest/api/3/search/jql` (API atual do Jira Cloud)
- Criado script `INFRA/core/jira_manager.py` - gerenciador completo de épicos e tasks com opções CLI:
  - `--epics`: Lista todos os épicos
  - `--tasks`: Lista todas as tasks
  - `--details KEY`: Ver detalhes de uma issue
  - `--update KEY --summary/--description/--priority/--duedate/--storypoints/--estimate`: Atualiza campos
  - `--move KEY "STATUS"`: Move issue para novo status
  - `--comment KEY "TEXTO"`: Adiciona comentário
  - `--subtasks KEY`: Lista subtarefas
  - `--interactive`: Modo interativo
- Corrigido o épico RAG-332 (PRJ-01):
  - Nome: alterado de "Ecosistema: Sistema de QA Corporativo" para "PRJ-01 - Sistema de QA Corporativo (Vanilla RAG)"
  - Descrição: expandida com objetivos completos do projeto
  - Story Points: configurado para 21 (total das tasks)
- Corrigido as 7 tasks do PRJ-01 no Jira:
  - Adicionado Original Estimate em horas (8h, 4h, 6h, etc)
  - Adicionado Story Points via customfield_10016 (1-2 por task)
- Atualizado `INFRA/config/projetos.yaml` com dados completos de todos os 9 projetos:
  - PRJ-01 a PRJ-09 com descrições detalhadas
  - Tasks com User Stories, critérios de aceite, estimates, story points, due days, labels
- Criado script `INFRA/core/sync_all_projects.py` que sincroniza projetos do YAML para o Jira
- Executado sync completo - criados 57 items no Jira:
  - PRJ-01: 1 épico (RAG-332) + 7 tasks (RAG-333 a RAG-365)
  - PRJ-02: 1 épico (RAG-369) + 6 tasks (RAG-370 a RAG-375)
  - PRJ-03: 1 épico (RAG-376) + 6 tasks (RAG-377 a RAG-382)
  - PRJ-04: 1 épico (RAG-383) + 6 tasks (RAG-384 a RAG-389)
  - PRJ-05: 1 épico (RAG-390) + 6 tasks (RAG-391 a RAG-396)
  - PRJ-06: 1 épico (RAG-397) + 6 tasks (RAG-398 a RAG-403)
  - PRJ-07: 1 épico (RAG-404) + 6 tasks (RAG-405 a RAG-410)
  - PRJ-08: 1 épico (RAG-411) + 6 tasks (RAG-412 a RAG-417)
  - PRJ-09: 1 épico (RAG-418) + 7 tasks (RAG-419 a RAG-425)

**Decisões tomadas:**
- Story Points usa campo `customfield_10016` (Story point estimate) - o campo padrão 10033 não está disponível na tela
- Original Estimate usa campo `timetracking.originalEstimateSeconds`
- O script de sync é idempotente - detecta épicos existentes pela key PRJ-XX no summary
- API do Jira Cloud requer autenticação com email + API token (não senha)

**Jira Issues criadas/atualizadas:**
- RAG-332: Épico PRJ-01 atualizado com nome, descrição e 21 SP
- RAG-333 a RAG-365: 7 tasks PRJ-01 com estimates e SP
- RAG-369 a RAG-425: 50 tasks PRJ-02 a PRJ-09 criadas

---


---
### Sessão #011 — 2026-04-29
**Agente:** Gemini (Antigravity)
**Foco:** Implementação e Validação do PRJ-03 (Agentic RAG)

**O que foi feito:**
- **Motor ReAct com Classic LangChain**: Superado o desafio de versionamento do LangChain no ambiente local (v1.2.15) migrando para o pacote `langchain_classic` para habilitar `create_tool_calling_agent` e `AgentExecutor`.
- **Estratégia de Sanitização de Ferramentas**: Implementada camada de tratamento de entrada na `doc_retriever` para converter inputs em dicionário (JSONSchema literal) de volta para strings, corrigindo erros de validação do Pydantic causados pelo `llama3.2:3b`.
- **Arquitetura de Ferramentas**: Implementadas `doc_retriever` (ChromaDB), `math_tool` (Numexpr) e uma `web_search_fallback` baseada no princípio Privacy-First.
- **Frontend Streamlit**: Desenvolvida interface com suporte a visualização de "pílulas de raciocínio", permitindo ao usuário acompanhar o trace do pensamento do agente (Thought/Action/Observation).
- **Encerramento de Fase**: Movidos os tickets GARE-48, GARE-49, GARE-50 e GARE-51 para `Done`.

**Decisões tomadas:**
- Adoção do `langchain_classic` como padrão temporário para manter o suporte a agentes ReAct estáveis na versão atual do ecossistema.
- Sanitização de inputs de ferramentas no nível do Python para compensar instabilidades de tool-calling em LLMs locais menores.

**Jira Issues tocadas:**
- GARE-48, GARE-49, GARE-50, GARE-51: Movidas para `Done`.

---


---
### Sessão #012 — 2026-04-29
**Agente:** OpenCode (Antigravity)
**Foco:** Correções de Resposta e Validacao Final do PRJ-03

**O que foi feito:**
- **Correção de Imports**: Alterado `langchain_classic` para `langchain.agents` (pacote correto na versão instalada).
- **Post-processamento de Resposta**: Adicionado regex para limpar trechos crus `[Trecho N]` retornados pelo modelo.
- ** Tags de Feedback**:
  - `[NÃO LOCALIZADO]`: Quando doc_retriever não encontra nada no documento.
  - `[BUSCA EM DOCUMENTO]`: Quando resposta vem do documento (não é final).
  - `[BUSCA EXTERNA]`: Quando resposta vem da web.
- ** Dependências**: Instalado pacote `ddgs` para busca DuckDuckGo.
- **Limpeza ChromaDB**: Corrigido banco vetorial corrompido removendo arquivos e recriando.

**Decisões tomadas:**
- Modelo `llama3.2:3b` tem limitação em formatar saída - post-processamento em Python necessário.
- Tagsavisam usuário sobre origem da resposta para evitar confusão.

**Próximos passos:**
- Encerrar tickets restantes do PRJ-03 no Jira.

---

## 🧭 Orientações para o Próximo Agente

> **⚠️ LEIA PRIMEIRO:** Antes deste diário, leia o `CONTEXTO_RLM.md`.

**Estado atual (2026-05-11):**
- PRJ-01 a PRJ-08: 100% concluídos. Ecossistema Jira sincronizado sob a chave `GARE`.
- PRJ-09 (Deploy Cloud): Em desenvolvimento — épico GARE-88 In Progress, tasks GARE-89 a GARE-94 Done, GARE-95 (Documentação) em Backlog.
- Infraestrutura de governança ativa: `validate_ecosystem.py`, `lifecycle_manager.py`, `rebuild_sync_state.py`.

**O que fazer agora:**
1. Ler `CONTEXTO_RLM.md` para estado atual completo.
2. Rodar `python3 INFRA/core/validate_ecosystem.py` para garantir consistência.
3. Iniciar GARE-95 (Documentação do PRJ-09): `python3 INFRA/core/atualizar_tarefa.py GARE-95 in_progress`.
4. Ao encerrar sessão: rodar `validate_ecosystem.py` + commit semântico + atualizar este diário.

---


## 🤝 Agent Handoff Notes
- **Current State:** Estável e validado localmente.
- **Critical Path:** Manter integridade do pipeline RAG durante atualizações de biblioteca.
- **Focus:** Preparação para PRJ-09 (Cloud).
