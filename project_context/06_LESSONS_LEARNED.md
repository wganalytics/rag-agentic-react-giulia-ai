# 💡 Lessons Learned: PRJ-03

## What Worked Well
- A técnica HyDE resolveu efetivamente o problema de queries monossilábicas.
- O isolamento do `hyde_engine` permitiu testes independentes de geração.

## What Failed or Was Difficult
- Modelos locais de 3B parâmetros podem gerar documentos hipotéticos curtos demais se não bem instigados.

## Bugs and Fixes
- **Fix:** Ajustado prompt para forçar tom técnico no `hyde_engine`.

## TDD Insights
- Mocks de embedding aceleram em 10x a bateria de testes de busca.

## Future Recommendations
- Implementar re-ranking (PRJ-07) em cima dos resultados do HyDE para refinamento final.
