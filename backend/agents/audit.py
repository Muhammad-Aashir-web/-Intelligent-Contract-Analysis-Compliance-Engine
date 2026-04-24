"""Audit trail agent for pipeline event logging and timeline retrieval."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
import time
import uuid

from dotenv import load_dotenv
from sqlalchemy import text

from database import get_db

load_dotenv()


@dataclass
class AuditEntry:
	"""Represents one audit event recorded during contract processing."""

	id: str
	contract_id: str
	user_id: str | None
	agent_name: str
	event_type: str
	status: str
	details: dict | None
	duration_seconds: float | None
	timestamp: str
	error_message: str | None


class AuditTrailAgent:
	"""Log and retrieve audit trail entries without interrupting the pipeline."""

	SUPPORTED_EVENT_TYPES = {
		"CONTRACT_UPLOADED",
		"INGESTION_STARTED",
		"INGESTION_COMPLETED",
		"INGESTION_FAILED",
		"EXTRACTION_STARTED",
		"EXTRACTION_COMPLETED",
		"EXTRACTION_FAILED",
		"RISK_ASSESSMENT_STARTED",
		"RISK_ASSESSMENT_COMPLETED",
		"RISK_ASSESSMENT_FAILED",
		"COMPLIANCE_CHECK_STARTED",
		"COMPLIANCE_CHECK_COMPLETED",
		"COMPLIANCE_CHECK_FAILED",
		"NEGOTIATION_STARTED",
		"NEGOTIATION_COMPLETED",
		"NEGOTIATION_FAILED",
		"ANALYSIS_PIPELINE_STARTED",
		"ANALYSIS_PIPELINE_COMPLETED",
		"ANALYSIS_PIPELINE_FAILED",
		"USER_VIEWED_RESULTS",
		"USER_EXPORTED_REPORT",
		"USER_ACCEPTED_SUGGESTION",
	}

	def __init__(self) -> None:
		"""Initialize audit storage and logger."""

		self.logger = logging.getLogger(__name__)
		self._in_memory_audit_logs: list[dict] = []
		self._database_url = os.getenv("DATABASE_URL", "")

	def log_event(
		self,
		event_type: str,
		contract_id: str,
		user_id: str | None,
		agent_name: str,
		status: str,
		details: dict | None,
		duration_seconds: float | None,
	) -> AuditEntry:
		"""Create and persist an audit event in memory and best-effort database storage.

		Args:
			event_type: Event name, typically one of ``SUPPORTED_EVENT_TYPES``.
			contract_id: Contract identifier for traceability.
			user_id: Optional user identifier.
			agent_name: Name of the agent emitting the event.
			status: Event status such as ``started``, ``completed``, or ``failed``.
			details: Optional structured event details.
			duration_seconds: Optional execution duration in seconds.

		Returns:
			The created ``AuditEntry``.
		"""

		timestamp = datetime.now(timezone.utc).isoformat()
		normalized_event_type = str(event_type).strip().upper()
		entry = AuditEntry(
			id=str(uuid.uuid4()),
			contract_id=str(contract_id),
			user_id=user_id,
			agent_name=str(agent_name),
			event_type=normalized_event_type,
			status=str(status),
			details=details,
			duration_seconds=float(duration_seconds) if duration_seconds is not None else None,
			timestamp=timestamp,
			error_message=self._extract_error_message(status=status, details=details),
		)

		try:
			if normalized_event_type not in self.SUPPORTED_EVENT_TYPES:
				self.logger.warning("Logging non-standard audit event type: %s", normalized_event_type)

			self._in_memory_audit_logs.append(asdict(entry))
			self.logger.info(
				"Audit event logged: event_type=%s contract_id=%s agent=%s status=%s",
				entry.event_type,
				entry.contract_id,
				entry.agent_name,
				entry.status,
			)

			self._try_write_to_db(entry)
			return entry
		except Exception as exc:  # pragma: no cover - defensive safety path
			self.logger.warning("Audit logging failed unexpectedly: %s", exc)
			return entry

	def log_agent_start(
		self,
		agent_name: str,
		contract_id: str,
		user_id: str | None = None,
	) -> AuditEntry:
		"""Convenience helper to log an agent start event."""

		event_type = f"{self._normalize_agent_name(agent_name)}_STARTED"
		return self.log_event(
			event_type=event_type,
			contract_id=contract_id,
			user_id=user_id,
			agent_name=agent_name,
			status="started",
			details=None,
			duration_seconds=None,
		)

	def log_agent_complete(
		self,
		agent_name: str,
		contract_id: str,
		result_summary: dict,
		duration_seconds: float,
		user_id: str | None = None,
	) -> AuditEntry:
		"""Convenience helper to log successful agent completion."""

		event_type = f"{self._normalize_agent_name(agent_name)}_COMPLETED"
		return self.log_event(
			event_type=event_type,
			contract_id=contract_id,
			user_id=user_id,
			agent_name=agent_name,
			status="completed",
			details=result_summary,
			duration_seconds=duration_seconds,
		)

	def log_agent_error(
		self,
		agent_name: str,
		contract_id: str,
		error_message: str,
		user_id: str | None = None,
	) -> AuditEntry:
		"""Convenience helper to log agent failure events."""

		event_type = f"{self._normalize_agent_name(agent_name)}_FAILED"
		return self.log_event(
			event_type=event_type,
			contract_id=contract_id,
			user_id=user_id,
			agent_name=agent_name,
			status="failed",
			details={"error_message": error_message},
			duration_seconds=None,
		)

	def get_contract_audit_trail(self, contract_id: str) -> list[AuditEntry]:
		"""Retrieve all known audit events for a contract sorted by timestamp.

		Database reads are best-effort; in-memory data is always available.
		"""

		collected: dict[str, AuditEntry] = {}

		try:
			for item in self._in_memory_audit_logs:
				if str(item.get("contract_id")) == str(contract_id):
					entry = self._dict_to_entry(item)
					collected[entry.id] = entry
		except Exception as exc:
			self.logger.warning("Failed to read in-memory audit logs: %s", exc)

		db_rows = self._try_read_from_db(contract_id)
		for row in db_rows:
			collected[row.id] = row

		entries = sorted(collected.values(), key=lambda entry: entry.timestamp)
		return entries

	def get_audit_summary(self, contract_id: str) -> dict:
		"""Build a summarized view of audit activity for a contract."""

		try:
			entries = self.get_contract_audit_trail(contract_id)
			total_events = len(entries)

			agents_run = sorted({entry.agent_name for entry in entries if entry.agent_name})
			failed_agents = sorted(
				{
					entry.agent_name
					for entry in entries
					if entry.status.lower() == "failed" or entry.event_type.endswith("_FAILED")
				}
			)
			total_processing_time = sum(
				entry.duration_seconds or 0.0 for entry in entries
			)
			timeline = [
				{
					"event_type": entry.event_type,
					"timestamp": entry.timestamp,
					"duration": entry.duration_seconds,
				}
				for entry in entries
			]

			if not entries:
				overall_status = "PARTIAL"
			elif failed_agents and len(failed_agents) == len(agents_run) and agents_run:
				overall_status = "FAILED"
			elif failed_agents:
				overall_status = "PARTIAL"
			else:
				overall_status = "SUCCESS"

			return {
				"total_events": total_events,
				"agents_run": agents_run,
				"failed_agents": failed_agents,
				"total_processing_time": round(total_processing_time, 4),
				"timeline": timeline,
				"overall_status": overall_status,
			}
		except Exception as exc:
			self.logger.warning("Failed to build audit summary for contract_id=%s: %s", contract_id, exc)
			return {
				"total_events": 0,
				"agents_run": [],
				"failed_agents": [],
				"total_processing_time": 0.0,
				"timeline": [],
				"overall_status": "FAILED",
			}

	def _try_write_to_db(self, entry: AuditEntry) -> None:
		"""Best-effort write to audit_logs table; never raises to caller."""

		db_gen = None
		db = None
		start_time = time.time()

		try:
			db_gen = get_db()
			db = next(db_gen)

			details_json = json.dumps(entry.details, ensure_ascii=True) if entry.details is not None else None
			db.execute(
				text(
					"""
					INSERT INTO audit_logs (
						id,
						contract_id,
						user_id,
						agent_name,
						event_type,
						status,
						details,
						duration_seconds,
						timestamp,
						error_message
					) VALUES (
						:id,
						:contract_id,
						:user_id,
						:agent_name,
						:event_type,
						:status,
						CAST(:details AS JSONB),
						:duration_seconds,
						:timestamp,
						:error_message
					)
					"""
				),
				{
					"id": entry.id,
					"contract_id": entry.contract_id,
					"user_id": entry.user_id,
					"agent_name": entry.agent_name,
					"event_type": entry.event_type,
					"status": entry.status,
					"details": details_json,
					"duration_seconds": entry.duration_seconds,
					"timestamp": entry.timestamp,
					"error_message": entry.error_message,
				},
			)
			db.commit()

			elapsed = time.time() - start_time
			self.logger.info("Audit event persisted to database in %.4fs", elapsed)
		except Exception as exc:
			if db is not None:
				try:
					db.rollback()
				except Exception:
					pass
			self.logger.warning("Audit DB write failed (non-blocking): %s", exc)
		finally:
			if db_gen is not None:
				try:
					db_gen.close()
				except Exception:
					pass

	def _try_read_from_db(self, contract_id: str) -> list[AuditEntry]:
		"""Best-effort read from audit_logs table; returns empty list on failure."""

		db_gen = None
		db = None

		try:
			db_gen = get_db()
			db = next(db_gen)
			result = db.execute(
				text(
					"""
					SELECT
						id,
						contract_id,
						user_id,
						agent_name,
						event_type,
						status,
						details,
						duration_seconds,
						timestamp,
						error_message
					FROM audit_logs
					WHERE contract_id = :contract_id
					ORDER BY timestamp ASC
					"""
				),
				{"contract_id": contract_id},
			)

			entries: list[AuditEntry] = []
			for row in result.mappings().all():
				raw_details = row.get("details")
				if isinstance(raw_details, str):
					try:
						details = json.loads(raw_details)
					except json.JSONDecodeError:
						details = None
				else:
					details = raw_details

				timestamp_raw = row.get("timestamp")
				if isinstance(timestamp_raw, datetime):
					timestamp_value = timestamp_raw.astimezone(timezone.utc).isoformat()
				else:
					timestamp_value = str(timestamp_raw)

				entry = AuditEntry(
					id=str(row.get("id")),
					contract_id=str(row.get("contract_id")),
					user_id=row.get("user_id"),
					agent_name=str(row.get("agent_name") or ""),
					event_type=str(row.get("event_type") or ""),
					status=str(row.get("status") or ""),
					details=details,
					duration_seconds=(
						float(row.get("duration_seconds"))
						if row.get("duration_seconds") is not None
						else None
					),
					timestamp=timestamp_value,
					error_message=row.get("error_message"),
				)
				entries.append(entry)

			return entries
		except Exception as exc:
			self.logger.warning("Audit DB read failed (non-blocking): %s", exc)
			return []
		finally:
			if db_gen is not None:
				try:
					db_gen.close()
				except Exception:
					pass

	def _normalize_agent_name(self, agent_name: str) -> str:
		"""Normalize an agent identifier for event type generation."""

		return str(agent_name).strip().upper().replace(" ", "_")

	def _extract_error_message(self, status: str, details: dict | None) -> str | None:
		"""Extract error message from event details when status indicates failure."""

		if str(status).lower() != "failed" or not isinstance(details, dict):
			return None
		message = details.get("error_message")
		return str(message) if message else None

	def _dict_to_entry(self, payload: dict) -> AuditEntry:
		"""Convert a raw dictionary payload to AuditEntry with safe defaults."""

		return AuditEntry(
			id=str(payload.get("id", str(uuid.uuid4()))),
			contract_id=str(payload.get("contract_id", "")),
			user_id=payload.get("user_id"),
			agent_name=str(payload.get("agent_name", "")),
			event_type=str(payload.get("event_type", "")),
			status=str(payload.get("status", "")),
			details=payload.get("details") if isinstance(payload.get("details"), dict) or payload.get("details") is None else None,
			duration_seconds=(
				float(payload.get("duration_seconds"))
				if payload.get("duration_seconds") is not None
				else None
			),
			timestamp=str(payload.get("timestamp", datetime.now(timezone.utc).isoformat())),
			error_message=(
				str(payload.get("error_message"))
				if payload.get("error_message") is not None
				else None
			),
		)
