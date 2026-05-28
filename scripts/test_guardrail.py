import os
import sys
from dotenv import load_dotenv

# Adiciona o diretório src ao path
sys.path.append(os.path.join(os.getcwd(), "src"))

from core.agent_engine import get_engine

def test_hallucination():
    engine = get_engine()
    session_id = "test_guardrail"
    question = "O que é openclaw"
    
    print(f"\n--- TESTANDO PERGUNTA: {question} ---")
    result = engine.investigate(question, session_id)
    
    print("\nRESPOSTA FINAL:")
    print(result["answer"])
    
    print("\nPASSOS DE RACIOCÍNIO:")
    for i, step in enumerate(result["reasoning_steps"], 1):
        print(f"\nPasso {i}:")
        print(f"Pensamento: {step['thought']}")
        print(f"Ação: {step['action']}")
        print(f"Input: {step['action_input']}")
        print(f"Observação: {step['observation']}")

if __name__ == "__main__":
    test_hallucination()
