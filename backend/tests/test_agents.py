"""
Comprehensive pytest tests for all six agents in the contract analysis system.

Tests cover:
- DocumentIngestionAgent: file extraction, validation, chunking
- ClauseExtractionAgent: LLM-based clause identification
- RiskAssessmentAgent: rule-based and LLM-assisted risk scoring
- ComplianceAgent: framework-based compliance checking
- NegotiationAgent: clause rewriting and strategy generation
- AuditTrailAgent: event logging and audit trail retrieval

All fixtures and configuration are in conftest.py
"""

import json
from types import SimpleNamespace

import pytest

# Agent imports must not include the 'backend.' prefix per project rules
from agents.ingestion import DocumentIngestionAgent
from agents.extraction import ClauseExtractionAgent
from agents.risk import RiskAssessmentAgent
from agents.compliance import ComplianceAgent
from agents.negotiation import NegotiationAgent
from agents.audit import AuditTrailAgent


# ============================================================================
# DocumentIngestionAgent Tests
# ============================================================================


@pytest.mark.asyncio
async def test_ingestion_success(tmp_path, mocker, sample_contract_text):
	"""Test successful document ingestion with valid PDF file."""
	# Create a dummy file and mock extraction to avoid heavy I/O
	f = tmp_path / "contract.pdf"
	f.write_text("PDF_PLACEHOLDER")

	mocker.patch("agents.ingestion.extract_text", return_value=sample_contract_text)

	agent = DocumentIngestionAgent()
	result = agent.process(str(f))

	assert result.status == "success"
	assert "Confidential" in result.cleaned_text or "confidential" in result.cleaned_text.lower()
	assert result.chunks and isinstance(result.chunks, list)
	assert result.word_count > 0
	assert result.char_count > 0


@pytest.mark.asyncio
async def test_ingestion_file_not_found(tmp_path):
	"""Test ingestion with non-existent file returns failed status."""
	agent = DocumentIngestionAgent()
	# nonexistent file -> should return failed result with FileNotFoundError text
	result = agent.process(str(tmp_path / "no-file.pdf"))
	assert result.status == "failed"
	assert "not found" in (result.error_message or "").lower()


@pytest.mark.asyncio
async def test_ingestion_unsupported_extension(tmp_path, mocker):
	"""Test ingestion with unsupported file type returns error."""
	f = tmp_path / "contract.txt"
	f.write_text("plain text")
	mocker.patch("agents.ingestion.extract_text", return_value="text")
	agent = DocumentIngestionAgent()
	res = agent.process(str(f))
	assert res.status == "failed"
	assert "unsupported file type" in (res.error_message or "").lower()


# ============================================================================
# ClauseExtractionAgent Tests
# ============================================================================


@pytest.mark.asyncio
async def test_clause_extraction_success(mocker, sample_contract_text):
	"""Test successful clause extraction with valid contract text."""
	# Mock the OpenAI client response
	fake_content = json.dumps([
		{
			"clause_type": "nda_terms",
			"clause_text": "Each party shall maintain confidentiality of disclosed information.",
			"summary": "Mutual confidentiality obligation.",
			"confidence": 0.9,
			"page_hint": 0.05,
		}
	])

	fake_response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=fake_content))])
	mocker.patch("agents.extraction.client.chat.completions.create", return_value=fake_response)

	agent = ClauseExtractionAgent()
	result = agent.process(sample_contract_text, contract_id="c1")
	assert result.status == "success"
	assert result.total_clauses_found == 1
	assert "nda_terms" in result.clause_types_found


@pytest.mark.asyncio
async def test_clause_extraction_empty_input():
	"""Test clause extraction with empty input returns error."""
	agent = ClauseExtractionAgent()
	res = agent.process("   ", contract_id="c-empty")
	assert res.status == "failed"
	assert "empty" in (res.error_message or "").lower()


