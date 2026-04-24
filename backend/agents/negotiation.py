"""Negotiation agent for clause rewrite suggestions and strategy guidance."""

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

_VALID_STANCES = {"buyer_friendly", "seller_friendly", "balanced"}


@dataclass
class NegotiationResult:
	"""Structured output for contract negotiation support."""

	contract_id: str
	negotiation_stance: str
	clauses_reviewed: int = 0
	clauses_with_suggestions: int = 0
	clause_suggestions: list[dict] = field(default_factory=list)
	opening_strategy: str = ""
	priority_clauses: list[str] = field(default_factory=list)
	concession_areas: list[str] = field(default_factory=list)
	deal_breakers: list[str] = field(default_factory=list)
	negotiation_timeline: str = ""
	status: str = "failed"
	error_message: str | None = None
	processing_time_seconds: float = 0.0


class NegotiationAgent:
	"""Generate clause-level alternatives and overall contract negotiation strategy."""

	def __init__(self) -> None:
		"""Initialize the negotiation agent with logger and model settings."""

		self.logger = logging.getLogger(__name__)
		self.model = "gpt-4o-mini"

	def process(
		self,
		clauses: list[dict],
		contract_id: str,
		negotiation_stance: str = "balanced",
	) -> NegotiationResult:
		"""Process high-risk clauses and return negotiation recommendations.

		Args:
			clauses: Clause dictionaries with ``clause_type``, ``clause_text``, and ``risk_score``.
			contract_id: Unique identifier for the contract.
			negotiation_stance: One of ``buyer_friendly``, ``seller_friendly``, or ``balanced``.

		Returns:
			NegotiationResult with clause-level rewrites and strategy guidance.
		"""

		start_time = time.time()
		self.logger.info("Starting negotiation analysis for contract_id=%s", contract_id)

		try:
			normalized_stance = negotiation_stance.strip().lower()
			if normalized_stance not in _VALID_STANCES:
				raise ValueError(
					"Invalid negotiation_stance. Expected buyer_friendly, seller_friendly, or balanced"
				)

			high_risk_clauses = self._select_high_risk_clauses(clauses)
			clauses_reviewed = len(high_risk_clauses)

			if clauses_reviewed > 0 and not os.getenv("OPENAI_API_KEY"):
				raise ValueError("OPENAI_API_KEY is not set")

			self.logger.info(
				"Selected %s high-risk clauses for contract_id=%s",
				clauses_reviewed,
				contract_id,
			)

			clause_suggestions: list[dict] = []
			for index, clause in enumerate(high_risk_clauses, start=1):
				self.logger.info(
					"Generating negotiation suggestion %s/%s for contract_id=%s",
					index,
					clauses_reviewed,
					contract_id,
				)
				suggestion = self._generate_clause_suggestion(
					clause=clause,
					negotiation_stance=normalized_stance,
				)
				clause_suggestions.append({**clause, **suggestion})

			strategy = self._generate_overall_strategy(
				clauses=high_risk_clauses,
				negotiation_stance=normalized_stance,
			)

			processing_time = time.time() - start_time
			return NegotiationResult(
				contract_id=contract_id,
				negotiation_stance=normalized_stance,
				clauses_reviewed=clauses_reviewed,
				clauses_with_suggestions=len(clause_suggestions),
				clause_suggestions=clause_suggestions,
				opening_strategy=strategy.get("opening_strategy", ""),
				priority_clauses=strategy.get("priority_clauses", []),
				concession_areas=strategy.get("concession_areas", []),
				deal_breakers=strategy.get("deal_breakers", []),
				negotiation_timeline=strategy.get("negotiation_timeline", ""),
				status="success",
				error_message=None,
				processing_time_seconds=processing_time,
			)

		except Exception as exc:
			processing_time = time.time() - start_time
			self.logger.info(
				"Negotiation analysis failed for contract_id=%s: %s", contract_id, exc
			)
			return NegotiationResult(
				contract_id=contract_id,
				negotiation_stance=negotiation_stance,
				clauses_reviewed=0,
				clauses_with_suggestions=0,
				clause_suggestions=[],
				opening_strategy="",
				priority_clauses=[],
				concession_areas=[],
				deal_breakers=[],
				negotiation_timeline="",
				status="failed",
				error_message=str(exc),
				processing_time_seconds=processing_time,
			)

	def _select_high_risk_clauses(self, clauses: list[dict]) -> list[dict]:
		"""Filter, sort, and cap high-risk clauses to control API costs."""

		eligible: list[dict] = []
		for clause in clauses:
			try:
				risk_score = float(clause.get("risk_score", 0.0))
			except (TypeError, ValueError):
				risk_score = 0.0

			if risk_score >= 0.4:
				clause_copy = dict(clause)
				clause_copy["risk_score"] = risk_score
				eligible.append(clause_copy)

		eligible.sort(key=lambda item: float(item.get("risk_score", 0.0)), reverse=True)
		return eligible[:15]

	def _generate_clause_suggestion(self, clause: dict, negotiation_stance: str) -> dict:
		"""Call OpenAI to rewrite one high-risk clause into improved language."""

		system_prompt = (
			"You are an expert contract negotiation attorney with 20 years of experience. "
			"Your task is to rewrite problematic contract clauses into better alternatives. "
			f"Negotiation stance: {negotiation_stance}\n"
			"- buyer_friendly: protect the buyer/client interests primarily\n"
			"- seller_friendly: protect the seller/vendor interests primarily\n"
			"- balanced: fair and reasonable for both parties\n"
			"Return ONLY a JSON object with fields:\n"
			"original_issues (list of strings explaining what is wrong with the clause),\n"
			"suggested_language (the complete rewritten clause text),\n"
			"key_changes (list of strings explaining each change made),\n"
			"negotiation_notes (string with tips for negotiating this clause),\n"
			"fallback_position (string with minimum acceptable version if full suggestion rejected)"
		)

		prompt_payload = {
			"clause_type": str(clause.get("clause_type", "")).strip(),
			"clause_text": str(clause.get("clause_text", "")).strip(),
			"summary": str(clause.get("summary", "")).strip(),
			"risk_score": float(clause.get("risk_score", 0.0)),
			"confidence": float(clause.get("confidence", 0.0)),
			"page_hint": float(clause.get("page_hint", 0.0)),
		}

		response = client.chat.completions.create(
			model=self.model,
			messages=[
				{"role": "system", "content": system_prompt},
				{
					"role": "user",
					"content": (
						"Rewrite this clause and return the required JSON only:\n\n"
						f"{json.dumps(prompt_payload, ensure_ascii=True)}"
					),
				},
			],
			temperature=0,
		)
		response_text = (response.choices[0].message.content or "{}").strip()
		return self._safe_parse_clause_suggestion(response_text)

	def _generate_overall_strategy(self, clauses: list[dict], negotiation_stance: str) -> dict:
		"""Generate one overall negotiation strategy from high-risk clause summary."""

		if not clauses:
			self.logger.info("No high-risk clauses for overall negotiation strategy")
			return {
				"opening_strategy": "No high-risk clauses identified.",
				"priority_clauses": [],
				"concession_areas": [],
				"deal_breakers": [],
				"negotiation_timeline": "No immediate negotiation actions required.",
			}

		summary_payload = [
			{
				"clause_type": str(item.get("clause_type", "")).strip(),
				"summary": str(item.get("summary", "")).strip(),
				"risk_score": float(item.get("risk_score", 0.0)),
			}
			for item in clauses
		]

		system_prompt = (
			"You are an expert contract negotiation strategist. "
			f"Negotiation stance: {negotiation_stance}. "
			"Return ONLY a JSON object with:\n"
			"opening_strategy (string: how to open negotiations),\n"
			"priority_clauses (list of strings: which clauses to fight hardest for),\n"
			"concession_areas (list of strings: where you can compromise),\n"
			"deal_breakers (list of strings: clauses that must be changed or walk away),\n"
			"negotiation_timeline (string: suggested timeline and approach)"
		)

		response = client.chat.completions.create(
			model=self.model,
			messages=[
				{"role": "system", "content": system_prompt},
				{
					"role": "user",
					"content": (
						"Build a negotiation strategy using this high-risk clause summary:\n\n"
						f"{json.dumps(summary_payload, ensure_ascii=True)}"
					),
				},
			],
			temperature=0,
		)
		response_text = (response.choices[0].message.content or "{}").strip()
		return self._safe_parse_strategy(response_text)

	def _safe_parse_clause_suggestion(self, response_text: str) -> dict:
		"""Safely parse per-clause suggestion JSON response."""

		try:
			parsed = json.loads(response_text)
		except json.JSONDecodeError:
			self.logger.info("Failed to parse clause suggestion JSON; using fallback")
			parsed = {}

		if not isinstance(parsed, dict):
			parsed = {}

		def _to_str_list(value: object) -> list[str]:
			if not isinstance(value, list):
				return []
			return [str(item).strip() for item in value if str(item).strip()]

		return {
			"original_issues": _to_str_list(parsed.get("original_issues", [])),
			"suggested_language": str(parsed.get("suggested_language", "")).strip(),
			"key_changes": _to_str_list(parsed.get("key_changes", [])),
			"negotiation_notes": str(parsed.get("negotiation_notes", "")).strip(),
			"fallback_position": str(parsed.get("fallback_position", "")).strip(),
		}

	def _safe_parse_strategy(self, response_text: str) -> dict:
		"""Safely parse overall strategy JSON response."""

		try:
			parsed = json.loads(response_text)
		except json.JSONDecodeError:
			self.logger.info("Failed to parse negotiation strategy JSON; using fallback")
			parsed = {}

		if not isinstance(parsed, dict):
			parsed = {}

		def _to_str_list(value: object) -> list[str]:
			if not isinstance(value, list):
				return []
			return [str(item).strip() for item in value if str(item).strip()]

		return {
			"opening_strategy": str(parsed.get("opening_strategy", "")).strip(),
			"priority_clauses": _to_str_list(parsed.get("priority_clauses", [])),
			"concession_areas": _to_str_list(parsed.get("concession_areas", [])),
			"deal_breakers": _to_str_list(parsed.get("deal_breakers", [])),
			"negotiation_timeline": str(parsed.get("negotiation_timeline", "")).strip(),
		}
