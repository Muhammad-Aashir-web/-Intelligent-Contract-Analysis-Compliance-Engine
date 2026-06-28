# Intelligent Contract Analysis & Compliance Engine

AI-powered multi-agent platform that analyzes contracts end to end: it extracts clauses, scores risk, checks compliance, suggests negotiation edits, and records a full audit trail. The goal is to reduce manual review effort and surface issues earlier in the contract process.

## Key Features

- Upload and analyze contracts through a multi-step AI pipeline
- Extract structured clauses from raw contract text
- Score contract risk using rule-based metrics plus LLM analysis
- Check clauses against real compliance frameworks: GDPR, HIPAA, SOX, CCPA, and GENERAL
- Generate negotiation suggestions for high-risk clauses
- Track every stage with audit events and pipeline summaries
- View contracts, risk, compliance, and results in the React frontend

## Architecture

The backend uses LangGraph to orchestrate a six-agent workflow:

- Document ingestion
- Clause extraction
- Risk assessment
- Compliance analysis
- Negotiation support
- Audit logging

```text
ingest_document
		->
extract_clauses
		->
[risk_assessment | compliance | negotiation]
		(run in parallel via ThreadPoolExecutor)
		->
finalize_audit
```

The runtime services are:

- `postgres` for primary application data
- `redis` for task coordination and background jobs
- `n8n` for workflow automation integrations
- `backend` for the FastAPI application
- `celery_worker` for asynchronous contract processing
- `frontend` for the React dashboard

## Agent Pipeline

- Document ingestion validates file types, extracts text, cleans content, and chunks long documents.
- Clause extraction uses OpenAI to identify clause types and normalize them into structured output.
- Risk assessment scores clauses with deterministic heuristics and then asks the LLM for qualitative risk insights.
- Compliance checks clauses against framework-specific requirement sets and produces a score plus recommendations.
- Negotiation generates rewritten clause language and an overall negotiation strategy for high-risk clauses.
- Audit logging records start, completion, failure, and pipeline summary events for traceability.

## Tech Stack

**Backend**
- FastAPI
- Uvicorn
- SQLAlchemy
- Alembic
- Celery
- Redis
- OpenAI
- Anthropic
- LangGraph
- LangChain
- LlamaIndex
- Pinecone
- Weaviate
- PyMuPDF
- Unstructured
- python-docx
- pytesseract
- Pillow
- NumPy
- Pandas
- scikit-learn
- pytest
- pytest-asyncio

**Planned future risk-scoring upgrades, not yet active in the current pipeline**
- XGBoost
- SHAP

**Frontend**
- React 19
- React DOM 19
- Vite
- TypeScript 6
- Tailwind CSS 3
- React Query
- Axios
- React Router
- Recharts
- react-pdf
- lucide-react

## Setup

1. Clone the repository.
2. Copy `backend/.env.example` to `backend/.env`.
3. Fill in your own API keys and environment values.
4. From the `docker/` directory, start the stack with:
	 ```bash
	 docker compose up -d --build
	 ```
5. The compose stack brings up `postgres`, `redis`, `n8n`, `backend`, `celery_worker`, and `frontend`.
6. Open the frontend in your browser after the containers are running.

The backend and worker both read `backend/.env`, so make sure the file is configured before starting the stack.

## Important

> This is a portfolio demo, not a shared hosted service.  
> You must provide your own API keys for OpenAI, Pinecone, and Weaviate.  
> The project is designed to run with your own accounts and local Docker services.
>
> Using GPT-4o-mini, the per-contract analysis cost is typically low for short contracts, but it still depends on document length, chunk count, and how many clauses reach the risk, compliance, and negotiation stages.

## Testing

The backend test suite is 42/42 passing:
- 18 agent tests
- 14 API tests
- 9 end-to-end tests
- 1 pipeline smoke test in `test_pipeline.py`

Run tests from the backend directory:

```bash
pytest
```

## Project Structure

```text
backend/
	agents/
	api/
	models/
	services/
	workflows/
	tests/
frontend/
	src/
docker/
n8n_workflows/
docs/
data/
```

## Workflow Automation

The repository also includes n8n workflow definitions for contract analysis automation and DocuSign webhook handling. See `n8n_workflows/README.md` for import and setup details.

## License

Personal portfolio project
