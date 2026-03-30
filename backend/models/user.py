from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from database import Base


def utc_now() -> datetime:
	"""Return the current UTC datetime for timestamp defaults."""
	return datetime.now(timezone.utc)


class User(Base):
	# Database table name used by SQLAlchemy for this model.
	__tablename__ = "users"

	# Primary key identifier for each user.
	id = Column(Integer, primary_key=True, index=True, autoincrement=True)

	# Email is unique, required, and indexed for fast lookups during auth.
	email = Column(String(255), unique=True, nullable=False, index=True)

	# Password hash (never store raw passwords).
	hashed_password = Column(String(255), nullable=False)

	# Optional profile metadata.
	full_name = Column(String(255), nullable=True)
	company = Column(String(255), nullable=True)

	# Role can be user, admin, or lawyer.
	role = Column(String(50), nullable=False, default="user")

	# Account status flags.
	is_active = Column(Boolean, nullable=False, default=True)
	is_verified = Column(Boolean, nullable=False, default=False)

	# Audit timestamps in UTC.
	created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
	updated_at = Column(
		DateTime(timezone=True),
		nullable=False,
		default=utc_now,
		onupdate=utc_now,
	)

	# One user can have many contracts.
	contracts = relationship("Contract", back_populates="user")

	def __repr__(self) -> str:
		return f"User(id={self.id}, email='{self.email}')"
