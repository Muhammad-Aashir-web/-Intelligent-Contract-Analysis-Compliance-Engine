"""LangGraph workflow for orchestrating end-to-end contract analysis."""

from __future__ import annotations

from dataclasses import asdict
import logging
import time
from typing import Annotated, TypedDict

from langgraph.graph import END, StateGraph

from agents.audit import AuditTrailAgent
from agents.compliance import ComplianceAgent
from agents.extraction import ClauseExtractionAgent
from agents.ingestion import DocumentIngestionAgent
from agents.negotiation import NegotiationAgent
from agents.risk import RiskAssessmentAgent

logger = logging.getLogger(__name__)

_INGESTION_AGENT = DocumentIngestionAgent()
_EXTRACTION_AGENT = ClauseExtractionAgent()
_RISK_AGENT = RiskAssessmentAgent()
_COMPLIANCE_AGENT = ComplianceAgent()
_NEGOTIATION_AGENT = NegotiationAgent()
_AUDIT_AGENT = AuditTrailAgent()


class ContractAnalysisState(TypedDict):
	"""Workflow state shared across all contract analysis nodes."""

	contract_id: str
	file_path: str
	user_id: str | None
	negotiation_stance: str
	frameworks: Annotated[list[str], "Compliance frameworks to evaluate"]
	ingestion_result: dict | None
	extraction_result: dict | None
	risk_result: dict | None
	compliance_result: dict | None
	negotiation_result: dict | None
	audit_entries: Annotated[list[dict], "Audit entries produced during execution"]
	current_step: str
	error: str | None
	start_time: float


def _safe_to_dict(value: object) -> object:
	"""Safely convert dataclass instances and nested structures to dictionaries."""

	if hasattr(value, "__dataclass_fields__"):
		return {key: _safe_to_dict(item) for key, item in asdict(value).items()}

	if isinstance(value, dict):
		return {key: _safe_to_dict(item) for key, item in value.items()}

	if isinstance(value, list):
		return [_safe_to_dict(item) for item in value]

	if isinstance(value, tuple):
		return [_safe_to_dict(item) for item in value]

	return value


def _append_audit_entry(state: ContractAnalysisState, entry: object) -> None:
	"""Append a serialized audit entry to workflow state."""

	serialized = _safe_to_dict(entry)
	if isinstance(serialized, dict):
		state["audit_entries"].append(serialized)


def ingest_document(state: ContractAnalysisState) -> ContractAnalysisState:
	"""Ingest contract document and produce cleaned text for downstream analysis."""

	state["current_step"] = "ingestion"
	step_start = time.time()
	logger.info("Workflow step started: ingest_document for contract_id=%s", state["contract_id"])

	start_entry = _AUDIT_AGENT.log_event(
		event_type="INGESTION_STARTED",
		contract_id=state["contract_id"],
		user_id=state["user_id"],
		agent_name="ingestion",
		status="started",
		details={"file_path": state["file_path"]},
		duration_seconds=None,
	)
	_append_audit_entry(state, start_entry)

	result = _INGESTION_AGENT.process(state["file_path"])
	result_dict = _safe_to_dict(result)
	state["ingestion_result"] = result_dict if isinstance(result_dict, dict) else None

	if isinstance(state["ingestion_result"], dict) and state["ingestion_result"].get("status") == "failed":
		state["error"] = str(state["ingestion_result"].get("error_message") or "Ingestion failed")

	duration = time.time() - step_start
	completion_event = "INGESTION_FAILED" if state["error"] else "INGESTION_COMPLETED"
	completion_status = "failed" if state["error"] else "completed"

	done_entry = _AUDIT_AGENT.log_event(
		event_type=completion_event,
		contract_id=state["contract_id"],
		user_id=state["user_id"],
		agent_name="ingestion",
		status=completion_status,
		details=state["ingestion_result"],
		duration_seconds=duration,
	)
	_append_audit_entry(state, done_entry)
	return state


def extract_clauses(state: ContractAnalysisState) -> ContractAnalysisState:
	"""Extract structured clauses from cleaned contract text."""

	if state["error"] is not None:
		logger.info("Skipping extract_clauses due to prior workflow error")
		return state

	state["current_step"] = "extraction"
	step_start = time.time()
	logger.info("Workflow step started: extract_clauses for contract_id=%s", state["contract_id"])

	start_entry = _AUDIT_AGENT.log_event(
		event_type="EXTRACTION_STARTED",
		contract_id=state["contract_id"],
		user_id=state["user_id"],
		agent_name="extraction",
		status="started",
		details=None,
		duration_seconds=None,
	)
	_append_audit_entry(state, start_entry)

	ingestion_result = state["ingestion_result"] or {}
	cleaned_text = str(ingestion_result.get("cleaned_text") or "")
	if not cleaned_text:
		state["error"] = "Missing cleaned_text from ingestion result"

	if state["error"] is None:
		result = _EXTRACTION_AGENT.process(cleaned_text, state["contract_id"])
		result_dict = _safe_to_dict(result)
		state["extraction_result"] = result_dict if isinstance(result_dict, dict) else None

		if isinstance(state["extraction_result"], dict) and state["extraction_result"].get("status") == "failed":
			state["error"] = str(state["extraction_result"].get("error_message") or "Extraction failed")

	duration = time.time() - step_start
	completion_event = "EXTRACTION_FAILED" if state["error"] else "EXTRACTION_COMPLETED"
	completion_status = "failed" if state["error"] else "completed"

	done_entry = _AUDIT_AGENT.log_event(
		event_type=completion_event,
		contract_id=state["contract_id"],
		user_id=state["user_id"],
		agent_name="extraction",
		status=completion_status,
		details=state["extraction_result"] if state["error"] is None else {"error": state["error"]},
		duration_seconds=duration,
	)
	_append_audit_entry(state, done_entry)
	return state


