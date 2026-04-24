"""End-to-end test script for the contract analysis pipeline with mocked LLM calls."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import json
import logging
import os

from agents.ingestion import IngestionResult
import agents.compliance as compliance_module
import agents.extraction as extraction_module
import agents.negotiation as negotiation_module
import agents.risk as risk_module
from workflows.contract_analysis import run_contract_analysis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

os.environ["OPENAI_API_KEY"] = "test-openai-key"


def mock_openai_response(content_str: str) -> MagicMock:
	"""Create a mock OpenAI response object matching chat.completions shape."""

	mock_response = MagicMock()
	mock_response.choices = [MagicMock()]
	mock_response.choices[0].message = MagicMock()
	mock_response.choices[0].message.content = content_str
	return mock_response


mock_extraction_response = json.dumps(
	[
		{
			"clause_type": "payment_terms",
			"clause_text": "Payment is due within 45 days of invoice.",
			"summary": "Payment terms allow delayed payment window.",
			"confidence": 0.95,
			"page_hint": 0.2,
		},
		{
			"clause_type": "liability_cap",
			"clause_text": "Vendor shall have unlimited liability for all claims.",
			"summary": "Liability is uncapped and highly risky.",
			"confidence": 0.90,
			"page_hint": 0.5,
		},
		{
			"clause_type": "termination_for_convenience",
			"clause_text": "Customer may terminate at sole discretion at any time.",
			"summary": "One-sided termination rights favor one party.",
			"confidence": 0.85,
			"page_hint": 0.8,
		},
	]
)

mock_risk_response = json.dumps(
	{
		"risk_factors": ["Unlimited liability exposure", "One-sided termination"],
		"recommendations": [
			"Cap liability to contract value",
			"Equalize termination rights",
		],
		"red_flags": ["Unlimited liability is a critical risk"],
		"executive_summary": "This contract presents HIGH risk due to unlimited liability.",
	}
)

mock_compliance_response = json.dumps(
	{
		"compliance_issues": ["Missing data breach notification clause"],
		"missing_requirements": ["data_protection", "privacy_obligations"],
		"compliant_items": ["governing_law present"],
		"compliance_recommendations": ["Add GDPR data protection clause"],
		"overall_compliance_summary": "Contract is PARTIALLY_COMPLIANT with GDPR.",
	}
)

mock_negotiation_response = json.dumps(
	{
		"original_issues": ["Unlimited liability is unacceptable"],
		"suggested_language": "Vendor liability shall not exceed the total contract value.",
		"key_changes": ["Added liability cap equal to contract value"],
		"negotiation_notes": "Push hard on this clause - it is a deal breaker",
		"fallback_position": "Cap at 2x contract value as minimum",
	}
)

mock_strategy_response = json.dumps(
	{
		"opening_strategy": "Start by addressing liability and termination clauses",
		"priority_clauses": ["liability_cap", "termination_for_convenience"],
		"concession_areas": ["payment_terms timeline"],
		"deal_breakers": ["unlimited liability must be capped"],
		"negotiation_timeline": "Allow 2 weeks for negotiation",
	}
)


@patch("workflows.contract_analysis._INGESTION_AGENT.process")
@patch("agents.negotiation.OpenAI")
@patch("agents.compliance.OpenAI")
@patch("agents.risk.OpenAI")
@patch("agents.extraction.OpenAI")
def test_full_pipeline(
	mock_extraction_openai: MagicMock,
	mock_risk_openai: MagicMock,
	mock_compliance_openai: MagicMock,
	mock_negotiation_openai: MagicMock,
	mock_ingestion_process: MagicMock,
) -> None:
	"""Run the complete contract analysis workflow with mocked OpenAI responses."""

	mock_extraction_client = mock_extraction_openai.return_value
	mock_extraction_client.chat.completions.create.return_value = mock_openai_response(
		mock_extraction_response
	)
	extraction_module.client = mock_extraction_client

	mock_risk_client = mock_risk_openai.return_value
	mock_risk_client.chat.completions.create.return_value = mock_openai_response(
		mock_risk_response
	)
	risk_module.client = mock_risk_client

	mock_compliance_client = mock_compliance_openai.return_value
	mock_compliance_client.chat.completions.create.return_value = mock_openai_response(
		mock_compliance_response
	)
	compliance_module.client = mock_compliance_client

	mock_negotiation_client = mock_negotiation_openai.return_value
	mock_negotiation_client.chat.completions.create.side_effect = [
		mock_openai_response(mock_negotiation_response),
		mock_openai_response(mock_negotiation_response),
		mock_openai_response(mock_negotiation_response),
		mock_openai_response(mock_strategy_response),
	]
	negotiation_module.client = mock_negotiation_client

	mock_ingestion_process.return_value = IngestionResult(
		file_path="../data/sample_contracts/sample_contract.txt",
		file_name="sample_contract.txt",
		file_type=".txt",
		raw_text=(
			"Payment is due within 45 days. "
			"Vendor shall have unlimited liability. "
			"Customer may terminate at sole discretion."
		),
		cleaned_text=(
			"Payment is due within 45 days.\n\n"
			"Vendor shall have unlimited liability.\n\n"
			"Customer may terminate at sole discretion."
		),
		chunks=[
			"Payment is due within 45 days.",
			"Vendor shall have unlimited liability.",
			"Customer may terminate at sole discretion.",
		],
		page_count=1,
		word_count=17,
		char_count=118,
		status="success",
		error_message=None,
	)

	result = run_contract_analysis(
		file_path="../data/sample_contracts/sample_contract.txt",
		contract_id="test-contract-001",
		user_id="test-user-001",
		negotiation_stance="balanced",
		frameworks=["GDPR", "GENERAL"],
	)

	print("\n=== Pipeline Result Summary ===")
	print(f"Current step: {result.get('current_step')}")
	print(f"Error: {result.get('error')}")

	ingestion = result.get("ingestion_result") or {}
	print("\n[Ingestion]")
	print(f"Status: {ingestion.get('status')}")
	print(f"Word count: {ingestion.get('word_count')}")
	print(f"Chunk count: {len(ingestion.get('chunks', []))}")

	extraction = result.get("extraction_result") or {}
	print("\n[Extraction]")
	print(f"Total clauses found: {extraction.get('total_clauses_found')}")
	print(f"Clause types: {extraction.get('clause_types_found')}")

	risk = result.get("risk_result") or {}
	top_risks = risk.get("top_risk_clauses", [])
	top_risk_types = [item.get("clause_type") for item in top_risks]
	print("\n[Risk]")
	print(f"Overall score: {risk.get('overall_risk_score')}")
	print(f"Risk level: {risk.get('risk_level')}")
	print(f"Top risk clauses: {top_risk_types}")

	compliance = result.get("compliance_result") or {}
	print("\n[Compliance]")
	print(f"Overall score: {compliance.get('overall_compliance_score')}")
	print(f"Compliance status: {compliance.get('compliance_status')}")

	negotiation = result.get("negotiation_result") or {}
	print("\n[Negotiation]")
	print(f"Clauses reviewed: {negotiation.get('clauses_reviewed')}")
	print(f"Suggestions count: {negotiation.get('clauses_with_suggestions')}")

	assert result.get("ingestion_result") is not None, "ingestion_result should not be None"
	print("\n✅ Pipeline test passed!")


if __name__ == "__main__":
	test_full_pipeline()
