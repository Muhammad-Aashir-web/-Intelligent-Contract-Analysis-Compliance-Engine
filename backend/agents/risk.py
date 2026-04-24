"""Risk assessment agent for comprehensive contract risk analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

from utils.metrics import calculate_clause_risk_score, calculate_overall_risk

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = (
	"You are a senior contract risk analyst. Analyze these contract clauses and "
	"identify risks. Return ONLY a JSON object with fields: "
	"risk_factors (list of strings describing specific risks found), "
	"recommendations (list of strings with actionable improvements), "
	"red_flags (list of strings for critical issues needing immediate attention), "
	"executive_summary (2-3 sentence plain English summary of overall risk)"
)


@dataclass
class RiskAssessmentResult:
	"""Structured result from contract risk assessment."""

	contract_id: str
	overall_risk_score: float = 0.0
	risk_level: str = "LOW"
	clause_risks: list[dict] = field(default_factory=list)
	top_risk_clauses: list[dict] = field(default_factory=list)
	risk_factors: list[str] = field(default_factory=list)
	recommendations: list[str] = field(default_factory=list)
	red_flags: list[str] = field(default_factory=list)
	executive_summary: str = ""
	status: str = "failed"
	error_message: str | None = None
	processing_time_seconds: float = 0.0


class RiskAssessmentAgent:
	"""Assess contract risks from extracted clauses using rules and LLM analysis."""

	def __init__(self) -> None:
		"""Initialize the risk assessment agent with logger and model config."""

		self.logger = logging.getLogger(__name__)
		self.model = "gpt-4o-mini"

	def process(self, clauses: list[dict], contract_id: str) -> RiskAssessmentResult:
		"""Process extracted clauses and generate a comprehensive risk assessment.

		Args:
			clauses: List of extracted clause dictionaries.
			contract_id: Unique identifier for the contract.

		Returns:
			RiskAssessmentResult with rule-based and AI-assisted risk outputs.
		"""

		start_time = time.time()
		self.logger.info("Starting risk assessment for contract_id=%s", contract_id)

		try:
			if not clauses:
				raise ValueError("No clauses provided for risk assessment")

			clause_risks = self._score_clauses(clauses)
			clause_risks.sort(key=lambda item: float(item.get("risk_score", 0.0)), reverse=True)
			top_risk_clauses = clause_risks[:5]

			overall = calculate_overall_risk(
				[float(item.get("risk_score", 0.0)) for item in clause_risks]
			)

			llm_analysis = self._analyze_top_clauses_with_llm(clause_risks[:10])

			processing_time = time.time() - start_time
			self.logger.info(
				"Risk assessment complete for contract_id=%s level=%s",
				contract_id,
				overall.get("risk_level", "LOW"),
			)

			return RiskAssessmentResult(
				contract_id=contract_id,
				overall_risk_score=float(overall.get("overall_score", 0.0)),
				risk_level=str(overall.get("risk_level", "LOW")),
				clause_risks=clause_risks,
				top_risk_clauses=top_risk_clauses,
				risk_factors=llm_analysis.get("risk_factors", []),
				recommendations=llm_analysis.get("recommendations", []),
				red_flags=llm_analysis.get("red_flags", []),
				executive_summary=llm_analysis.get("executive_summary", ""),
				status="success",
				error_message=None,
				processing_time_seconds=processing_time,
			)

		except Exception as exc:
			processing_time = time.time() - start_time
			self.logger.info(
				"Risk assessment failed for contract_id=%s: %s", contract_id, exc
			)
			return RiskAssessmentResult(
				contract_id=contract_id,
				overall_risk_score=0.0,
				risk_level="LOW",
				clause_risks=[],
				top_risk_clauses=[],
				risk_factors=[],
				recommendations=[],
				red_flags=[],
				executive_summary="",
				status="failed",
				error_message=str(exc),
				processing_time_seconds=processing_time,
			)

	def _score_clauses(self, clauses: list[dict]) -> list[dict]:
		"""Calculate and attach rule-based risk scores to clause dictionaries."""

		scored: list[dict] = []
		for clause in clauses:
			clause_type = str(clause.get("clause_type", "")).strip()
			clause_text = str(clause.get("clause_text", "")).strip()
			risk_score = calculate_clause_risk_score(clause_type, clause_text)

			clause_with_risk = dict(clause)
			clause_with_risk["risk_score"] = risk_score
			scored.append(clause_with_risk)

		self.logger.info("Scored %s clauses with rule-based risk metrics", len(scored))
		return scored

	def _analyze_top_clauses_with_llm(self, top_clauses: list[dict]) -> dict:
		"""Call OpenAI to produce qualitative risk analysis for top risky clauses."""

		if not top_clauses:
			self.logger.info("No clauses available for LLM risk analysis")
			return {
				"risk_factors": [],
				"recommendations": [],
				"red_flags": [],
				"executive_summary": "No clause data provided for AI analysis.",
			}

		if not os.getenv("OPENAI_API_KEY"):
			raise ValueError("OPENAI_API_KEY is not set")

		payload = [
			{
				"clause_type": str(item.get("clause_type", "")).strip(),
				"summary": str(item.get("summary", "")).strip(),
				"clause_text": str(item.get("clause_text", "")).strip(),
				"risk_score": float(item.get("risk_score", 0.0)),
				"confidence": float(item.get("confidence", 0.0)),
				"page_hint": float(item.get("page_hint", 0.0)),
			}
			for item in top_clauses
		]

		user_prompt = (
			"Analyze the following top-risk contract clauses and produce the requested JSON output:\n\n"
			f"{json.dumps(payload, ensure_ascii=True)}"
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
		"""Safely parse model JSON response with fallback defaults."""

		try:
			parsed = json.loads(response_text)
		except json.JSONDecodeError:
			self.logger.info("Failed to parse LLM risk analysis JSON; using defaults")
			parsed = {}

		if not isinstance(parsed, dict):
			parsed = {}

		def _to_str_list(value: object) -> list[str]:
			if not isinstance(value, list):
				return []
			return [str(item).strip() for item in value if str(item).strip()]

		return {
			"risk_factors": _to_str_list(parsed.get("risk_factors", [])),
			"recommendations": _to_str_list(parsed.get("recommendations", [])),
			"red_flags": _to_str_list(parsed.get("red_flags", [])),
			"executive_summary": str(parsed.get("executive_summary", "")).strip(),
		}