def assess_risk(state: ContractAnalysisState) -> ContractAnalysisState:
	"""Compute rule-based and AI-assisted risk analysis from extracted clauses."""

	if state["error"] is not None:
		logger.info("Skipping assess_risk due to prior workflow error")
		return state

	state["current_step"] = "risk_assessment"
	step_start = time.time()
	logger.info("Workflow step started: assess_risk for contract_id=%s", state["contract_id"])

	start_entry = _AUDIT_AGENT.log_event(
		event_type="RISK_ASSESSMENT_STARTED",
		contract_id=state["contract_id"],
		user_id=state["user_id"],
		agent_name="risk_assessment",
		status="started",
		details=None,
		duration_seconds=None,
	)
	_append_audit_entry(state, start_entry)

	extraction_result = state["extraction_result"] or {}
	clauses = extraction_result.get("clauses", []) if isinstance(extraction_result, dict) else []
	result = _RISK_AGENT.process(clauses, state["contract_id"])

	result_dict = _safe_to_dict(result)
	state["risk_result"] = result_dict if isinstance(result_dict, dict) else None
	if isinstance(state["risk_result"], dict) and state["risk_result"].get("status") == "failed":
		state["error"] = str(state["risk_result"].get("error_message") or "Risk assessment failed")

	duration = time.time() - step_start
	completion_event = "RISK_ASSESSMENT_FAILED" if state["error"] else "RISK_ASSESSMENT_COMPLETED"
	completion_status = "failed" if state["error"] else "completed"

	done_entry = _AUDIT_AGENT.log_event(
		event_type=completion_event,
		contract_id=state["contract_id"],
		user_id=state["user_id"],
		agent_name="risk_assessment",
		status=completion_status,
		details=state["risk_result"],
		duration_seconds=duration,
	)
	_append_audit_entry(state, done_entry)
	return state


def check_compliance(state: ContractAnalysisState) -> ContractAnalysisState:
	"""Evaluate extracted clauses against selected compliance frameworks."""

	if state["error"] is not None:
		logger.info("Skipping check_compliance due to prior workflow error")
		return state

	state["current_step"] = "compliance_check"
	step_start = time.time()
	logger.info("Workflow step started: check_compliance for contract_id=%s", state["contract_id"])

	start_entry = _AUDIT_AGENT.log_event(
		event_type="COMPLIANCE_CHECK_STARTED",
		contract_id=state["contract_id"],
		user_id=state["user_id"],
		agent_name="compliance_check",
		status="started",
		details={"frameworks": state["frameworks"]},
		duration_seconds=None,
	)
	_append_audit_entry(state, start_entry)

	extraction_result = state["extraction_result"] or {}
	clauses = extraction_result.get("clauses", []) if isinstance(extraction_result, dict) else []
	result = _COMPLIANCE_AGENT.process(clauses, state["contract_id"], state["frameworks"])

	result_dict = _safe_to_dict(result)
	state["compliance_result"] = result_dict if isinstance(result_dict, dict) else None
	if isinstance(state["compliance_result"], dict) and state["compliance_result"].get("status") == "failed":
		state["error"] = str(state["compliance_result"].get("error_message") or "Compliance check failed")

	duration = time.time() - step_start
	completion_event = "COMPLIANCE_CHECK_FAILED" if state["error"] else "COMPLIANCE_CHECK_COMPLETED"
	completion_status = "failed" if state["error"] else "completed"

	done_entry = _AUDIT_AGENT.log_event(
		event_type=completion_event,
		contract_id=state["contract_id"],
		user_id=state["user_id"],
		agent_name="compliance_check",
		status=completion_status,
		details=state["compliance_result"],
		duration_seconds=duration,
	)
	_append_audit_entry(state, done_entry)
	return state