@pytest.mark.asyncio
async def test_clause_extraction_llm_failure(mocker, sample_contract_text):
	"""Test clause extraction handles LLM API failures gracefully."""
	mocker.patch("agents.extraction.client.chat.completions.create", side_effect=Exception("API down"))
	agent = ClauseExtractionAgent()
	res = agent.process(sample_contract_text, contract_id="c-fail")
	assert res.status == "failed"
	assert "api down" in (res.error_message or "").lower()


# ============================================================================
# RiskAssessmentAgent Tests
# ============================================================================


@pytest.mark.asyncio
async def test_risk_assessment_success(mocker, sample_clauses):
	"""Test successful risk assessment with valid clause data."""
	# LLM returns a structured JSON object
	llm_out = json.dumps({
		"risk_factors": ["high indemnity exposure"],
		"recommendations": ["Limit liability to $1M"],
		"red_flags": ["unlimited liability"],
		"executive_summary": "Overall medium risk"
	})
	fake_resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=llm_out))])
	mocker.patch("agents.risk.client.chat.completions.create", return_value=fake_resp)

	agent = RiskAssessmentAgent()
	res = agent.process(sample_clauses, contract_id="r1")
	assert res.status == "success"
	assert isinstance(res.overall_risk_score, float)
	assert res.recommendations and "Limit liability" in res.recommendations[0]


@pytest.mark.asyncio
async def test_risk_assessment_no_clauses():
	"""Test risk assessment with empty clause list returns error."""
	agent = RiskAssessmentAgent()
	res = agent.process([], contract_id="r-empty")
	assert res.status == "failed"
	assert "no clauses" in (res.error_message or "").lower()


@pytest.mark.asyncio
async def test_risk_assessment_llm_failure(mocker, sample_clauses):
	"""Test risk assessment handles LLM failures gracefully."""
	mocker.patch("agents.risk.client.chat.completions.create", side_effect=Exception("LLM error"))
	agent = RiskAssessmentAgent()
	res = agent.process(sample_clauses, contract_id="r-llm-fail")
	assert res.status == "failed"
	assert "llm error" in (res.error_message or "").lower()


# ============================================================================
# ComplianceAgent Tests
# ============================================================================


@pytest.mark.asyncio
async def test_compliance_success(mocker, sample_clauses):
	"""Test successful compliance check with GDPR framework."""
	llm_out = json.dumps({
		"compliance_issues": ["missing data processing agreement"],
		"missing_requirements": ["data_processing_agreement"],
		"compliant_items": ["governing_law"],
		"compliance_recommendations": ["Add DPA language"],
		"overall_compliance_summary": "Partially compliant with GDPR"
	})
	fake_resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=llm_out))])
	mocker.patch("agents.compliance.client.chat.completions.create", return_value=fake_resp)

	agent = ComplianceAgent()
	res = agent.process(sample_clauses, contract_id="comp1", frameworks=["GDPR"])
	assert res.status == "success"
	assert "data_processing_agreement" in res.missing_requirements


@pytest.mark.asyncio
async def test_compliance_invalid_framework():
	"""Test compliance check with empty framework list returns error."""
	agent = ComplianceAgent()
	res = agent.process([], contract_id="comp-empty", frameworks=[])
	assert res.status == "failed"
	assert "no valid compliance frameworks" in (res.error_message or "").lower()


@pytest.mark.asyncio
async def test_compliance_llm_failure(mocker, sample_clauses):
	"""Test compliance check handles service errors gracefully."""
	mocker.patch("agents.compliance.client.chat.completions.create", side_effect=Exception("service error"))
	agent = ComplianceAgent()
	res = agent.process(sample_clauses, contract_id="comp-llm-fail", frameworks=["GENERAL"])
	assert res.status == "failed"
	assert "service error" in (res.error_message or "").lower()


# ============================================================================
# NegotiationAgent Tests
# ============================================================================


