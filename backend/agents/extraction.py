"""Clause extraction agent for structured contract analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import os
import re
import time

from dotenv import load_dotenv
from openai import OpenAI

from utils.chunking import chunk_by_paragraph

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = (
	"You are a legal contract analyst. Extract all contract clauses from the text. "
	"Return ONLY a JSON array of objects with fields: "
	"clause_type (string), clause_text (extracted verbatim text), "
	"summary (one sentence summary), confidence (0.0-1.0 float), "
	"page_hint (approximate position as fraction 0.0-1.0). "
	"Only include clauses you find - do not invent clauses not present."
)

CLAUSE_TYPES = [
	"payment_terms",
	"pricing",
	"penalties",
	"late_fees",
	"currency",
	"tax_obligations",
	"effective_date",
	"expiration_date",
	"renewal_terms",
	"notice_period",
	"termination_for_cause",
	"termination_for_convenience",
	"termination_notice",
	"liability_cap",
	"indemnification",
	"warranty",
	"disclaimer",
	"insurance_requirements",
	"ip_ownership",
	"license_grant",
	"ip_restrictions",
	"work_for_hire",
	"nda_terms",
	"data_protection",
	"privacy_obligations",
	"trade_secrets",
	"dispute_resolution",
	"arbitration",
	"governing_law",
	"jurisdiction",
	"mediation",
	"regulatory_compliance",
	"audit_rights",
	"reporting_obligations",
	"sla_terms",
	"delivery_terms",
	"acceptance_criteria",
	"change_management",
	"exclusivity",
	"non_compete",
	"non_solicitation",
	"subcontracting",
	"force_majeure",
	"business_continuity",
	"assignment",
	"amendment_process",
	"entire_agreement",
	"severability",
	"waiver",
]


@dataclass
class ClauseExtractionResult:
	"""Structured result for clause extraction from a contract."""

	contract_id: str
	clauses: list[dict] = field(default_factory=list)
	total_clauses_found: int = 0
	clause_types_found: list[str] = field(default_factory=list)
	status: str = "failed"
	error_message: str | None = None
	processing_time_seconds: float = 0.0


class ClauseExtractionAgent:
	"""Extract structured clause data from contract text using OpenAI."""

	def __init__(self) -> None:
		"""Initialize the extraction agent with a logger and OpenAI model."""

		self.logger = logging.getLogger(__name__)
		self.model = "gpt-4o-mini"

	def process(self, cleaned_text: str, contract_id: str) -> ClauseExtractionResult:
		"""Extract clauses from cleaned contract text.

		Args:
			cleaned_text: Contract text that has already been cleaned.
			contract_id: Unique identifier for the contract.

		Returns:
			ClauseExtractionResult containing extracted and deduplicated clauses.
		"""

		start_time = time.time()
		self.logger.info("Starting clause extraction for contract_id=%s", contract_id)

		try:
			if not cleaned_text or not cleaned_text.strip():
				raise ValueError("cleaned_text is empty")

			if not os.getenv("OPENAI_API_KEY"):
				raise ValueError("OPENAI_API_KEY is not set")

			chunks = chunk_by_paragraph(cleaned_text)
			self.logger.info("Prepared %s chunks for clause extraction", len(chunks))

			extracted_clauses: list[dict] = []
			total_chunks = len(chunks)

			for index, chunk in enumerate(chunks, start=1):
				self.logger.info(
					"Processing chunk %s/%s for contract_id=%s",
					index,
					total_chunks,
					contract_id,
				)
				response_text = self._extract_chunk_clauses(
					chunk=chunk,
					chunk_index=index,
					total_chunks=total_chunks,
				)
				parsed = self._safe_parse_clauses(response_text)
				extracted_clauses.extend(parsed)

			deduped_clauses = self._deduplicate_clauses(extracted_clauses)
			clause_types_found = sorted(
				{
					str(clause.get("clause_type", "")).strip()
					for clause in deduped_clauses
					if str(clause.get("clause_type", "")).strip()
				}
			)

			processing_time = time.time() - start_time
			self.logger.info(
				"Clause extraction complete for contract_id=%s with %s unique clauses",
				contract_id,
				len(deduped_clauses),
			)

			return ClauseExtractionResult(
				contract_id=contract_id,
				clauses=deduped_clauses,
				total_clauses_found=len(deduped_clauses),
				clause_types_found=clause_types_found,
				status="success",
				error_message=None,
				processing_time_seconds=processing_time,
			)

		except Exception as exc:
			processing_time = time.time() - start_time
			self.logger.info(
				"Clause extraction failed for contract_id=%s: %s", contract_id, exc
			)
			return ClauseExtractionResult(
				contract_id=contract_id,
				clauses=[],
				total_clauses_found=0,
				clause_types_found=[],
				status="failed",
				error_message=str(exc),
				processing_time_seconds=processing_time,
			)

	def _extract_chunk_clauses(self, chunk: str, chunk_index: int, total_chunks: int) -> str:
		"""Call OpenAI for a single chunk and return raw response text."""

		prompt = (
			f"Contract chunk {chunk_index}/{total_chunks}. "
			f"Target clause types include: {', '.join(CLAUSE_TYPES)}.\n\n"
			f"Text:\n{chunk}"
		)

		response = client.chat.completions.create(
			model=self.model,
			messages=[
				{"role": "system", "content": SYSTEM_PROMPT},
				{"role": "user", "content": prompt},
			],
			temperature=0,
		)
		content = response.choices[0].message.content or "[]"
		return content.strip()

	def _safe_parse_clauses(self, response_text: str) -> list[dict]:
		"""Safely parse model output into a list of clause dictionaries."""

		try:
			parsed = json.loads(response_text)
			if isinstance(parsed, list):
				return [self._normalize_clause(item) for item in parsed if isinstance(item, dict)]
			self.logger.info("Model returned non-list JSON payload; skipping chunk output")
			return []
		except json.JSONDecodeError:
			self.logger.info("Malformed JSON detected; attempting regex recovery")

		fenced_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", response_text, re.DOTALL)
		if fenced_match:
			candidate = fenced_match.group(1)
			try:
				parsed = json.loads(candidate)
				if isinstance(parsed, list):
					return [self._normalize_clause(item) for item in parsed if isinstance(item, dict)]
			except json.JSONDecodeError:
				pass

		array_match = re.search(r"(\[\s*\{.*\}\s*\])", response_text, re.DOTALL)
		if array_match:
			candidate = array_match.group(1)
			try:
				parsed = json.loads(candidate)
				if isinstance(parsed, list):
					return [self._normalize_clause(item) for item in parsed if isinstance(item, dict)]
			except json.JSONDecodeError:
				pass

		self.logger.info("Unable to parse clause JSON from model output")
		return []

	def _normalize_clause(self, clause: dict) -> dict:
		"""Normalize a raw clause dictionary into expected keys and value types."""

		confidence = clause.get("confidence", 0.0)
		page_hint = clause.get("page_hint", 0.0)

		try:
			confidence_value = float(confidence)
		except (TypeError, ValueError):
			confidence_value = 0.0

		try:
			page_hint_value = float(page_hint)
		except (TypeError, ValueError):
			page_hint_value = 0.0

		confidence_value = max(0.0, min(1.0, confidence_value))
		page_hint_value = max(0.0, min(1.0, page_hint_value))

		normalized = {
			"clause_type": str(clause.get("clause_type", "")).strip(),
			"clause_text": str(clause.get("clause_text", "")).strip(),
			"summary": str(clause.get("summary", "")).strip(),
			"confidence": confidence_value,
			"page_hint": page_hint_value,
		}
		return normalized

	def _deduplicate_clauses(self, clauses: list[dict]) -> list[dict]:
		"""Deduplicate clauses by type while keeping the highest-confidence record."""

		best_by_type: dict[str, dict] = {}

		for clause in clauses:
			clause_type = str(clause.get("clause_type", "")).strip()
			if not clause_type:
				continue

			current_best = best_by_type.get(clause_type)
			if current_best is None:
				best_by_type[clause_type] = clause
				continue

			current_confidence = float(current_best.get("confidence", 0.0))
			new_confidence = float(clause.get("confidence", 0.0))
			if new_confidence > current_confidence:
				best_by_type[clause_type] = clause

		return list(best_by_type.values())
