"""Compliance agent for contract framework checks and AI-assisted analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = (
	"You are a regulatory compliance expert. Review these contract clauses "
	"against the specified regulatory frameworks. Return ONLY a JSON object with: "
	"compliance_issues (list of strings describing specific violations found), "
	"missing_requirements (list of strings for required items not found), "
	"compliant_items (list of strings for requirements that ARE met), "
	"compliance_recommendations (list of actionable fixes), "
	"overall_compliance_summary (2-3 sentence plain English summary)"
)

FRAMEWORK_REQUIREMENTS: dict[str, list[str]] = {
	"GDPR": [
		"data_protection",
		"privacy_obligations",
		"data_processing_agreement",
		"right_to_erasure",
		"data_breach_notification",
		"data_transfer_restrictions",
	],
	"HIPAA": [
		"data_protection",
		"audit_rights",
		"business_associate_agreement",
		"phi_handling",
		"security_requirements",
		"breach_notification",
	],
	"SOX": [
		"audit_rights",
		"financial_reporting",
		"internal_controls",
		"record_retention",
		"whistleblower_protection",
	],
	"CCPA": [
		"privacy_obligations",
		"data_protection",
		"opt_out_rights",
		"data_sale_disclosure",
		"consumer_rights",
	],
	"GENERAL": [
		"governing_law",
		"dispute_resolution",
		"termination_for_cause",
		"entire_agreement",
		"amendment_process",
	],
}


@dataclass
class ComplianceResult:
	"""Structured result for framework-based compliance assessment."""

	contract_id: str
	frameworks_checked: list[str] = field(default_factory=list)
	framework_results: dict = field(default_factory=dict)
	overall_compliance_score: float = 0.0
	compliance_status: str = "NON_COMPLIANT"
	compliance_issues: list[str] = field(default_factory=list)
	missing_requirements: list[str] = field(default_factory=list)
	compliant_items: list[str] = field(default_factory=list)
	compliance_recommendations: list[str] = field(default_factory=list)
	overall_compliance_summary: str = ""
	status: str = "failed"
	error_message: str | None = None
	processing_time_seconds: float = 0.0


class ComplianceAgent:
	"""Check contract clauses against regulatory frameworks and summarize gaps."""

	def __init__(self) -> None:
		"""Initialize compliance agent with logger and OpenAI model settings."""

		self.logger = logging.getLogger(__name__)
		self.model = "gpt-4o-mini"

	def process(
		self,
		clauses: list[dict],
		contract_id: str,
		frameworks: list[str] | None = None,
	) -> ComplianceResult:
		"""Assess clause-level compliance for selected frameworks.

		Args:
			clauses: Extracted clause dictionaries containing at least ``clause_type``.
			contract_id: Contract identifier.
			frameworks: Requested frameworks; defaults to ["GENERAL"].

		Returns:
			ComplianceResult with deterministic checks and LLM analysis outputs.
		"""

		start_time = time.time()
		self.logger.info("Starting compliance assessment for contract_id=%s", contract_id)

		try:
			if frameworks is None:
				frameworks = ["GENERAL"]

			normalized_frameworks = self._normalize_frameworks(frameworks)
			if not normalized_frameworks:
				raise ValueError("No valid compliance frameworks provided")

			clause_types_present = {
				str(clause.get("clause_type", "")).strip()
				for clause in clauses
				if str(clause.get("clause_type", "")).strip()
			}

			framework_results: dict[str, dict] = {}
			framework_scores: list[float] = []

			for framework in normalized_frameworks:
				required = FRAMEWORK_REQUIREMENTS[framework]
				present = sorted([item for item in required if item in clause_types_present])
				missing = sorted([item for item in required if item not in clause_types_present])
				score = len(present) / len(required) if required else 0.0
				framework_scores.append(score)

				framework_results[framework] = {
					"score": round(score, 4),
					"present": present,
					"missing": missing,
				}

			overall_score = (
				sum(framework_scores) / len(framework_scores) if framework_scores else 0.0
			)
			overall_score = max(0.0, min(1.0, overall_score))

			if overall_score >= 0.8:
				compliance_status = "COMPLIANT"
			elif overall_score >= 0.5:
				compliance_status = "PARTIALLY_COMPLIANT"
			else:
				compliance_status = "NON_COMPLIANT"

			llm_analysis = self._analyze_with_llm(clauses, normalized_frameworks)

			processing_time = time.time() - start_time
			self.logger.info(
				"Compliance assessment complete for contract_id=%s status=%s",
				contract_id,
				compliance_status,
			)

			return ComplianceResult(
				contract_id=contract_id,
				frameworks_checked=normalized_frameworks,
				framework_results=framework_results,
				overall_compliance_score=round(overall_score, 4),
				compliance_status=compliance_status,
				compliance_issues=llm_analysis.get("compliance_issues", []),
				missing_requirements=llm_analysis.get("missing_requirements", []),
				compliant_items=llm_analysis.get("compliant_items", []),
				compliance_recommendations=llm_analysis.get(
					"compliance_recommendations", []
				),
				overall_compliance_summary=llm_analysis.get(
					"overall_compliance_summary", ""
				),
				status="success",
				error_message=None,
				processing_time_seconds=processing_time,
			)

		except Exception as exc:
			processing_time = time.time() - start_time
			self.logger.info(
				"Compliance assessment failed for contract_id=%s: %s", contract_id, exc
			)
			return ComplianceResult(
				contract_id=contract_id,
				frameworks_checked=[],
				framework_results={},
				overall_compliance_score=0.0,
				compliance_status="NON_COMPLIANT",
				compliance_issues=[],
				missing_requirements=[],
				compliant_items=[],
				compliance_recommendations=[],
				overall_compliance_summary="",
				status="failed",
				error_message=str(exc),
				processing_time_seconds=processing_time,
			)

	def _normalize_frameworks(self, frameworks: list[str]) -> list[str]:
		"""Normalize requested framework names and keep known unique values."""

		known = set(FRAMEWORK_REQUIREMENTS.keys())
		normalized: list[str] = []
		seen: set[str] = set()

		for framework in frameworks:
			key = str(framework).strip().upper()
			if key in known and key not in seen:
				normalized.append(key)
				seen.add(key)

		return normalized

	def _analyze_with_llm(self, clauses: list[dict], frameworks: list[str]) -> dict:
		"""Use OpenAI to perform deeper compliance analysis across frameworks."""

		if not os.getenv("OPENAI_API_KEY"):
			raise ValueError("OPENAI_API_KEY is not set")

		clause_payload = [
			{
				"clause_type": str(item.get("clause_type", "")).strip(),
				"summary": str(item.get("summary", "")).strip(),
				"clause_text": str(item.get("clause_text", "")).strip(),
				"confidence": float(item.get("confidence", 0.0)),
				"page_hint": float(item.get("page_hint", 0.0)),
			}
			for item in clauses
		]

		user_prompt = (
			"Frameworks to review: "
			f"{json.dumps(frameworks, ensure_ascii=True)}\n\n"
			"Contract clauses:\n"
			f"{json.dumps(clause_payload, ensure_ascii=True)}"
		)

		response = client.chat.completions.create(
			model=self.model,
			messages=[
				{"role": "system", "content": SYSTEM_PROMPT},
				{"role": "user", "content": user_prompt},
			],
			temperature=0,
		)
		response_text = (response.choices[0].message.content or "{}").strip()
		return self._safe_parse_llm_response(response_text)

	def _safe_parse_llm_response(self, response_text: str) -> dict:
		"""Safely parse compliance JSON returned by the LLM."""

		try:
			parsed = json.loads(response_text)
		except json.JSONDecodeError:
			self.logger.info("Failed to parse compliance JSON; using default empty output")
			parsed = {}

		if not isinstance(parsed, dict):
			parsed = {}

		def _to_str_list(value: object) -> list[str]:
			if not isinstance(value, list):
				return []
			return [str(item).strip() for item in value if str(item).strip()]

		return {
			"compliance_issues": _to_str_list(parsed.get("compliance_issues", [])),
			"missing_requirements": _to_str_list(
				parsed.get("missing_requirements", [])
			),
			"compliant_items": _to_str_list(parsed.get("compliant_items", [])),
			"compliance_recommendations": _to_str_list(
				parsed.get("compliance_recommendations", [])
			),
			"overall_compliance_summary": str(
				parsed.get("overall_compliance_summary", "")
			).strip(),
		}
