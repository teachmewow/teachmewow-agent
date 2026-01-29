# TeachMeWoW Agent

Backend FastAPI com LangGraph para coaching de World of Warcraft.

## Arquitetura

O projeto segue uma arquitetura em camadas com separação de responsabilidades:

```
app/
├── domain/           # Entidades e interfaces (sem dependências externas)
│   ├── entities/     # Message, Thread, User
│   ├── value_objects/# MessageRole, WowClass, WowSpec
│   └── repositories/ # Interfaces de repositórios
├── infrastructure/   # Implementações concretas
│   ├── config/       # Settings (Pydantic)
│   ├── database/     # SQLAlchemy models e repositories
│   └── llm/          # Cliente OpenAI
├── application/      # Lógica de negócio
│   ├── agent/        # LangGraph (graph, nodes, tools, streaming)
│   └── services/     # ChatService, ThreadService
└── presentation/     # API FastAPI
    ├── api/          # Routes e dependencies
    ├── schemas/      # Pydantic request/response schemas
    └── serializers/  # Conversão entity -> schema
```

## Setup

### 1. Dependências

```bash
# Usando uv (recomendado)
uv sync

# Ou usando pip
pip install -e .
```

### 2. Variáveis de ambiente

```bash
cp .env.example .env
# Edite .env com suas configurações
```

### 3. Banco de dados

```bash
# Subir PostgreSQL com Docker
docker-compose up -d

# Rodar migrations
alembic upgrade head
```

### 4. Executar

```bash
# Desenvolvimento
uvicorn app.main:app --reload

# Ou
python -m app.main
```

## API Endpoints

### Chat

```
POST /agent/chat
```

Envia uma mensagem e recebe resposta via SSE (Server-Sent Events).

**Request:**
```json
{
  "input": "How do I play Arms Warrior?",
  "thread_id": "uuid_user123",
  "user_id": "user123",
  "class": "warrior",
  "spec": "arms",
  "role": "dps"
}
```

**Response (SSE):**
```
event: llm_delta
data: {"kind": "llm_delta", "content": "Arms Warrior is a..."}

event: tool_call
data: {"kind": "tool_call", "tool_name": "get_spec_info", "arguments": "..."}

event: tool_result
data: {"kind": "tool_result", "result": "..."}

event: done
data: {"kind": "done"}
```

### Threads

```
GET /threads/{thread_id}/messages
GET /threads/{thread_id}
DELETE /threads/{thread_id}
```

### Health

```
GET /health
```

## Arquitetura do Agent

O agente usa LangGraph para orquestração:

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │    agent    │ ◄─────────────┐
                    │  (LLM call) │               │
                    └──────┬──────┘               │
                           │                      │
                    ┌──────▼──────┐               │
                    │  has tools? │               │
                    └──────┬──────┘               │
                           │                      │
              ┌────────────┼────────────┐         │
              │ yes        │        no  │         │
              │            │            │         │
       ┌──────▼──────┐     │     ┌──────▼──────┐  │
       │    tools    │     │     │     END     │  │
       │  (execute)  │─────┘     └─────────────┘  │
       └──────┬──────┘                            │
              │                                   │
              └───────────────────────────────────┘
```

### Isolamento de Streaming

- **Grafo compilado**: Singleton stateless, compartilhado entre requests
- **Stream handler**: Criado por request, isolado
- **State do LangGraph**: Isolado por execução

## Tools Disponíveis

- `get_spec_info`: Retorna informações sobre uma especialização (mock)

## Desenvolvimento

### Criar nova migration

```bash
alembic revision --autogenerate -m "description"
```

### Aplicar migrations

```bash
alembic upgrade head
```

### Lint

```bash
ruff check .
ruff format .
```

### Testes

```bash
pytest
```
