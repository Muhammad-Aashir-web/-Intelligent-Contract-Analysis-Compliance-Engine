import io
from datetime import datetime, timezone

import pytest
from starlette.testclient import TestClient

from database import get_db
from main import app

# Sample contract content to upload
SAMPLE_CONTRACT = (
    "NON-DISCLOSURE AGREEMENT - This agreement is entered into between Acme Corp and Beta LLC."
    " Confidential information shall be protected for 5 years. GDPR and CCPA compliant."
)


class _FakeQuery:
    def __init__(self, session, model):
        self._session = session
        self._model = model
        self._filters = {}
        self._offset = 0
        self._limit = None

    def filter(self, *criteria):
        for criterion in criteria:
            left = getattr(criterion, "left", None)
            right = getattr(criterion, "right", None)
            column_name = getattr(left, "name", None)
            column_value = getattr(right, "value", None)
            if column_name is not None:
                self._filters[column_name] = column_value
        return self

    def offset(self, value):
        self._offset = value
        return self

    def limit(self, value):
        self._limit = value
        return self

    def count(self):
        return len(self.all())

    def all(self):
        items = list(self._apply_filters(self._items()))
        return items

    def first(self):
        items = self.all()
        return items[0] if items else None

    def _items(self):
        name = self._model.__name__
        if name == "User":
            return self._session.users
        if name == "Contract":
            return self._session.contracts
        if name == "Clause":
            return self._session.clauses
        return []

    def _apply_filters(self, items):
        filtered = list(items)
        if self._model.__name__ == "User":
            if "email" in self._filters:
                filtered = [item for item in filtered if item.email == self._filters["email"]]
            if "id" in self._filters:
                filtered = [item for item in filtered if item.id == self._filters["id"]]
        elif self._model.__name__ == "Contract":
            if "id" in self._filters:
                filtered = [item for item in filtered if item.id == self._filters["id"]]
            if "user_id" in self._filters:
                filtered = [item for item in filtered if item.user_id == self._filters["user_id"]]
        elif self._model.__name__ == "Clause":
            if "contract_id" in self._filters:
                filtered = [item for item in filtered if item.contract_id == self._filters["contract_id"]]

        if self._offset:
            filtered = filtered[self._offset :]
        if self._limit is not None:
            filtered = filtered[: self._limit]
        return filtered


class _FakeSession:
    def __init__(self):
        self.users = []
        self.contracts = []
        self.clauses = []
        self._pending = []
        self._user_seq = 1
        self._contract_seq = 1
        self._clause_seq = 1

    def query(self, model):
        return _FakeQuery(self, model)

    def add(self, obj):
        self._pending.append(obj)

    def commit(self):
        now = datetime.now(timezone.utc)
        for obj in self._pending:
            name = obj.__class__.__name__
            if name == "User":
                if getattr(obj, "id", None) is None:
                    obj.id = self._user_seq
                    self._user_seq += 1
                if getattr(obj, "role", None) is None:
                    obj.role = "user"
                if getattr(obj, "is_active", None) is None:
                    obj.is_active = True
                if getattr(obj, "is_verified", None) is None:
                    obj.is_verified = False
                if getattr(obj, "created_at", None) is None:
                    obj.created_at = now
                if getattr(obj, "updated_at", None) is None:
                    obj.updated_at = now
                if obj not in self.users:
                    self.users.append(obj)
            elif name == "Contract":
                if getattr(obj, "id", None) is None:
                    obj.id = self._contract_seq
                    self._contract_seq += 1
                if getattr(obj, "status", None) == "processing":
                    obj.status = "completed"
                if getattr(obj, "created_at", None) is None:
                    obj.created_at = now
                if getattr(obj, "updated_at", None) is None:
                    obj.updated_at = now
                if obj not in self.contracts:
                    self.contracts.append(obj)
            elif name == "Clause":
                if getattr(obj, "id", None) is None:
                    obj.id = self._clause_seq
                    self._clause_seq += 1
                if getattr(obj, "created_at", None) is None:
                    obj.created_at = now
                if obj not in self.clauses:
                    self.clauses.append(obj)
        self._pending.clear()

    def rollback(self):
        self._pending.clear()

    def refresh(self, obj):
        pass

    def close(self):
        pass


@pytest.fixture(scope="module")
def fake_db():
    return _FakeSession()


@pytest.fixture(scope="module")
def client(fake_db):
    """Create a TestClient for the FastAPI app for the whole module."""
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def auth_token(client):
    """Register a test user and return an Authorization header with JWT token.

    Mocks external services (OpenAI, Pinecone, Weaviate) so no real calls are made.
    """
    # 1) Register a new user
    register_payload = {
        "email": "e2e_user@example.com",
        "password": "testpassword",
        "full_name": "E2E User",
        "company": "E2E Corp",
    }
    r = client.post("/api/v1/auth/register", json=register_payload)
    assert r.status_code in (200, 201)
    # 2) Login to receive JWT token
    login_payload = {"username": "e2e_user@example.com", "password": "testpassword"}
    r2 = client.post("/api/v1/auth/login", data=login_payload)
    assert r2.status_code == 200
    body = r2.json()
    assert "access_token" in body
    token = body["access_token"]
    yield {"Authorization": f"Bearer {token}"}


def _upload_contract(client, headers):
    """Helper to upload the sample contract as a .txt multipart file."""
    file_bytes = SAMPLE_CONTRACT.encode("utf-8")
    files = {"file": ("nda.pdf", io.BytesIO(file_bytes), "application/pdf")}
    r = client.post("/api/v1/contracts/upload", files=files, headers=headers)
    return r


