from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


def utc_now() -> datetime:
	"""Return the current UTC datetime for timestamp defaults."""
	return datetime.now(timezone.utc)


class Clause(Base):
	# Database table name used by SQLAlchemy for this model.
	__tablename__ = "clauses"

	# Additional indexes for common filtering by contract and clause category.
	__table_args__ = (
		Index("ix_clauses_contract_id", "contract_id"),
		Index("ix_clauses_clause_type", "clause_type"),
	)

	# Primary key identifier for each clause.
	id = Column(Integer, primary_key=True, index=True, autoincrement=True)

	# Link each clause to a parent contract.
	contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)

	# Clause classification and source location metadata.
	clause_type = Column(String(100), nullable=False)
	clause_text = Column(Text, nullable=False)
	page_number = Column(Integer, nullable=True)
	position_start = Column(Integer, nullable=True)
	position_end = Column(Integer, nullable=True)

	# Risk and compliance analysis outputs.
	risk_score = Column(Float, nullable=True)
	risk_level = Column(String(20), nullable=True)
	risk_explanation = Column(Text, nullable=True)
	compliance_status = Column(String(50), nullable=True)
	compliance_notes = Column(Text, nullable=True)
	negotiation_suggestion = Column(Text, nullable=True)

	# Flag indicates whether this clause needs special review.
	is_flagged = Column(Boolean, nullable=False, default=False)

	# Creation timestamp in UTC.
	created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

	# ORM relationship back to the parent contract.
	contract = relationship("Contract", back_populates="clauses")

	def __repr__(self) -> str:
		return f"Clause(id={self.id}, clause_type='{self.clause_type}')"
