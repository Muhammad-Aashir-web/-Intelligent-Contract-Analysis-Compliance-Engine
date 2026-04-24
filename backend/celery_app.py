"""Celery application and background task for contract analysis.

# Reminder: add REDIS_URL to .env, for example:
# REDIS_URL=redis://localhost:6379/0
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
from typing import Any

from celery import Celery
from dotenv import load_dotenv

from database import SessionLocal
from models.clause import Clause
from models.contract import Contract
from services.embeddings import EmbeddingsService
from utils.chunking import chunk_by_size
from workflows.contract_analysis import run_contract_analysis

load_dotenv()

logger = logging.getLogger(__name__)

celery_app = Celery(
	"contract_intelligence",
	broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
	backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)

celery_app.conf.update(
	task_serializer="json",
	result_serializer="json",
	accept_content=["json"],
	timezone="UTC",
)


def _utc_now() -> datetime:
	"""Return current timezone-aware UTC timestamp."""

	return datetime.now(timezone.utc)


def _normalize_frameworks(frameworks: list[str] | tuple[str, ...] | None) -> list[str]:
	"""Normalize framework list while preserving a safe default."""

	if not frameworks:
		return ["GENERAL"]
	cleaned = [str(item).strip().upper() for item in frameworks if str(item).strip()]
	return cleaned or ["GENERAL"]


def _persist_error(contract: Contract, message: str) -> None:
	"""Persist error details on the contract using available schema fields."""

	if hasattr(contract, "error_message"):
		setattr(contract, "error_message", message)
	else:
		fallback_summary = (contract.summary or "").strip()
		contract.summary = f"{fallback_summary}\n\nProcessing error: {message}".strip()


def _extract_clauses_payload(extraction_result: dict[str, Any] | None) -> list[dict[str, Any]]:
	"""Safely extract clause list from workflow extraction result."""

	if not isinstance(extraction_result, dict):
		return []
	clauses = extraction_result.get("clauses", [])
	if not isinstance(clauses, list):
		return []
	return [item for item in clauses if isinstance(item, dict)]


@celery_app.task(bind=True, max_retries=3)
def process_contract_task(
	self: Any,
	contract_id: int,
	file_path: str,
	frameworks: list[str] | None = None,
	negotiation_stance: str = "balanced",
) -> dict[str, Any]:
	"""Analyze a contract asynchronously and persist all outcomes.

	This task updates processing status in PostgreSQL, executes the full LangGraph
	pipeline, stores extracted clauses, writes risk outputs, and saves embeddings.
	On failure it marks the contract as failed and retries up to max_retries.
	"""

	db = SessionLocal()
	normalized_frameworks = _normalize_frameworks(frameworks)

	logger.info(
		"Starting process_contract_task contract_id=%s file_path=%s frameworks=%s stance=%s attempt=%s",
		contract_id,
		file_path,
		normalized_frameworks,
		negotiation_stance,
		getattr(self.request, "retries", 0),
	)

	try:
		contract = db.query(Contract).filter(Contract.id == contract_id).first()
		if contract is None:
			raise ValueError(f"Contract not found: {contract_id}")

		logger.info("Setting contract_id=%s status=processing", contract_id)
		contract.status = "processing"
		db.commit()

		analysis_result = run_contract_analysis(
			file_path=file_path,
			contract_id=str(contract_id),
			frameworks=normalized_frameworks,
			negotiation_stance=negotiation_stance,
		)
		logger.info("Workflow complete for contract_id=%s", contract_id)

		ingestion_result = analysis_result.get("ingestion_result")
		extraction_result = analysis_result.get("extraction_result")
		risk_result = analysis_result.get("risk_result")

		if isinstance(ingestion_result, dict):
			raw_text = str(ingestion_result.get("cleaned_text") or "").strip()
			if raw_text:
				contract.raw_text = raw_text

		if isinstance(risk_result, dict):
			contract.risk_score = float(risk_result.get("overall_risk_score") or 0.0)
			contract.risk_level = str(risk_result.get("risk_level") or "LOW")
			if str(risk_result.get("executive_summary") or "").strip():
				contract.summary = str(risk_result.get("executive_summary") or "").strip()

		clauses_payload = _extract_clauses_payload(extraction_result)
		logger.info("Persisting %s extracted clauses for contract_id=%s", len(clauses_payload), contract_id)

		db.query(Clause).filter(Clause.contract_id == contract_id).delete(synchronize_session=False)
		for clause_item in clauses_payload:
			clause = Clause(
				contract_id=contract_id,
				clause_type=str(clause_item.get("clause_type") or "unknown"),
				clause_text=str(clause_item.get("clause_text") or "").strip(),
				risk_score=float(clause_item.get("risk_score") or 0.0),
				risk_level=str(clause_item.get("risk_level") or "LOW"),
				risk_explanation=str(clause_item.get("risk_explanation") or "").strip() or None,
				compliance_status=str(clause_item.get("compliance_status") or "").strip() or None,
				compliance_notes=str(clause_item.get("compliance_notes") or "").strip() or None,
				negotiation_suggestion=str(clause_item.get("negotiation_suggestion") or "").strip() or None,
				is_flagged=bool(clause_item.get("is_flagged", False)),
			)
			db.add(clause)

		contract.status = "completed"
		contract.processed_at = _utc_now()
		db.commit()
		logger.info("Contract persisted as completed contract_id=%s", contract_id)

		try:
			embeddings = EmbeddingsService()
			full_text = str((ingestion_result or {}).get("cleaned_text") or contract.raw_text or "").strip()
			text_chunks = chunk_by_size(full_text, chunk_size=1000, overlap=150) if full_text else []

			if text_chunks:
				doc_embed_result = embeddings.embed_and_store_document(
					contract_id=str(contract_id),
					chunks=text_chunks,
					metadata={
						"file_name": contract.file_name,
						"contract_type": contract.contract_type,
						"source": "full_text",
					},
				)
				logger.info("Document embeddings result for contract_id=%s: %s", contract_id, doc_embed_result)
			else:
				logger.info("Skipping document embeddings for contract_id=%s due to empty text", contract_id)

			clause_embed_result = embeddings.embed_and_store_clauses(
				contract_id=str(contract_id),
				clauses=clauses_payload,
			)
			logger.info("Clause embeddings result for contract_id=%s: %s", contract_id, clause_embed_result)
		except Exception:
			logger.exception("Embeddings storage failed for contract_id=%s", contract_id)

		return {
			"contract_id": contract_id,
			"status": "completed",
			"risk_score": contract.risk_score,
			"risk_level": contract.risk_level,
			"clauses_stored": len(clauses_payload),
		}

	except Exception as exc:
		logger.exception("Contract processing failed for contract_id=%s", contract_id)
		error_message = str(exc)

		try:
			contract = db.query(Contract).filter(Contract.id == contract_id).first()
			if contract is not None:
				contract.status = "failed"
				contract.processed_at = _utc_now()
				_persist_error(contract, error_message)
				db.commit()
				logger.info("Marked contract_id=%s as failed", contract_id)
		except Exception:
			db.rollback()
			logger.exception("Failed to persist failure status for contract_id=%s", contract_id)

		if getattr(self.request, "retries", 0) < getattr(self, "max_retries", 3):
			raise self.retry(exc=exc, countdown=60)
		raise
	finally:
		db.close()