@pytest.mark.asyncio
async def test_negotiation_success(mocker):
	"""Test successful negotiation strategy generation with buyer-friendly stance."""
	clauses = [
		{
			"clause_type": "liability_cap",
			"clause_text": "Supplier is liable for unlimited damages.",
			"summary": "Unlimited supplier liability.",
			"confidence": 0.9,
			"page_hint": 0.2,
			"risk_score": 0.7,
		}
	]

	suggestion_json = json.dumps({
		"original_issues": ["unlimited liability"],
		"suggested_language": "Liability limited to $100,000 annual aggregate",
		"key_changes": ["cap damages"],
		"negotiation_notes": "Push to cap liability at a reasonable level",
		"fallback_position": "Cap at $250,000 annual aggregate",
	})

	strategy_json = json.dumps({
		"opening_strategy": "Start with a cap at $100,000",
		"priority_clauses": ["liability_cap"],
		"concession_areas": [],
		"deal_breakers": ["unlimited liability"],
		"negotiation_timeline": "Two rounds over two weeks"
	})

	resp1 = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=suggestion_json))])
	resp2 = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=strategy_json))])
	# First call returns suggestion, second returns strategy
	mocker.patch("agents.negotiation.client.chat.completions.create", side_effect=[resp1, resp2])

	agent = NegotiationAgent()
	res = agent.process(clauses, contract_id="neg1", negotiation_stance="buyer_friendly")
	assert res.status == "success"
	assert res.clauses_with_suggestions == 1
	assert "Liability limited" in res.clause_suggestions[0].get("suggested_language", "")


@pytest.mark.asyncio
async def test_negotiation_invalid_stance():
	"""Test negotiation with invalid stance returns error."""
	agent = NegotiationAgent()
	res = agent.process([], contract_id="neg-empty", negotiation_stance="invalid_stance")
	assert res.status == "failed"
	assert "invalid negotiation_stance" in (res.error_message or "").lower()


@pytest.mark.asyncio
async def test_negotiation_llm_failure(mocker):
	"""Test negotiation handles LLM failures gracefully."""
	clauses = [
		{"clause_type": "liability_cap", "clause_text": "...", "risk_score": 0.8}
	]
	mocker.patch("agents.negotiation.client.chat.completions.create", side_effect=Exception("LLM fail"))
	agent = NegotiationAgent()
	res = agent.process(clauses, contract_id="neg-llm-fail", negotiation_stance="balanced")
	assert res.status == "failed"
	assert "llm fail" in (res.error_message or "").lower()


# ============================================================================
# AuditTrailAgent Tests
# ============================================================================


@pytest.mark.asyncio
async def test_audit_logging_and_summary(mocker, mock_get_db):
	"""Test audit logging and summary generation."""
	agent = AuditTrailAgent()
	e1 = agent.log_agent_start("Ingestion", contract_id="audit1")
	e2 = agent.log_agent_complete("Ingestion", contract_id="audit1", result_summary={"chunks": 3}, duration_seconds=0.5)
	trail = agent.get_contract_audit_trail("audit1")
	assert any(t.contract_id == "audit1" for t in trail)
	summary = agent.get_audit_summary("audit1")
	assert summary["total_events"] >= 2
	assert "Ingestion" in summary["agents_run"]


@pytest.mark.asyncio
async def test_audit_db_failure_does_not_raise(mocker):
	"""Test that DB failures do not raise exceptions (best-effort logging)."""

	def bad_get_db():
		raise Exception("DB down")

	mocker.patch("agents.audit.get_db", bad_get_db)
	agent = AuditTrailAgent()
	e = agent.log_agent_error("Extraction", contract_id="audit2", error_message="boom")
	# In-memory log should still contain the event
	entries = agent.get_contract_audit_trail("audit2")
	assert any(x.event_type.endswith("_FAILED") for x in entries)


@pytest.mark.asyncio
async def test_audit_event_logging_with_user(mock_get_db):
	"""Test audit event logging with user context."""
	agent = AuditTrailAgent()
	event = agent.log_event(
		event_type="ANALYSIS_STARTED",
		contract_id="audit3",
		user_id="user123",
		agent_name="MultiAgent",
		status="started",
		details={"version": "1.0"},
		duration_seconds=None,
	)
	assert event.user_id == "user123"
	assert event.event_type == "ANALYSIS_STARTED"
	assert event.status == "started"
	assert event.details["version"] == "1.0"

