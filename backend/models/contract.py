from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


def utc_now() -> datetime:
	"""Return the current UTC datetime for timestamp defaults."""
	return datetime.now(timezone.utc)


class Contract(Base):
	# Database table name used by SQLAlchemy for this model.
	__tablename__ = "contracts"

	# Additional indexes for frequent filtering by owner and processing status.
	__table_args__ = (
		Index("ix_contracts_user_id", "user_id"),
		Index("ix_contracts_status", "status"),
	)

	# Primary key identifier for each contract record.
	id = Column(Integer, primary_key=True, index=True, autoincrement=True)

	# Core file metadata.
	title = Column(String(500), nullable=False)
	file_name = Column(String(500), nullable=False)
	file_path = Column(String(1000), nullable=True)
	file_size = Column(Integer, nullable=True)

	# Contract classification fields.
	contract_type = Column(String(100), nullable=True)
	jurisdiction = Column(String(100), nullable=True)

	# Processing state and risk analysis outputs.
	status = Column(String(50), nullable=False, default="pending")
	risk_score = Column(Float, nullable=True)
	risk_level = Column(String(20), nullable=True)
	summary = Column(Text, nullable=True)
	raw_text = Column(Text, nullable=True)

	# Owner relationship key to users table.
	user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

	# Audit and processing timestamps in UTC.
	created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
	updated_at = Column(
		DateTime(timezone=True),
		nullable=False,
		default=utc_now,
		onupdate=utc_now,
	)
	processed_at = Column(DateTime(timezone=True), nullable=True)

	# ORM relationships.
	user = relationship("User", back_populates="contracts")
	clauses = relationship("Clause", back_populates="contract")

	def __repr__(self) -> str:
		return f"Contract(id={self.id}, title='{self.title}')"
