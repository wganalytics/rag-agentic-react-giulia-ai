"""
Diagnóstico dos providers de LLM do GraphRAG.

Mostra quais providers estão prontos (SDK instalado + chave presente) e,
com --live, faz uma chamada real de baixo custo em cada um para confirmar
que a credencial funciona de verdade.

Uso:
    python3 scripts/verify_llm.py
    python3 scripts/verify_llm.py --live
    python3 scripts/verify_llm.py --live --provider gemini
"""

import argparse
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.llm_factory import (  # noqa: E402
    PROVIDERS,
    SEM_CREDITO,
    CHAVE_INVALIDA,
    MODELO_INEXISTENTE,
    LIMITE_TAXA,
    describe_provider,
    probe_provider,
)

# O que fazer diante de cada categoria de falha.
SUGESTOES = {
    SEM_CREDITO: "Adicione crédito/licença no painel do provider. A chave está correta.",
    CHAVE_INVALIDA: "Gere uma nova chave e atualize o .env.",
    LIMITE_TAXA: "Aguarde e tente de novo, ou reduza a frequência de chamadas.",
    MODELO_INEXISTENTE: "Confira o nome do modelo na variável *_MODEL_NAME do .env.",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica os providers de LLM.")
    parser.add_argument("--live", action="store_true",
                        help="Faz uma chamada real a cada provider (única forma de detectar falta de crédito).")
    parser.add_argument("--provider", choices=PROVIDERS, help="Verifica apenas um provider.")
    args = parser.parse_args()

    alvos = [args.provider] if args.provider else list(PROVIDERS)
    falhas = 0

    print("=" * 66)
    print("Providers de LLM — PRJ-03 Agentic RAG")
    print("=" * 66)

    for provider in alvos:
        status = probe_provider(provider) if args.live else describe_provider(provider)

        if not status.available:
            icone = "⛔"
        elif status.verified is True:
            icone = "✅"
        elif status.verified is False:
            icone = "⛔"
        else:
            icone = "⚙️ "

        print(f"\n{icone} {provider:8s} modelo={status.model}")
        print(f"   {status.reason}")

        if status.detail:
            print(f"   detalhe: {status.detail[:160]}")
        if status.categoria in SUGESTOES:
            print(f"   → {SUGESTOES[status.categoria]}")

        if not status.available or status.verified is False:
            falhas += 1

    print("\n" + "=" * 66)
    if not args.live:
        print("Sem --live isto verifica apenas SDK e chave. Falta de crédito não")
        print("aparece aqui: rode 'verify_llm.py --live' para confirmar de verdade.")
    if falhas:
        print(f"{falhas} provider(s) com problema.")
    else:
        print("Nenhum problema detectado.")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
