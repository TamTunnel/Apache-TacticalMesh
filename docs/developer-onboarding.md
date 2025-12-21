# Developer Onboarding Guide

## Apache TacticalMesh — Getting Started for Developers

This guide will help you set up a development environment and become productive with Apache TacticalMesh within a day.

---

## Prerequisites

Before you begin, ensure you have the following installed:

### Required

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Backend controller and agent |
| Node.js | 20+ | Frontend console |
| Docker | Latest | Container deployment |
| Docker Compose | Latest | Multi-container orchestration |
| Git | Latest | Version control |

### Recommended

| Tool | Purpose |
|------|---------|
| PostgreSQL 15+ | Local database (or use Docker) |
| Redis 7+ | Local cache (or use Docker) |
| VS Code | IDE with Python and TypeScript extensions |

---

## Quick Start (Docker)

The fastest way to run the full stack:

```bash
# Clone the repository
git clone https://github.com/TamTunnel/Apache-TacticalMesh.git
cd Apache-TacticalMesh

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f controller
```

Access points:
- **Controller API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs
- **Web Console:** http://localhost:3000

Default credentials: `admin` / `admin123`

---

## Local Development Setup

### 1. Backend (Mesh Controller)

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env

# Edit .env to set your local database URL
# TM_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/tacticalmesh

# Start the development server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend (Web Console)

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be available at http://localhost:5173 with hot reload enabled.

### 3. Agent (Node Agent)

```bash
# Navigate to agent directory
cd agent

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize a configuration file
python -m agent.main --init-config --node-id test-node-001 --controller http://localhost:8000

# Run the agent
python -m agent.main --config config.yaml --log-level DEBUG
```

---

## Database Setup

### Using Docker (Recommended)

```bash
# Start only the database
docker-compose up -d db redis

# The database will be automatically initialized
```

### Local PostgreSQL

```bash
# Create database
createdb tacticalmesh

# Create user
psql -c "CREATE USER tacticalmesh WITH PASSWORD 'tacticalmesh';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE tacticalmesh TO tacticalmesh;"

# Tables are created automatically on first startup
```

---

## Running Tests

### Backend Tests

```bash
cd backend

# Install test dependencies (if not already installed)
pip install pytest pytest-asyncio httpx aiosqlite

# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ -v --cov=backend --cov-report=html
```

### Frontend Tests

```bash
cd frontend

# Run linting
npm run lint

# Build check
npm run build
```

---

## Code Style and Formatting

### Python (Backend & Agent)

We use the following tools:

```bash
# Format code with Black
black backend/ agent/

# Sort imports with isort
isort backend/ agent/

# Check style with flake8
flake8 backend/ agent/

# Type checking with mypy
mypy backend/ agent/
```

Configuration is in `pyproject.toml` (if present) or tool-specific config files.

### TypeScript (Frontend)

```bash
# Lint code
npm run lint

# Format with Prettier (if configured)
npx prettier --write src/
```

---

## Project Structure

```
Apache-TacticalMesh/
├── backend/                 # Mesh Controller (FastAPI)
│   ├── main.py             # Application entry point
│   ├── config.py           # Environment configuration
│   ├── database.py         # Database setup
│   ├── models.py           # SQLAlchemy models
│   ├── schemas.py          # Pydantic schemas
│   ├── auth.py             # Authentication & RBAC
│   ├── routers/            # API route handlers
│   │   ├── auth.py         # /api/v1/auth/*
│   │   ├── nodes.py        # /api/v1/nodes/*
│   │   ├── commands.py     # /api/v1/commands/*
│   │   └── config.py       # /api/v1/config/*
│   └── tests/              # Backend tests
├── agent/                   # Node Agent (Python)
│   ├── main.py             # Agent entry point
│   ├── config.py           # YAML configuration
│   ├── client.py           # HTTP client
│   └── actions.py          # Command handlers
├── frontend/                # Web Console (React/TS)
│   ├── src/
│   │   ├── App.tsx         # Main application
│   │   ├── api/client.ts   # API client
│   │   ├── components/     # UI components
│   │   └── context/        # React contexts
│   └── package.json
├── openapi/                 # API specifications
│   └── controller-v1.yaml  # OpenAPI 3.0 spec
├── deploy/                  # Deployment configs
│   └── kubernetes/         # K8s manifests
├── docs/                    # Documentation
└── docker-compose.yaml      # Local development stack
```

---

## Working with the OpenAPI Spec

The OpenAPI specification in `openapi/controller-v1.yaml` is the source of truth for the API.

### Viewing the Spec

1. Start the controller: `uvicorn backend.main:app`
2. Open http://localhost:8000/docs (Swagger UI)
3. Or open http://localhost:8000/redoc (ReDoc)

### Regenerating Client Code

You can generate typed clients from the OpenAPI spec:

```bash
# Generate TypeScript client (example using openapi-generator)
npx @openapitools/openapi-generator-cli generate \
  -i openapi/controller-v1.yaml \
  -g typescript-axios \
  -o frontend/src/api/generated
```

---

## Common Development Tasks

### Adding a New API Endpoint

1. Define the Pydantic schemas in `backend/schemas.py`
2. Add the route in the appropriate `backend/routers/*.py` file
3. Update the OpenAPI spec in `openapi/controller-v1.yaml`
4. Add tests in `backend/tests/`

### Adding a New Agent Command

1. Create a new handler class in `agent/actions.py`
2. Register it in `create_default_registry()`
3. Update the `CommandType` enum in `backend/models.py`
4. Update the frontend command creation dialog

### Adding a New Frontend Component

1. Create the component in `frontend/src/components/`
2. Add routing in `frontend/src/App.tsx` if needed
3. Add API calls using the client in `frontend/src/api/client.ts`

---

## Environment Variables

### Backend (Controller)

| Variable | Default | Description |
|----------|---------|-------------|
| `TM_DATABASE_URL` | (required) | PostgreSQL connection URL |
| `TM_REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `TM_JWT_SECRET_KEY` | (required) | JWT signing secret |
| `TM_DEBUG` | `false` | Enable debug mode |
| `TM_LOG_LEVEL` | `INFO` | Logging level |

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `/api/v1` | Backend API URL |

---

## Getting Help

- **Documentation:** Check the `docs/` directory
- **Issues:** https://github.com/TamTunnel/Apache-TacticalMesh/issues
- **Discussions:** https://github.com/TamTunnel/Apache-TacticalMesh/discussions

---

## Contributing

Before contributing, please read:

1. **No proprietary code:** Do not submit code that is proprietary or export-controlled
2. **Code quality:** Follow the style guidelines above
3. **Tests:** Add tests for new functionality
4. **Documentation:** Update docs for user-facing changes

See `CONTRIBUTING.md` in the root directory for full guidelines.

---

*Licensed under Apache 2.0 — https://www.apache.org/licenses/LICENSE-2.0*
