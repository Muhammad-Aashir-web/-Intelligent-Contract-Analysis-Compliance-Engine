"""Utilities for contract clause risk scoring and summary metrics."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_HIGH_RISK_TYPES = {
	"liability_cap",
	"indemnification",
	"termination_for_convenience",
	"non_compete",
	"ip_ownership",
}
_MEDIUM_RISK_TYPES = {
	"payment_terms",
	"penalties",
	"arbitration",
	"governing_law",
	"assignment",
}
_LOW_RISK_TYPES = {
	"entire_agreement",
	"severability",
	"waiver",
	"notice_period",
	"amendment_process",
}

_RISKY_KEYWORDS = ["unlimited liability", "sole discretion", "irrevocable"]
_SAFE_KEYWORDS = ["mutual", "reasonable", "both parties"]


def _clamp_score(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
	"""Clamp a floating-point value to a closed interval."""

	return max(minimum, min(maximum, value))


def calculate_clause_risk_score(clause_type: str, clause_text: str) -> float:
	"""Calculate a rule-based risk score for a clause.

	Args:
		clause_type: Normalized clause type identifier.
		clause_text: Raw clause text for keyword-based risk adjustments.

	Returns:
		Risk score in the range 0.0 to 1.0.
	"""

	normalized_type = clause_type.strip().lower()
	normalized_text = clause_text.lower()

	if normalized_type in _HIGH_RISK_TYPES:
		score = 0.8
	elif normalized_type in _MEDIUM_RISK_TYPES:
		score = 0.5
	elif normalized_type in _LOW_RISK_TYPES:
		score = 0.2
	else:
		score = 0.5

	if any(keyword in normalized_text for keyword in _RISKY_KEYWORDS):
		score += 0.15

	if any(keyword in normalized_text for keyword in _SAFE_KEYWORDS):
		score -= 0.1

	final_score = _clamp_score(score)
	logger.info(
		"Calculated clause risk score type=%s score=%.3f", normalized_type or "unknown", final_score
	)
	return final_score


def calculate_overall_risk(clause_scores: list[float]) -> dict:
	"""Aggregate individual clause scores into an overall contract risk profile.

	Overall score is a weighted average where higher individual risks receive
	higher weights.

	Thresholds:
	- LOW: score < 0.3
	- MEDIUM: score < 0.6
	- HIGH: score < 0.8
	- CRITICAL: score >= 0.8

	Args:
		clause_scores: List of individual clause risk scores.

	Returns:
		Dictionary with overall score, level, distribution, and thresholds used.
	"""

	if not clause_scores:
		logger.info("No clause scores provided; returning zero-risk defaults")
		return {
			"overall_score": 0.0,
			"risk_level": "LOW",
			"risk_distribution": {
				"low": 0,
				"medium": 0,
				"high": 0,
				"critical": 0,
			},
			"thresholds_used": {
				"low_lt": 0.3,
				"medium_lt": 0.6,
				"high_lt": 0.8,
				"critical_gte": 0.8,
			},
		}

	normalized_scores = [_clamp_score(float(score)) for score in clause_scores]

	weights = [1.0 + score for score in normalized_scores]
	weighted_sum = sum(score * weight for score, weight in zip(normalized_scores, weights))
	total_weight = sum(weights)
	overall_score = weighted_sum / total_weight if total_weight else 0.0

	distribution = {
		"low": 0,
		"medium": 0,
		"high": 0,
		"critical": 0,
	}

	for score in normalized_scores:
		if score < 0.3:
			distribution["low"] += 1
		elif score < 0.6:
			distribution["medium"] += 1
		elif score < 0.8:
			distribution["high"] += 1
		else:
			distribution["critical"] += 1

	if overall_score < 0.3:
		risk_level = "LOW"
	elif overall_score < 0.6:
		risk_level = "MEDIUM"
	elif overall_score < 0.8:
		risk_level = "HIGH"
	else:
		risk_level = "CRITICAL"

	result = {
		"overall_score": round(overall_score, 4),
		"risk_level": risk_level,
		"risk_distribution": distribution,
		"thresholds_used": {
			"low_lt": 0.3,
			"medium_lt": 0.6,
			"high_lt": 0.8,
			"critical_gte": 0.8,
		},
	}
	logger.info(
		"Calculated overall risk score=%.3f level=%s", result["overall_score"], result["risk_level"]
	)
	return result


def format_risk_summary(overall_risk: dict, top_risks: list[dict]) -> str:
	"""Create a markdown summary for contract risk findings.

	Args:
		overall_risk: Aggregated risk dictionary from ``calculate_overall_risk``.
		top_risks: List of clause dictionaries ordered by descending risk.

	Returns:
		Human-readable markdown summary including overall status and top clauses.
	"""

	overall_score = float(overall_risk.get("overall_score", 0.0))
	risk_level = str(overall_risk.get("risk_level", "LOW"))

	lines = [
		"## Contract Risk Summary",
		"",
		f"- Overall Score: **{overall_score:.2f}**",
		f"- Risk Level: **{risk_level}**",
		"",
		"### Top Risky Clauses",
	]

	top_three = top_risks[:3]
	if not top_three:
		lines.append("- No high-risk clauses identified.")
	else:
		for index, item in enumerate(top_three, start=1):
			clause_type = str(item.get("clause_type", "unknown"))
			score = float(item.get("risk_score", item.get("confidence", 0.0)))
			summary = str(item.get("summary", "No summary available.")).strip()
			lines.append(
				f"{index}. **{clause_type}** (score: {score:.2f}) - {summary}"
			)

	summary_text = "\n".join(lines)
	logger.info("Formatted risk summary with %s top risk entries", len(top_three))
	return summary_text
