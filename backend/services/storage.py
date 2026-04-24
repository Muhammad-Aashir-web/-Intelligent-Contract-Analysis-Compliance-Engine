"""File storage service for upload validation and persistence."""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
import shutil
import uuid

from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".tiff"}
MAX_FILE_SIZE = 50 * 1024 * 1024
UPLOAD_DIR = Path("../data/uploads")


class FileStorageService:
	"""Handle file upload validation, storage, lookup, and deletion operations."""

	def __init__(self) -> None:
		"""Initialize upload storage configuration and ensure base directory exists."""

		load_dotenv()
		self.logger = logging.getLogger(__name__)

		base_path = Path(__file__).resolve().parent
		override_dir = os.getenv("UPLOAD_DIR")
		configured_dir = Path(override_dir) if override_dir else UPLOAD_DIR
		self.upload_dir = (base_path / configured_dir).resolve() if not configured_dir.is_absolute() else configured_dir

		try:
			self.upload_dir.mkdir(parents=True, exist_ok=True)
			self.logger.info("FileStorageService initialized at %s", self.upload_dir)
		except Exception as exc:
			self.logger.exception("Failed to initialize upload directory")
			raise RuntimeError(f"Failed to initialize upload directory: {exc}") from exc

	async def save_upload(self, file: UploadFile, contract_id: str) -> dict[str, str | int]:
		"""Validate and persist an uploaded file under its contract-specific directory.

		Args:
			file: FastAPI upload file object.
			contract_id: Contract identifier used to namespace uploaded files.

		Returns:
			Dictionary containing saved file metadata and integrity hash.

		Raises:
			HTTPException: If validation fails or file cannot be saved.
		"""

		validation = self.validate_file(file)
		if not validation["is_valid"]:
			raise HTTPException(status_code=400, detail=str(validation["error"]))

		file_name = str(validation["file_name"])
		extension = str(validation["extension"])

		try:
			content = await file.read()
		except Exception as exc:
			self.logger.exception("Failed to read upload content for contract_id=%s", contract_id)
			raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {exc}") from exc

		file_size = len(content)
		if file_size > MAX_FILE_SIZE:
			self.logger.warning(
				"Upload rejected for contract_id=%s file=%s size=%s exceeds max=%s",
				contract_id,
				file_name,
				file_size,
				MAX_FILE_SIZE,
			)
			raise HTTPException(status_code=400, detail="File size exceeds 50MB limit")

		contract_dir = self.upload_dir / str(contract_id)
		contract_dir = contract_dir.resolve()
		try:
			contract_dir.mkdir(parents=True, exist_ok=True)
		except Exception as exc:
			self.logger.exception("Failed to create contract upload directory for contract_id=%s", contract_id)
			raise HTTPException(status_code=400, detail=f"Failed to prepare upload directory: {exc}") from exc

		safe_name = Path(file_name).name
		target_path = contract_dir / safe_name

		if target_path.exists():
			stem = target_path.stem
			suffix = target_path.suffix
			target_path = contract_dir / f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"
			safe_name = target_path.name

		try:
			with target_path.open("wb") as out_file:
				out_file.write(content)
		except Exception as exc:
			self.logger.exception("Failed to persist upload for contract_id=%s", contract_id)
			raise HTTPException(status_code=400, detail=f"Failed to save uploaded file: {exc}") from exc
		finally:
			try:
				await file.close()
			except Exception:
				self.logger.debug("Upload file close failed for contract_id=%s", contract_id)

		md5_hash = hashlib.md5(content).hexdigest()
		result = {
			"contract_id": str(contract_id),
			"file_path": str(target_path.resolve()),
			"file_name": safe_name,
			"file_size": file_size,
			"file_type": extension,
			"md5_hash": md5_hash,
			"status": "saved",
		}
		self.logger.info(
			"File saved for contract_id=%s file=%s size=%s path=%s",
			contract_id,
			safe_name,
			file_size,
			target_path,
		)
		return result

	def validate_file(self, file: UploadFile) -> dict[str, bool | str | None]:
		"""Validate uploaded file metadata including extension allowlist.

		Args:
			file: FastAPI upload file object.

		Returns:
			Validation details with status and any error message.
		"""

		file_name = Path(file.filename or "").name
		extension = Path(file_name).suffix.lower()

		if not file_name:
			return {
				"is_valid": False,
				"file_name": "",
				"extension": extension,
				"error": "File name is missing",
			}

		if extension not in ALLOWED_EXTENSIONS:
			self.logger.warning("Invalid file extension received file=%s extension=%s", file_name, extension)
			return {
				"is_valid": False,
				"file_name": file_name,
				"extension": extension,
				"error": f"Invalid file type: {extension}",
			}

		return {
			"is_valid": True,
			"file_name": file_name,
			"extension": extension,
			"error": None,
		}

	def delete_upload(self, contract_id: str) -> dict[str, str | int]:
		"""Delete all uploaded files for a contract.

		Args:
			contract_id: Contract identifier.

		Returns:
			Deletion metadata with file count and status.
		"""

		contract_dir = (self.upload_dir / str(contract_id)).resolve()
		if not contract_dir.exists() or not contract_dir.is_dir():
			return {"contract_id": str(contract_id), "status": "not_found", "files_deleted": 0}

		try:
			files_deleted = sum(1 for item in contract_dir.rglob("*") if item.is_file())
			shutil.rmtree(contract_dir)
			self.logger.info("Deleted upload directory for contract_id=%s files_deleted=%s", contract_id, files_deleted)
			return {
				"contract_id": str(contract_id),
				"status": "deleted",
				"files_deleted": files_deleted,
			}
		except Exception as exc:
			self.logger.exception("Failed to delete upload directory for contract_id=%s", contract_id)
			return {
				"contract_id": str(contract_id),
				"status": f"error: {exc}",
				"files_deleted": 0,
			}

	def get_file_path(self, contract_id: str, file_name: str) -> str | None:
		"""Return absolute path for a contract file if present.

		Args:
			contract_id: Contract identifier.
			file_name: File name to locate.

		Returns:
			Absolute file path if found, otherwise None.
		"""

		candidate = (self.upload_dir / str(contract_id) / Path(file_name).name).resolve()
		try:
			if candidate.exists() and candidate.is_file():
				return str(candidate)
			return None
		except Exception:
			self.logger.exception("Failed file path lookup for contract_id=%s file=%s", contract_id, file_name)
			return None

	def list_uploads(self, contract_id: str) -> list[dict[str, str | int]]:
		"""List uploaded files and metadata for a contract.

		Args:
			contract_id: Contract identifier.

		Returns:
			List of dictionaries with file_name, file_size, and absolute file_path.
		"""

		contract_dir = (self.upload_dir / str(contract_id)).resolve()
		if not contract_dir.exists() or not contract_dir.is_dir():
			return []

		uploads: list[dict[str, str | int]] = []
		try:
			for path in sorted(contract_dir.iterdir()):
				if not path.is_file():
					continue
				uploads.append(
					{
						"file_name": path.name,
						"file_size": path.stat().st_size,
						"file_path": str(path.resolve()),
					}
				)
			return uploads
		except Exception:
			self.logger.exception("Failed to list uploads for contract_id=%s", contract_id)
			return []

	def format_file_size(self, size_bytes: int) -> str:
		"""Format byte size to a human-readable string.

		Args:
			size_bytes: Raw file size in bytes.

		Returns:
			Human-readable size string, for example 1.5 MB.
		"""

		if size_bytes == 1:
			return "1 byte"
		if size_bytes < 1024:
			return f"{size_bytes} bytes"

		units = ["KB", "MB", "GB", "TB"]
		size_value = float(size_bytes)
		for unit in units:
			size_value /= 1024.0
			if size_value < 1024.0 or unit == units[-1]:
				if abs(size_value - int(size_value)) < 0.01:
					return f"{int(size_value)} {unit}"
				return f"{size_value:.1f} {unit}"

		return f"{size_bytes} bytes"
