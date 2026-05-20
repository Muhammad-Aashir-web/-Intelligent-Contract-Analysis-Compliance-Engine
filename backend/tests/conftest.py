"""
Pytest configuration and shared fixtures for contract analysis agent tests.

This module provides:
- test environment setup (environment variables, settings overrides)
- realistic sample contract text and clauses
- mock objects for external services (OpenAI, database, vector stores)
- database session fixtures for testing agent operations
"""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


# ============================================================================
# Environment and Settings Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def test_env(monkeypatch):
	"""
	Automatically set test environment variables for every test.
	Ensures no real API calls are made and test isolation is maintained.
	"""
	monkeypatch.setenv("OPENAI_API_KEY", "test-api-key-12345")
	monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/contract_test")
	monkeypatch.setenv("PINECONE_API_KEY", "test-pinecone-key")
	monkeypatch.setenv("WEAVIATE_URL", "http://localhost:8080")
	monkeypatch.setenv("PYTHONUNBUFFERED", "1")


@pytest.fixture
def test_settings():
	"""
	Override application settings for testing.
	Returns a mock settings object with test-safe values.
	"""
	return SimpleNamespace(
		debug=True,
		testing=True,
		api_key="test-api-key",
		database_url="postgresql://test:test@localhost/contract_test",
		pinecone_index="test-index",
		weaviate_url="http://localhost:8080",
		max_chunk_size=1000,
		chunk_overlap=200,
		openai_model="gpt-4o-mini",
		log_level="DEBUG",
	)


# ============================================================================
# Sample Contract and Clause Fixtures
# ============================================================================


@pytest.fixture
def sample_contract_text():
	"""
	Realistic 200+ word NDA agreement snippet suitable for testing extraction and analysis.
	Contains multiple clause types: confidentiality, term, termination, governing law, etc.
	"""
	return (
		"MUTUAL NON-DISCLOSURE AGREEMENT\n\n"
		"This Mutual Non-Disclosure Agreement (\"Agreement\") is entered into effective as of "
		"January 1, 2024, between Company A, Inc., a Delaware corporation (\"Discloser\"), and "
		"Company B LLC, a California limited liability company (\"Recipient\").\n\n"
		"1. CONFIDENTIAL INFORMATION\n"
		"Confidential Information means any and all non-public information disclosed by one party "
		"to the other, including but not limited to: business plans, financial information, trade "
		"secrets, customer lists, technical data, software, algorithms, source code, and any other "
		"proprietary information marked as confidential or reasonably understood to be confidential.\n\n"
		"2. OBLIGATIONS\n"
		"Each party shall: (a) maintain strict confidentiality of all Confidential Information using "
		"reasonable security measures; (b) limit access to employees and contractors with a need to know; "
		"(c) use Confidential Information solely for the purposes of evaluating a potential business relationship; "
		"and (d) return or destroy all Confidential Information upon written request.\n\n"
		"3. TERM AND TERMINATION\n"
		"This Agreement shall commence on the Effective Date and continue for a period of three (3) years, "
		"unless earlier terminated by either party upon thirty (30) days written notice. "
		"Termination of this Agreement shall not relieve the parties of their obligations regarding "
		"information disclosed prior to termination.\n\n"
		"4. GOVERNING LAW\n"
		"This Agreement shall be governed by and construed in accordance with the laws of the State of "
		"Delaware, without regard to its conflict of laws principles. Any disputes arising under this "
		"Agreement shall be subject to binding arbitration administered by the American Arbitration Association.\n\n"
		"5. LIABILITY CAP\n"
		"IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY INDIRECT, INCIDENTAL, CONSEQUENTIAL, SPECIAL, "
		"OR PUNITIVE DAMAGES, INCLUDING LOST PROFITS, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.\n"
	)


@pytest.fixture
def sample_clause():
	"""
	A single realistic clause dictionary with all key fields for testing extraction and analysis.
	Scope: function (unique instance per test to allow mutation without cross-test pollution).
	"""
	return {
		"clause_type": "nda_terms",
		"clause_text": (
			"Each party shall maintain strict confidentiality of all Confidential Information "
			"using reasonable security measures and limit access to employees with a need to know."
		),
		"summary": "Mutual confidentiality obligation with reasonable security measures.",
		"confidence": 0.95,
		"page_hint": 0.15,
		"risk_score": 0.25,
	}


@pytest.fixture
def sample_clauses():
	"""
	Multiple clause dictionaries representing a diverse set of contract provisions.
	Useful for testing agents that process clause lists.
	"""
	return [
		{
			"clause_type": "nda_terms",
			"clause_text": "Each party shall maintain confidentiality of disclosed information.",
			"summary": "Mutual confidentiality obligation.",
			"confidence": 0.95,
			"page_hint": 0.1,
			"risk_score": 0.2,
		},
		{
			"clause_type": "liability_cap",
			"clause_text": (
				"IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY INDIRECT, INCIDENTAL, "
				"OR CONSEQUENTIAL DAMAGES."
			),
			"summary": "Liability limited to direct damages only.",
			"confidence": 0.92,
			"page_hint": 0.8,
			"risk_score": 0.5,
		},
		{
			"clause_type": "termination_for_cause",
			"clause_text": "Either party may terminate this Agreement immediately upon material breach.",
			"summary": "Termination right for material breach.",
			"confidence": 0.88,
			"page_hint": 0.5,
			"risk_score": 0.35,
		},
		{
			"clause_type": "governing_law",
			"clause_text": "This Agreement shall be governed by the laws of Delaware.",
			"summary": "Delaware law applies.",
			"confidence": 0.99,
			"page_hint": 0.9,
			"risk_score": 0.1,
		},
		{
			"clause_type": "data_protection",
			"clause_text": (
				"The parties shall comply with all applicable data protection regulations "
				"including GDPR and CCPA."
			),
			"summary": "Compliance with GDPR and CCPA required.",
			"confidence": 0.91,
			"page_hint": 0.6,
			"risk_score": 0.4,
		},
	]


