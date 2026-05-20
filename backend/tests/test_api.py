from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

from database import get_db
from main import app


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
        items = list(self._session._items_for_model(self._model))
        items = self._apply_filters(items)
        if self._offset:
            items = items[self._offset :]
        if self._limit is not None:
            items = items[: self._limit]
        return items

    def first(self):
        items = self.all()
        return items[0] if items else None

    def _apply_filters(self, items):
        if self._model.__name__ == "User":
            if "email" in self._filters:
                items = [item for item in items if item.email == self._filters["email"]]
            if "id" in self._filters:
                items = [item for item in items if item.id == self._filters["id"]]
        elif self._model.__name__ == "Contract":
            if "id" in self._filters:
                items = [item for item in items if item.id == self._filters["id"]]
            if "user_id" in self._filters:
                items = [item for item in items if item.user_id == self._filters["user_id"]]
            if "status" in self._filters:
                items = [item for item in items if item.status == self._filters["status"]]
        elif self._model.__name__ == "Clause":
            if "contract_id" in self._filters:
                items = [item for item in items if item.contract_id == self._filters["contract_id"]]
        return items


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
        if obj not in self._pending:
            self._pending.append(obj)

    def commit(self):
        for obj in self._pending:
            self._persist(obj)
        self._pending.clear()

    def rollback(self):
        self._pending.clear()

    def refresh(self, obj):
        self._persist(obj)

    def close(self):
        pass

    def _items_for_model(self, model):
        name = model.__name__
        if name == "User":
            return self.users
        if name == "Contract":
            return self.contracts
        if name == "Clause":
            return self.clauses
        return []

    def _persist(self, obj):
        now = datetime.now(timezone.utc)
        class_name = obj.__class__.__name__
        if class_name == "User":
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
        elif class_name == "Contract":
            if getattr(obj, "id", None) is None:
                obj.id = self._contract_seq
                self._contract_seq += 1
            if getattr(obj, "status", None) is None:
                obj.status = "uploaded"
            if getattr(obj, "created_at", None) is None:
                obj.created_at = now
            if getattr(obj, "updated_at", None) is None:
                obj.updated_at = now
            if obj not in self.contracts:
                self.contracts.append(obj)
        elif class_name == "Clause":
            if getattr(obj, "id", None) is None:
                obj.id = self._clause_seq
                self._clause_seq += 1
            if getattr(obj, "created_at", None) is None:
                obj.created_at = now
            if obj not in self.clauses:
                self.clauses.append(obj)


@pytest.fixture(scope="module")
def fake_db():
    return _FakeSession()


# Fixture: provide a TestClient for the FastAPI app
@pytest.fixture(scope="module")
def client(fake_db):
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


# Fixture: registers a test user and returns an auth header with JWT token
@pytest.fixture(scope="module")
def auth_header(client):
    # realistic test credentials
    user = {
        "email": "alice.smith@example.com",
        "password": "Str0ngP@ssw0rd!",
        "full_name": "Alice Smith",
        "company": "Smith Legal",
    }

    # ensure registration (idempotent if app handles duplicates)
    client.post("/api/v1/auth/register", json=user)

    # login and get token
    r = client.post(
        "/api/v1/auth/login",
        data={"username": user["email"], "password": user["password"]},
    )
    assert r.status_code in (200, 201)
    data = r.json()
    token = data.get("access_token") or data.get("token")
    assert token, "Login did not return a token"
    return {"Authorization": f"Bearer {token}"}


# Mock external services (OpenAI or similar) globally for tests
@pytest.fixture(autouse=True)
def mock_external_services(mocker):
    # If the application imports openai, ensure calls are mocked
    try:
        mocker.patch("openai.Completion.create", return_value={})
        mocker.patch("openai.ChatCompletion.create", return_value={})
    except Exception:
        pass
    # Mock any HTTP calls to external signing providers if used
    try:
        mocker.patch("httpx.AsyncClient.post", return_value=type("R", (), {"status_code": 200, "json": lambda: {}})())
    except Exception:
        pass
    try:
        async def _fake_save_upload(file, contract_id):
            filename = getattr(file, "filename", "test-contract.pdf")
            suffix = ".pdf" if filename.lower().endswith(".pdf") else ".docx"
            return {
                "file_path": f"uploads/{filename}",
                "file_name": filename,
                "file_size": 2048,
                "file_type": suffix,
            }

        mocker.patch(
            "api.contracts.storage.save_upload",
            side_effect=_fake_save_upload,
        )
        mocker.patch(
            "api.contracts.celery_app",
            SimpleNamespace(
                tasks={
                    "process_contract_task": SimpleNamespace(delay=lambda *args, **kwargs: None)
                }
            ),
        )
    except Exception:
        pass
    yield


