import requests
import json
import time

API_URL = "http://localhost:8002"

def ask_question(question, session_id="test_session"):
    print(f"\n--- TESTANDO: {question} ---")
    payload = {
        "question": question,
        "session_id": session_id
    }
    
    start_time = time.time()
    try:
        response = requests.post(f"{API_URL}/investigate", json=payload, timeout=60)
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"RESPOSTA FINAL: {data['answer']}")
            print(f"FERRAMENTAS USADAS: {data['tools_used']}")
            print(f"PASSOS DE RACIOCÍNIO: {len(data['reasoning_steps'])}")
            print(f"TEMPO: {elapsed:.2f}s")
            
            for i, step in enumerate(data['reasoning_steps']):
                print(f"  Step {i+1}: Action={step['action']} | Input={step['action_input']}")
        else:
            print(f"ERRO API: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"ERRO DE CONEXÃO: {e}")

if __name__ == "__main__":
    print("Iniciando bateria de testes do Agente Investigador...")
    
    # Teste 1: Pura matemática (não deve usar RAG)
    ask_question("Quanto é 25 vezes 34?")
    
    # Teste 2: Pergunta que deve usar RAG (assumindo que há documentos no banco de dados do PRJ-01)
    ask_question("O que o documento fala sobre o projeto RAG?")
    
    # Teste 3: Multi-step (Matemática + Contexto - Exemplo hipotético)
    ask_question("Qual a soma de 100 com o número de documentos na base?")