# ============================================================================
# Mock OpenAI Fixtures
# ============================================================================


@pytest.fixture
def mock_openai_response():
	"""
	Mock OpenAI ChatCompletion response object.
	Returns a realistic response structure that agents expect.
	"""
	response = SimpleNamespace(
		choices=[
			SimpleNamespace(
				message=SimpleNamespace(
					content='[{"clause_type": "nda_terms", "clause_text": "test clause", "summary": "test", "confidence": 0.9, "page_hint": 0.1}]'
				)
			)
		],
		usage=SimpleNamespace(
			prompt_tokens=150,
			completion_tokens=100,
			total_tokens=250,
		),
		model="gpt-4o-mini",
		created=1704067200,
	)
	return response


@pytest.fixture
def mock_openai_error_response():
	"""Mock an OpenAI error response for testing error handling."""
	return Exception("OpenAI API Error: Rate limit exceeded")


@pytest.fixture
def mock_openai_client(mocker):
	"""
	Mock the OpenAI client for all tests.
	Prevents real API calls and allows simulation of various response scenarios.
	Scope: function (recreated per test to isolate state).
	"""
	mock_client = MagicMock()
	mock_client.chat = MagicMock()
	mock_client.chat.completions = MagicMock()
	mocker.patch("agents.extraction.client", mock_client)
	mocker.patch("agents.risk.client", mock_client)
	mocker.patch("agents.compliance.client", mock_client)
	mocker.patch("agents.negotiation.client", mock_client)
	return mock_client


# ============================================================================
# Mock Database Fixtures
# ============================================================================


@pytest.fixture
def mock_db_session():
	"""
	Mock SQLAlchemy database session for testing database operations.
	Simulates execute, commit, rollback, and other session methods.
	Scope: function (fresh mock per test to prevent state leakage).
	"""
	session = MagicMock()
	session.execute = MagicMock(return_value=MagicMock())
	session.commit = MagicMock(return_value=None)
	session.rollback = MagicMock(return_value=None)
	session.query = MagicMock(return_value=MagicMock())
	session.add = MagicMock(return_value=None)
	session.add_all = MagicMock(return_value=None)
	session.delete = MagicMock(return_value=None)
	session.close = MagicMock(return_value=None)
	return session


@pytest.fixture
def mock_get_db(mocker, mock_db_session):
	"""
	Mock the get_db generator function from database.py.
	Yields a mock session instead of creating a real database connection.
	"""

	def fake_get_db():
		yield mock_db_session

	mock_func = mocker.patch("agents.audit.get_db", fake_get_db)
	return mock_func


# ============================================================================
# Mock Vector Store Fixtures
# ============================================================================


@pytest.fixture
def mock_pinecone():
	"""
	Mock Pinecone vector store client for testing RAG and similarity search.
	"""
	mock = MagicMock()
	mock.Index = MagicMock(return_value=MagicMock())
	mock.Index.return_value.query = MagicMock(
		return_value={
			"matches": [
				{"id": "vec1", "score": 0.95, "metadata": {"text": "relevant clause"}},
				{"id": "vec2", "score": 0.87, "metadata": {"text": "similar clause"}},
			]
		}
	)
	mock.Index.return_value.upsert = MagicMock(return_value={"upserted_count": 5})
	return mock


@pytest.fixture
def mock_weaviate():
	"""
	Mock Weaviate vector store client for testing semantic search and RAG.
	"""
	mock = MagicMock()
	mock.Client = MagicMock(return_value=MagicMock())
	mock.Client.return_value.query = MagicMock(
		return_value={
			"data": {
				"Get": {
					"ContractClause": [
						{"clause_type": "nda_terms", "text": "confidentiality clause"},
						{"clause_type": "liability_cap", "text": "liability limitation clause"},
					]
				}
			}
		}
	)
	return mock


# ============================================================================
# Audit and Logging Fixtures
# ============================================================================


@pytest.fixture
def mock_audit_logger(mocker):
	"""
	Mock logger for audit trail operations.
	Allows verification that audit events are logged without actual I/O.
	"""
	logger = MagicMock()
	logger.info = MagicMock()
	logger.warning = MagicMock()
	logger.error = MagicMock()
	mocker.patch("agents.audit.logging.getLogger", return_value=logger)
	return logger


# ============================================================================
# Utility Fixtures
# ============================================================================


@pytest.fixture
def contract_id_fixture():
	"""Standard contract ID for use across tests."""
	return "contract-test-12345"


@pytest.fixture
def user_id_fixture():
	"""Standard user ID for audit trail testing."""
	return "user-test-6789"


@pytest.fixture
def sample_extraction_result():
	"""
	Sample extraction result object for testing downstream agents.
	Simulates the output of DocumentIngestionAgent.
	"""
	return SimpleNamespace(
		file_path="/tmp/contract.pdf",
		file_name="contract.pdf",
		file_type=".pdf",
		raw_text="Raw contract text here...",
		cleaned_text="Cleaned contract text here...",
		chunks=["chunk1", "chunk2", "chunk3"],
		page_count=5,
		word_count=1200,
		char_count=7500,
		status="success",
		error_message=None,
	)


# ============================================================================
# Pytest Configuration and Hooks
# ============================================================================


def pytest_configure(config):
	"""Global pytest configuration."""
	config.addinivalue_line(
		"markers",
		"asyncio: mark test as requiring asyncio support (async def test functions)",
	)