"""
Health check tests
Ensure the service health endpoint responds with a simple status OK.
"""


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") in ("ok", "healthy", "OK")


def test_health_not_found_wrong_method(client):
    # Using POST on a GET-only health endpoint should return 405
    r = client.post("/health")
    assert r.status_code in (404, 405)


"""
Auth route tests
1. Register new user and receive success
2. Register with invalid payload returns 4xx
3. Login happy path and error path
4. Get /api/auth/me with and without token
"""


def test_register_success(client):
    payload = {
        "email": "bob.jones@example.com",
        "password": "An0ther$tr0ngPass",
        "full_name": "Bob Jones",
        "company": "Jones Advisory",
    }
    r = client.post("/api/v1/auth/register", json=payload)
    assert r.status_code in (200, 201)
    assert "email" in r.json()


def test_register_invalid(client):
    # missing password
    payload = {"email": "no.password@example.com", "full_name": "No Password", "company": "Acme"}
    r = client.post("/api/v1/auth/register", json=payload)
    assert r.status_code >= 400 and r.status_code < 500


def test_login_success(client):
    payload = {
        "email": "charlie.k@example.com",
        "password": "MyP@ssword123",
        "full_name": "Charlie K",
        "company": "K Consulting",
    }
    client.post("/api/v1/auth/register", json=payload)
    r = client.post(
        "/api/v1/auth/login",
        data={"username": payload["email"], "password": payload["password"]},
    )
    assert r.status_code in (200, 201)
    data = r.json()
    assert data.get("access_token") or data.get("token")


def test_login_bad_credentials(client):
    payload = {"email": "doesnotexist@example.com", "password": "wrongpass"}
    r = client.post("/api/v1/auth/login", data={"username": payload["email"], "password": payload["password"]})
    assert r.status_code >= 400 and r.status_code < 500


def test_get_me_requires_auth(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code in (401, 403, 404)


def test_get_me_with_token(client, auth_header):
    r = client.get("/api/v1/auth/me", headers=auth_header)
    assert r.status_code == 200
    data = r.json()
    assert "email" in data


"""
Contract routes tests
Test listing, creating, and retrieving contracts with and without auth.
"""


def test_get_contracts_unauthenticated(client):
    r = client.get("/api/v1/contracts")
    assert r.status_code == 200


def test_create_and_get_contract(client, auth_header):
    # create contract
    payload = {
        "file_name": "test-contract.pdf",
        "content": "This Agreement is between Acme Corp and Supplier...",
    }
    file_data = BytesIO(b"%PDF-1.4 test contract bytes")
    r = client.post(
        "/api/v1/contracts/upload",
        files={"file": (payload["file_name"], file_data, "application/pdf")},
        headers=auth_header,
    )
    assert r.status_code in (200, 201)
    created = r.json()
    contract_id = created.get("id") or created.get("contract_id")
    assert contract_id

    # get contract by id
    r2 = client.get(f"/api/v1/contracts/{contract_id}", headers=auth_header)
    assert r2.status_code == 200
    data = r2.json()
    assert data.get("file_name") == payload["file_name"]


def test_create_contract_invalid(client, auth_header):
    # missing required fields
    r = client.post("/api/v1/contracts/upload", headers=auth_header)
    assert r.status_code >= 400 and r.status_code < 500


def test_get_contract_not_found(client, auth_header):
    r = client.get("/api/v1/contracts/00000000-0000-0000-0000-000000000000", headers=auth_header)
    assert r.status_code in (404, 400, 422)


"""
Webhook route tests
Test the DocuSign webhook receiver for happy and error paths.
Use httpx AsyncClient to exercise async handling if present.
"""


def test_docusign_webhook_happy(mocker):
    # prepare realistic webhook payload
    payload = {
        "event_type": "envelope-completed",
        "data": {"envelopeId": "12345678-aaaa-bbbb-cccc-1234567890ab", "status": "completed"},
        "timestamp": "2026-05-20T12:00:00Z",
    }

    # mock any internal processing function that might be used
    mocker.patch("openai.ChatCompletion.create", return_value={})

    client = TestClient(app)
    r = client.post("/api/v1/webhooks/docusign", json=payload)
    assert r.status_code in (200, 202)


def test_docusign_webhook_bad_payload():
    # missing envelope id
    payload = {"event_type": "unknown"}
    client = TestClient(app)
    r = client.post("/api/v1/webhooks/docusign", json=payload)
    assert r.status_code >= 400 and r.status_code < 500
