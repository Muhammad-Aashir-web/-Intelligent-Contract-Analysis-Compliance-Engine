"""Document ingestion agent for contract text extraction and preprocessing."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re

from utils.pdf import extract_text


@dataclass
class IngestionResult:
	"""Structured output for a document ingestion run."""

	file_path: str
	file_name: str
	file_type: str
	raw_text: str
	cleaned_text: str
	chunks: list[str]
	page_count: int
	word_count: int
	char_count: int
	status: str
	error_message: str | None


class DocumentIngestionAgent:
	"""Ingest documents by validating, extracting, cleaning, and chunking text."""

	_SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".tiff"}

	def __init__(self) -> None:
		"""Initialize the ingestion agent with a module logger."""

		self.logger = logging.getLogger(__name__)

	def process(self, file_path: str) -> IngestionResult:
		"""Process a document path and return a structured ingestion result.

		Args:
			file_path: Absolute or relative path to the document.

		Returns:
			IngestionResult containing extraction artifacts and metadata.
		"""

		path = Path(file_path)
		file_name = path.name
		file_type = path.suffix.lower()

		self.logger.info("Starting ingestion for file: %s", file_path)

		try:
			if not path.exists() or not path.is_file():
				raise FileNotFoundError(f"File not found: {file_path}")

			if file_type not in self._SUPPORTED_EXTENSIONS:
				raise ValueError(f"Unsupported file type: {file_type or 'unknown'}")

			raw_text = extract_text(str(path))
			cleaned_text = self._clean_text(raw_text)
			chunks = self._chunk_text(cleaned_text)
			word_count = len(cleaned_text.split())
			char_count = len(cleaned_text)
			page_count = len(raw_text) // 3000 + 1

			self.logger.info(
				"Ingestion complete for %s with %s chunks", file_name, len(chunks)
			)

			return IngestionResult(
				file_path=str(path),
				file_name=file_name,
				file_type=file_type,
				raw_text=raw_text,
				cleaned_text=cleaned_text,
				chunks=chunks,
				page_count=page_count,
				word_count=word_count,
				char_count=char_count,
				status="success",
				error_message=None,
			)

		except Exception as exc:
			self.logger.info("Ingestion failed for %s: %s", file_path, exc)
			return IngestionResult(
				file_path=str(path),
				file_name=file_name,
				file_type=file_type,
				raw_text="",
				cleaned_text="",
				chunks=[],
				page_count=0,
				word_count=0,
				char_count=0,
				status="failed",
				error_message=str(exc),
			)

	def _clean_text(self, text: str) -> str:
		"""Normalize extracted text for downstream chunking and storage.

		Cleaning rules:
		- Remove null bytes and non-printable characters.
		- Collapse repeated whitespace while preserving line breaks.
		- Keep at most two consecutive newline characters.
		- Strip leading and trailing whitespace.

		Args:
			text: Raw extracted text.

		Returns:
			Cleaned text.
		"""

		cleaned = text.replace("\x00", "")
		cleaned = "".join(ch for ch in cleaned if ch.isprintable() or ch in {"\n", "\t"})
		cleaned = re.sub(r"[^\S\n]+", " ", cleaned)
		cleaned = re.sub(r"\n[ \t]+", "\n", cleaned)
		cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
		cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
		return cleaned.strip()

	def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
		"""Split text into overlapping chunks for vector storage.

		Args:
			text: Cleaned text to chunk.
			chunk_size: Maximum number of characters per chunk.
			overlap: Number of overlapping characters between chunks.

		Returns:
			List of text chunks.

		Raises:
			ValueError: If chunk_size is not positive or overlap is invalid.
		"""

		if not text:
			return []

		if chunk_size <= 0:
			raise ValueError("chunk_size must be greater than 0")

		if overlap < 0 or overlap >= chunk_size:
			raise ValueError("overlap must be non-negative and smaller than chunk_size")

		chunks: list[str] = []
		step = chunk_size - overlap
		start = 0

		while start < len(text):
			end = start + chunk_size
			chunk = text[start:end].strip()
			if chunk:
				chunks.append(chunk)
			start += step

		return chunks