def suggest_negotiations(state: ContractAnalysisState) -> ContractAnalysisState:
	"""Generate negotiation alternatives for high-risk clauses."""

	if state["error"] is not None:
		logger.info("Skipping suggest_negotiations due to prior workflow error")
		return state

	state["current_step"] = "negotiation"
	step_start = time.time()
	logger.info("Workflow step started: suggest_negotiations for contract_id=%s", state["contract_id"])

	start_entry = _AUDIT_AGENT.log_event(
		event_type="NEGOTIATION_STARTED",
		contract_id=state["contract_id"],
		user_id=state["user_id"],
		agent_name="negotiation",
		status="started",
		details={"negotiation_stance": state["negotiation_stance"]},
		duration_seconds=None,
	)
	_append_audit_entry(state, start_entry)

	risk_result = state["risk_result"] or {}
	clause_risks = risk_result.get("clause_risks", []) if isinstance(risk_result, dict) else []
	result = _NEGOTIATION_AGENT.process(
		clause_risks,
		state["contract_id"],
		state["negotiation_stance"],
	)

	result_dict = _safe_to_dict(result)
	state["negotiation_result"] = result_dict if isinstance(result_dict, dict) else None
	if isinstance(state["negotiation_result"], dict) and state["negotiation_result"].get("status") == "failed":
		state["error"] = str(state["negotiation_result"].get("error_message") or "Negotiation suggestions failed")

	duration = time.time() - step_start
	completion_event = "NEGOTIATION_FAILED" if state["error"] else "NEGOTIATION_COMPLETED"
	completion_status = "failed" if state["error"] else "completed"

	done_entry = _AUDIT_AGENT.log_event(
		event_type=completion_event,
		contract_id=state["contract_id"],
		user_id=state["user_id"],
		agent_name="negotiation",
		status=completion_status,
		details=state["negotiation_result"],
		duration_seconds=duration,
	)
	_append_audit_entry(state, done_entry)
	return state


def finalize_audit(state: ContractAnalysisState) -> ContractAnalysisState:
	"""Finalize workflow auditing and mark pipeline completion status."""

	state["current_step"] = "finalize_audit"
	total_processing_time = max(0.0, time.time() - state["start_time"])
	has_error = state["error"] is not None

	event_type = "ANALYSIS_PIPELINE_FAILED" if has_error else "ANALYSIS_PIPELINE_COMPLETED"
	status = "failed" if has_error else "completed"
	details = {
		"error": state["error"],
		"total_processing_time_seconds": total_processing_time,
	}

	logger.info(
		"Workflow finalizing for contract_id=%s status=%s duration=%.4fs",
		state["contract_id"],
		status,
		total_processing_time,
	)

	final_entry = _AUDIT_AGENT.log_event(
		event_type=event_type,
		contract_id=state["contract_id"],
		user_id=state["user_id"],
		agent_name="analysis_pipeline",
		status=status,
		details=details,
		duration_seconds=total_processing_time,
	)
	_append_audit_entry(state, final_entry)

	state["current_step"] = "completed"
	return state


def should_continue(state: ContractAnalysisState) -> str:
	"""Determine whether workflow should proceed or jump directly to finalization."""

	if state["error"] is not None:
		return "finalize_audit"
	return "continue"


def build_contract_analysis_graph() -> StateGraph:
	"""Build and compile the LangGraph state graph for contract analysis."""

	workflow = StateGraph(ContractAnalysisState)

	workflow.add_node("ingest_document", ingest_document)
	workflow.add_node("extract_clauses", extract_clauses)
	workflow.add_node("assess_risk", assess_risk)
	workflow.add_node("check_compliance", check_compliance)
	workflow.add_node("suggest_negotiations", suggest_negotiations)
	workflow.add_node("finalize_audit", finalize_audit)

	workflow.set_entry_point("ingest_document")

	workflow.add_conditional_edges(
		"ingest_document",
		should_continue,
		{
			"continue": "extract_clauses",
			"finalize_audit": "finalize_audit",
		},
	)

	workflow.add_conditional_edges(
		"extract_clauses",
		should_continue,
		{
			"continue": "assess_risk",
			"finalize_audit": "finalize_audit",
		},
	)

	workflow.add_edge("assess_risk", "check_compliance")
	workflow.add_edge("check_compliance", "suggest_negotiations")
	workflow.add_edge("suggest_negotiations", "finalize_audit")
	workflow.add_edge("finalize_audit", END)

	return workflow.compile()


def run_contract_analysis(
	file_path: str,
	contract_id: str,
	user_id: str | None = None,
	negotiation_stance: str = "balanced",
	frameworks: list[str] | None = None,
) -> dict:
	"""Run the full contract analysis workflow and return the final state."""

	selected_frameworks = frameworks if frameworks is not None else ["GENERAL"]

	initial_state: ContractAnalysisState = {
		"contract_id": contract_id,
		"file_path": file_path,
		"user_id": user_id,
		"negotiation_stance": negotiation_stance,
		"frameworks": selected_frameworks,
		"ingestion_result": None,
		"extraction_result": None,
		"risk_result": None,
		"compliance_result": None,
		"negotiation_result": None,
		"audit_entries": [],
		"current_step": "initialized",
		"error": None,
		"start_time": time.time(),
	}

	logger.info("Invoking contract analysis workflow for contract_id=%s", contract_id)
	graph = build_contract_analysis_graph()
	final_state = graph.invoke(initial_state)
	return dict(final_state)
