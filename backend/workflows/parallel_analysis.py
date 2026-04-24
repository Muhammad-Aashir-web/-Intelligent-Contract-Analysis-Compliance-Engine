"""Parallel workflow helpers for contract risk, compliance, and negotiation analysis."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
import dataclasses
import logging
import time

from agents.audit import AuditTrailAgent
from agents.compliance import ComplianceAgent
from agents.negotiation import NegotiationAgent
from agents.risk import RiskAssessmentAgent

logger = logging.getLogger(__name__)


def run_parallel_analysis(
	clauses: list[dict],
	contract_id: str,
	user_id: str | None = None,
	negotiation_stance: str = "balanced",
	frameworks: list[str] | None = None,
) -> dict:
	"""Run risk, compliance, and negotiation analysis in parallel.

	Args:
		clauses: Extracted clause dictionaries.
		contract_id: Contract identifier.
		user_id: Optional user identifier for audit events.
		negotiation_stance: Negotiation stance for negotiation analysis.
		frameworks: Optional compliance frameworks; defaults to ["GENERAL"].

	Returns:
		Dictionary containing per-agent results, error details, and duration.
	"""

	selected_frameworks = frameworks if frameworks is not None else ["GENERAL"]
	start_time = time.time()
	audit_agent = AuditTrailAgent()

	results: dict = {
		"risk": None,
		"compliance": None,
		"negotiation": None,
		"errors": [],
		"duration": 0.0,
	}

	logger.info("Starting parallel analysis for contract_id=%s", contract_id)

	def _result_to_dict(result_obj: object) -> dict:
		"""Convert dataclass-like result objects into plain dictionaries."""

		if dataclasses.is_dataclass(result_obj):
			return dataclasses.asdict(result_obj)
		if isinstance(result_obj, dict):
			return result_obj
		return {"status": "failed", "error_message": "Unexpected result type"}

	def run_risk(worker_clauses: list[dict], worker_contract_id: str) -> dict:
		"""Worker that executes risk assessment."""

		worker_start = time.time()
		logger.info("Parallel worker started: risk for contract_id=%s", worker_contract_id)
		audit_agent.log_event(
			event_type="RISK_ASSESSMENT_STARTED",
			contract_id=worker_contract_id,
			user_id=user_id,
			agent_name="risk_assessment",
			status="started",
			details=None,
			duration_seconds=None,
		)

		try:
			agent = RiskAssessmentAgent()
			result = _result_to_dict(agent.process(worker_clauses, worker_contract_id))
			result["worker_duration"] = time.time() - worker_start

			status = str(result.get("status", "")).lower()
			event_type = "RISK_ASSESSMENT_COMPLETED" if status == "success" else "RISK_ASSESSMENT_FAILED"
			audit_status = "completed" if status == "success" else "failed"

			audit_agent.log_event(
				event_type=event_type,
				contract_id=worker_contract_id,
				user_id=user_id,
				agent_name="risk_assessment",
				status=audit_status,
				details=result,
				duration_seconds=result["worker_duration"],
			)
			logger.info("Parallel worker completed: risk for contract_id=%s", worker_contract_id)
			return result
		except Exception as exc:  # pragma: no cover - defensive path
			logger.exception("Parallel worker failed: risk for contract_id=%s", worker_contract_id)
			worker_duration = time.time() - worker_start
			audit_agent.log_event(
				event_type="RISK_ASSESSMENT_FAILED",
				contract_id=worker_contract_id,
				user_id=user_id,
				agent_name="risk_assessment",
				status="failed",
				details={"error_message": str(exc)},
				duration_seconds=worker_duration,
			)
			return {
				"status": "failed",
				"error_message": str(exc),
				"worker_duration": worker_duration,
			}

	def run_compliance(
		worker_clauses: list[dict],
		worker_contract_id: str,
		worker_frameworks: list[str],
	) -> dict:
		"""Worker that executes compliance checks."""

		worker_start = time.time()
		logger.info("Parallel worker started: compliance for contract_id=%s", worker_contract_id)
		audit_agent.log_event(
			event_type="COMPLIANCE_CHECK_STARTED",
			contract_id=worker_contract_id,
			user_id=user_id,
			agent_name="compliance_check",
			status="started",
			details={"frameworks": worker_frameworks},
			duration_seconds=None,
		)

		try:
			agent = ComplianceAgent()
			result = _result_to_dict(
				agent.process(worker_clauses, worker_contract_id, worker_frameworks)
			)
			result["worker_duration"] = time.time() - worker_start

			status = str(result.get("status", "")).lower()
			event_type = "COMPLIANCE_CHECK_COMPLETED" if status == "success" else "COMPLIANCE_CHECK_FAILED"
			audit_status = "completed" if status == "success" else "failed"

			audit_agent.log_event(
				event_type=event_type,
				contract_id=worker_contract_id,
				user_id=user_id,
				agent_name="compliance_check",
				status=audit_status,
				details=result,
				duration_seconds=result["worker_duration"],
			)
			logger.info("Parallel worker completed: compliance for contract_id=%s", worker_contract_id)
			return result
		except Exception as exc:  # pragma: no cover - defensive path
			logger.exception("Parallel worker failed: compliance for contract_id=%s", worker_contract_id)
			worker_duration = time.time() - worker_start
			audit_agent.log_event(
				event_type="COMPLIANCE_CHECK_FAILED",
				contract_id=worker_contract_id,
				user_id=user_id,
				agent_name="compliance_check",
				status="failed",
				details={"error_message": str(exc)},
				duration_seconds=worker_duration,
			)
			return {
				"status": "failed",
				"error_message": str(exc),
				"worker_duration": worker_duration,
			}

	def run_negotiation(
		worker_clauses: list[dict],
		worker_contract_id: str,
		worker_stance: str,
	) -> dict:
		"""Worker that executes negotiation suggestion generation."""

		worker_start = time.time()
		logger.info("Parallel worker started: negotiation for contract_id=%s", worker_contract_id)
		audit_agent.log_event(
			event_type="NEGOTIATION_STARTED",
			contract_id=worker_contract_id,
			user_id=user_id,
			agent_name="negotiation",
			status="started",
			details={"negotiation_stance": worker_stance},
			duration_seconds=None,
		)

		try:
			agent = NegotiationAgent()
			result = _result_to_dict(
				agent.process(worker_clauses, worker_contract_id, worker_stance)
			)
			result["worker_duration"] = time.time() - worker_start

			status = str(result.get("status", "")).lower()
			event_type = "NEGOTIATION_COMPLETED" if status == "success" else "NEGOTIATION_FAILED"
			audit_status = "completed" if status == "success" else "failed"

			audit_agent.log_event(
				event_type=event_type,
				contract_id=worker_contract_id,
				user_id=user_id,
				agent_name="negotiation",
				status=audit_status,
				details=result,
				duration_seconds=result["worker_duration"],
			)
			logger.info("Parallel worker completed: negotiation for contract_id=%s", worker_contract_id)
			return result
		except Exception as exc:  # pragma: no cover - defensive path
			logger.exception("Parallel worker failed: negotiation for contract_id=%s", worker_contract_id)
			worker_duration = time.time() - worker_start
			audit_agent.log_event(
				event_type="NEGOTIATION_FAILED",
				contract_id=worker_contract_id,
				user_id=user_id,
				agent_name="negotiation",
				status="failed",
				details={"error_message": str(exc)},
				duration_seconds=worker_duration,
			)
			return {
				"status": "failed",
				"error_message": str(exc),
				"worker_duration": worker_duration,
			}

	with ThreadPoolExecutor(max_workers=3) as executor:
		futures: dict[Future, str] = {
			executor.submit(run_risk, clauses, contract_id): "risk",
			executor.submit(run_compliance, clauses, contract_id, selected_frameworks): "compliance",
			executor.submit(run_negotiation, clauses, contract_id, negotiation_stance): "negotiation",
		}

		for future in as_completed(futures):
			worker_name = futures[future]
			try:
				worker_result = future.result()
			except Exception as exc:  # pragma: no cover - defensive path
				logger.exception("Future failed unexpectedly for worker=%s", worker_name)
				worker_result = {"status": "failed", "error_message": str(exc), "worker_duration": 0.0}

			results[worker_name] = worker_result
			if str(worker_result.get("status", "")).lower() != "success":
				results["errors"].append(
					{
						"agent": worker_name,
						"error": str(worker_result.get("error_message", "Unknown error")),
					}
				)

	total_duration = time.time() - start_time
	results["duration"] = total_duration

	sequential_estimate = 0.0
	for worker_name in ("risk", "compliance", "negotiation"):
		worker_payload = results.get(worker_name)
		if isinstance(worker_payload, dict):
			sequential_estimate += float(worker_payload.get("worker_duration", 0.0))

	estimated_time_saved = sequential_estimate - total_duration
	logger.info(
		"Parallel analysis completed for contract_id=%s in %.4fs (estimated sequential %.4fs, saved %.4fs)",
		contract_id,
		total_duration,
		sequential_estimate,
		estimated_time_saved,
	)

	return results


def compare_sequential_vs_parallel(clauses: list[dict], contract_id: str) -> dict:
	"""Compare sequential and parallel execution times for three analysis agents.

	Args:
		clauses: Extracted clause dictionaries.
		contract_id: Contract identifier.

	Returns:
		Comparison dictionary with timings, speedup metrics, and summary message.
	"""

	logger.info("Starting sequential vs parallel comparison for contract_id=%s", contract_id)

	sequential_start = time.time()
	risk_agent = RiskAssessmentAgent()
	compliance_agent = ComplianceAgent()
	negotiation_agent = NegotiationAgent()

	risk_result = risk_agent.process(clauses, contract_id)
	compliance_result = compliance_agent.process(clauses, contract_id, ["GENERAL"])
	negotiation_input = dataclasses.asdict(risk_result).get("clause_risks", [])
	_ = negotiation_agent.process(negotiation_input, contract_id, "balanced")
	sequential_time = time.time() - sequential_start

	parallel_start = time.time()
	_ = run_parallel_analysis(
		clauses=clauses,
		contract_id=contract_id,
		user_id=None,
		negotiation_stance="balanced",
		frameworks=["GENERAL"],
	)
	parallel_time = time.time() - parallel_start

	time_saved = sequential_time - parallel_time
	speedup_factor = sequential_time / parallel_time if parallel_time > 0 else float("inf")

	summary = (
		f"Sequential run took {sequential_time:.4f}s, parallel run took {parallel_time:.4f}s, "
		f"saving {time_saved:.4f}s with a {speedup_factor:.2f}x speedup."
	)

	logger.info("%s", summary)
	return {
		"sequential_time": sequential_time,
		"parallel_time": parallel_time,
		"time_saved": time_saved,
		"speedup_factor": speedup_factor,
		"summary": summary,
	}
