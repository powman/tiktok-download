HELLO WORLD API - FastAPI

DESCRICAO:
API simples de Hello World criada com FastAPI. A API possui dois endpoints GET
que retornam "Hello World" em formato JSON.

ENDPOINTS:
1. GET / - Retorna {"message": "Hello World"}
2. GET /hello - Retorna {"message": "Hello World"}

COMO INSTALAR E RODAR:

1. INSTALAR DEPENDENCIAS:
   pip install -r requirements.txt

2. RODAR A API:
   python hello_api.py

   OU usar uvicorn diretamente:
   uvicorn hello_api:app --reload --host 0.0.0.0 --port 8000

3. ACESSAR A API:
   - No navegador: http://localhost:8000
   - Ou use curl:
     curl http://localhost:8000/
     curl http://localhost:8000/hello

4. DOCUMENTACAO INTERATIVA:
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

OPCOES DE EXECUCAO:

Option 1 - Script Python direto:
   python hello_api.py

Option 2 - Uvicorn com reload (desenvolvimento):
   uvicorn hello_api:app --reload --port 8000

Option 3 - Uvicorn producao:
   uvicorn hello_api:app --host 0.0.0.0 --port 8000 --workers 4

REQUISITOS:
- Python 3.7+
- FastAPI
- Uvicorn

NOTA:
A porta padrao e 8000. Voce pode mudar editando a porta nos comandos acima.