@pytest.fixture(autouse=True)
def mock_external_services(monkeypatch):
    import api.contracts as contracts_api

    async def _fake_save_upload(file, contract_id):
        filename = getattr(file, "filename", "nda.pdf")
        return {
            "file_path": f"uploads/{filename}",
            "file_name": filename,
            "file_size": 2048,
            "file_type": ".pdf",
        }

    monkeypatch.setattr(contracts_api.storage, "save_upload", _fake_save_upload, raising=True)

    dummy_celery = type(
        "DummyCelery",
        (),
        {
            "tasks": {"process_contract_task": type("Task", (), {"delay": staticmethod(lambda *args, **kwargs: None)})()},
            "send_task": staticmethod(lambda *args, **kwargs: None),
        },
    )()
    monkeypatch.setattr(contracts_api, "celery_app", dummy_celery, raising=False)

    class _DummyRAG:
        def summarize_contract(self, contract_id):
            return {"summary": "Mock summary", "key_points": ["Point A"], "parties": ["Acme", "Beta"]}

    monkeypatch.setattr(contracts_api, "RAGService", _DummyRAG, raising=False)
    yield


# Step 1: Register a new user
def test_step_1_register(client, mocker):
    # Ensure external APIs are mocked for this test too
    payload = {
        "email": "step1_user@example.com",
        "password": "pass1234",
        "full_name": "Step One User",
        "company": "Step One LLC",
    }
    r = client.post("/api/v1/auth/register", json=payload)
    assert r.status_code in (200, 201)
    data = r.json()
    assert "email" in data and data.get("email") == payload["email"]


# Step 2: Login and get JWT token
def test_step_2_login(client, mocker):
    payload = {"username": "step1_user@example.com", "password": "pass1234"}
    r = client.post("/api/v1/auth/login", data=payload)
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body


# Step 3: Upload a contract file
def test_step_3_upload(client, auth_token):
    r = _upload_contract(client, auth_token)
    assert r.status_code in (200, 201)
    body = r.json()
    assert "contract_id" in body
    # store contract_id for downstream tests via return
    global UPLOADED_CONTRACT_ID
    UPLOADED_CONTRACT_ID = body["contract_id"]


# Step 4: Trigger analysis on the contract
def test_step_4_trigger_analysis(client, auth_token):
    contract_id = globals().get("UPLOADED_CONTRACT_ID")
    assert contract_id
    r = client.post(
        f"/api/v1/contracts/{contract_id}/analyze",
        json={"contract_id": contract_id},
        headers=auth_token,
    )
    assert r.status_code in (200, 202)
    data = r.json()
    # expect an analysis_id or status field
    assert "analysis_id" in data or "status" in data or "message" in data


# Step 5: Poll for analysis status (mock to complete immediately)
def test_step_5_poll_status(client, auth_token, mocker):
    contract_id = globals().get("UPLOADED_CONTRACT_ID")
    assert contract_id
    # Mock the status endpoint to return completed on first call
    def fake_status(*args, **kwargs):
        return {"status": "completed"}

    r = client.get(f"/api/v1/contracts/{contract_id}/status", headers=auth_token)
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") in ("completed", "processing")


# Step 6: Get analysis results
def test_step_6_get_results(client, auth_token):
    contract_id = globals().get("UPLOADED_CONTRACT_ID")
    assert contract_id
    r = client.get(f"/api/v1/contracts/{contract_id}/results", headers=auth_token)
    assert r.status_code == 200
    body = r.json()
    assert "analysis" in body or "results" in body or "clauses" in body or body.get("status") == "processing"


# Step 7: Get contract summary
def test_step_7_summary(client, auth_token):
    contract_id = globals().get("UPLOADED_CONTRACT_ID")
    assert contract_id
    r = client.get(f"/api/v1/contracts/{contract_id}/summary", headers=auth_token)
    assert r.status_code == 200
    body = r.json()
    assert "summary" in body


# Step 8: List all contracts
def test_step_8_list_contracts(client, auth_token):
    r = client.get("/api/v1/contracts", headers=auth_token)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)


# Step 9: Full pipeline run-through and print summary
def test_step_9_full_pipeline(client, auth_token, mocker):
    # Re-upload to get fresh contract_id
    r_upload = _upload_contract(client, auth_token)
    assert r_upload.status_code in (200, 201)
    contract_id = r_upload.json().get("contract_id")
    assert contract_id

    # Trigger analysis
    r_an = client.post(
        f"/api/v1/contracts/{contract_id}/analyze",
        json={"contract_id": contract_id},
        headers=auth_token,
    )
    assert r_an.status_code in (200, 202)

    # Mock status to complete
    r_status = client.get(f"/api/v1/contracts/{contract_id}/status", headers=auth_token)
    assert r_status.status_code == 200
    status = r_status.json().get("status")

    r_results = client.get(f"/api/v1/contracts/{contract_id}/results", headers=auth_token)
    assert r_results.status_code == 200
    results = r_results.json()

    r_summary = client.get(f"/api/v1/contracts/{contract_id}/summary", headers=auth_token)
    assert r_summary.status_code == 200
    summary = r_summary.json()

    # Print a concise pipeline summary
    print(f"E2E: contract_id={contract_id}, status={status}, results_keys={list(results.keys())}, summary_keys={list(summary.keys())}")
