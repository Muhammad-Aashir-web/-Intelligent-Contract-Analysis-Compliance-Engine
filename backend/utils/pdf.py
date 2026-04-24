"""Utilities for extracting text from supported document types."""

from __future__ import annotations

import logging
from pathlib import Path

try:
	import fitz
except ImportError:  # pragma: no cover - environment-specific dependency handling
	fitz = None

try:
	from docx import Document
except ImportError:  # pragma: no cover - environment-specific dependency handling
	Document = None

try:
	from PIL import Image
except ImportError:  # pragma: no cover - environment-specific dependency handling
	Image = None

try:
	import pytesseract
except ImportError:  # pragma: no cover - environment-specific dependency handling
	pytesseract = None

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def _require_dependency(module: object, dependency_name: str) -> object:
	"""Return an imported dependency or raise a helpful ImportError."""

	if module is None:
		raise ImportError(
			f"{dependency_name} is required for this extractor. Install the backend dependencies and try again."
		)
	return module


def _normalize_text(text: str) -> str:
	"""Return text without leading/trailing whitespace when content exists."""

	return text.strip()


def extract_text_from_pdf(file_path: str) -> str:
	"""Extract text from a PDF file.

	Text is extracted from each page with PyMuPDF. If a page has no embedded
	text, the page is rendered to an image and OCR is applied with Tesseract.

	Args:
		file_path: Path to the PDF file.

	Returns:
		The combined text extracted from all pages.
	"""

	logger.info("Extracting text from PDF: %s", file_path)
	fitz_module = _require_dependency(fitz, "PyMuPDF (fitz)")
	image_module = _require_dependency(Image, "Pillow")
	tesseract_module = _require_dependency(pytesseract, "pytesseract")
	extracted_pages: list[str] = []

	with fitz_module.open(file_path) as document:
		for page_number, page in enumerate(document, start=1):
			logger.info("Processing PDF page %s of %s", page_number, document.page_count)
			page_text = _normalize_text(page.get_text("text"))

			if page_text:
				extracted_pages.append(page_text)
				continue

			logger.info("No embedded text found on page %s; running OCR", page_number)
			pixmap = page.get_pixmap(matrix=fitz_module.Matrix(2, 2), alpha=False, colorspace=fitz_module.csRGB)
			page_image = image_module.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
			ocr_text = _normalize_text(tesseract_module.image_to_string(page_image))
			if ocr_text:
				extracted_pages.append(ocr_text)

	return "\n\n".join(extracted_pages)


def extract_text_from_docx(file_path: str) -> str:
	"""Extract text from a DOCX file.

	All paragraphs and table cell text are collected and returned as a single
	combined string.

	Args:
		file_path: Path to the DOCX file.

	Returns:
		The combined text extracted from the document.

	Raises:
		ValueError: If the input is a legacy .doc file.
	"""

	document_path = Path(file_path)
	if document_path.suffix.lower() == ".doc":
		raise ValueError("Legacy .doc files are not supported; convert the file to .docx.")

	logger.info("Extracting text from DOCX: %s", file_path)
	document_module = _require_dependency(Document, "python-docx")
	document = document_module(file_path)
	extracted_parts: list[str] = []

	for paragraph in document.paragraphs:
		paragraph_text = _normalize_text(paragraph.text)
		if paragraph_text:
			extracted_parts.append(paragraph_text)

	for table_index, table in enumerate(document.tables, start=1):
		logger.info("Processing DOCX table %s", table_index)
		for row in table.rows:
			for cell in row.cells:
				cell_text = _normalize_text(cell.text)
				if cell_text:
					extracted_parts.append(cell_text)

	return "\n\n".join(extracted_parts)


def extract_text_from_image(file_path: str) -> str:
	"""Extract text from an image file with Tesseract OCR.

	Args:
		file_path: Path to the image file.

	Returns:
		The OCR-extracted text.
	"""

	logger.info("Extracting text from image: %s", file_path)
	image_module = _require_dependency(Image, "Pillow")
	tesseract_module = _require_dependency(pytesseract, "pytesseract")
	with image_module.open(file_path) as image:
		text = tesseract_module.image_to_string(image)
	return _normalize_text(text)


def extract_text(file_path: str) -> str:
	"""Extract text from a supported document based on file extension.

	Args:
		file_path: Path to the file.

	Returns:
		The combined text extracted from the file.

	Raises:
		ValueError: If the file type is unsupported.
	"""

	extension = Path(file_path).suffix.lower()
	logger.info("Detecting file type for text extraction: %s", file_path)

	if extension == ".pdf":
		return extract_text_from_pdf(file_path)

	if extension == ".docx":
		return extract_text_from_docx(file_path)

	if extension == ".doc":
		raise ValueError("Legacy .doc files are not supported; convert the file to .docx.")

	if extension in _IMAGE_EXTENSIONS:
		return extract_text_from_image(file_path)

	raise ValueError(f"Unsupported file type: {extension or 'unknown'}")
