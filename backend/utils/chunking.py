"""Utilities for smart text chunking strategies."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def _split_sentences(text: str) -> list[str]:
	"""Split text into sentence-like units using punctuation and newlines."""

	if not text:
		return []

	parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
	return [part.strip() for part in parts if part and part.strip()]


def _find_word_boundary_end(text: str, start: int, target_end: int) -> int:
	"""Find a safe chunk end that does not split in the middle of a word."""

	text_length = len(text)
	if target_end >= text_length:
		return text_length

	if text[target_end].isspace():
		return target_end

	probe = target_end
	while probe > start and not text[probe - 1].isspace():
		probe -= 1

	if probe > start:
		return probe

	probe = target_end
	while probe < text_length and not text[probe].isspace():
		probe += 1

	return probe


def chunk_by_size(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
	"""Split text into overlapping chunks by character count.

	The function preserves whole words and avoids splitting in the middle of
	a word, even if that occasionally makes a chunk exceed ``chunk_size``.

	Args:
		text: Input text to chunk.
		chunk_size: Target maximum characters per chunk.
		overlap: Number of overlapping characters between adjacent chunks.

	Returns:
		List of chunk strings.

	Raises:
		ValueError: If ``chunk_size`` is not positive or ``overlap`` is invalid.
	"""

	if not text or not text.strip():
		return []

	if chunk_size <= 0:
		raise ValueError("chunk_size must be greater than 0")

	if overlap < 0 or overlap >= chunk_size:
		raise ValueError("overlap must be non-negative and smaller than chunk_size")

	logger.info(
		"Chunking text by size with chunk_size=%s overlap=%s", chunk_size, overlap
	)

	chunks: list[str] = []
	text_length = len(text)
	start = 0

	while start < text_length:
		while start < text_length and text[start].isspace():
			start += 1

		if start >= text_length:
			break

		target_end = min(start + chunk_size, text_length)
		end = _find_word_boundary_end(text, start, target_end)
		chunk = text[start:end].strip()
		if chunk:
			chunks.append(chunk)

		if end >= text_length:
			break

		next_start = max(end - overlap, 0)
		if next_start <= start:
			next_start = end

		while (
			next_start < text_length
			and next_start > 0
			and not text[next_start - 1].isspace()
		):
			next_start += 1

		start = next_start

	logger.info("Created %s size-based chunks", len(chunks))
	return chunks


def chunk_by_sentence(text: str, sentences_per_chunk: int = 10) -> list[str]:
	"""Split text into sentence-based chunks.

	Sentences are detected with simple punctuation and newline boundaries,
	then grouped into chunks of ``sentences_per_chunk`` items.

	Args:
		text: Input text to chunk.
		sentences_per_chunk: Number of sentences per returned chunk.

	Returns:
		List of sentence-group chunks.

	Raises:
		ValueError: If ``sentences_per_chunk`` is not positive.
	"""

	if not text or not text.strip():
		return []

	if sentences_per_chunk <= 0:
		raise ValueError("sentences_per_chunk must be greater than 0")

	sentences = _split_sentences(text)
	logger.info(
		"Chunking text by sentence with %s detected sentences and %s per chunk",
		len(sentences),
		sentences_per_chunk,
	)

	chunks: list[str] = []
	for index in range(0, len(sentences), sentences_per_chunk):
		group = sentences[index : index + sentences_per_chunk]
		chunk = " ".join(group).strip()
		if chunk:
			chunks.append(chunk)

	logger.info("Created %s sentence-based chunks", len(chunks))
	return chunks


def chunk_by_paragraph(text: str, max_chunk_size: int = 2000) -> list[str]:
	"""Split text by paragraph boundaries with smart fallback for long sections.

	The function splits on double newlines. Paragraphs larger than
	``max_chunk_size`` are broken down by sentences (and then by size only if
	a single sentence remains too large). Small consecutive paragraphs are
	merged when their combined size is below ``max_chunk_size``.

	Args:
		text: Input text to chunk.
		max_chunk_size: Maximum characters allowed in each paragraph chunk.

	Returns:
		List of paragraph-aware chunks.

	Raises:
		ValueError: If ``max_chunk_size`` is not positive.
	"""

	if not text or not text.strip():
		return []

	if max_chunk_size <= 0:
		raise ValueError("max_chunk_size must be greater than 0")

	logger.info("Chunking text by paragraph with max_chunk_size=%s", max_chunk_size)

	paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text.strip()) if part and part.strip()]
	normalized_paragraphs: list[str] = []

	for paragraph in paragraphs:
		if len(paragraph) <= max_chunk_size:
			normalized_paragraphs.append(paragraph)
			continue

		sentence_units = _split_sentences(paragraph)
		sentence_buffer: list[str] = []

		for sentence in sentence_units:
			if len(sentence) > max_chunk_size:
				if sentence_buffer:
					normalized_paragraphs.append(" ".join(sentence_buffer).strip())
					sentence_buffer = []

				normalized_paragraphs.extend(
					chunk_by_size(sentence, chunk_size=max_chunk_size, overlap=0)
				)
				continue

			candidate = (
				f"{' '.join(sentence_buffer)} {sentence}".strip()
				if sentence_buffer
				else sentence
			)

			if len(candidate) <= max_chunk_size:
				sentence_buffer.append(sentence)
			else:
				normalized_paragraphs.append(" ".join(sentence_buffer).strip())
				sentence_buffer = [sentence]

		if sentence_buffer:
			normalized_paragraphs.append(" ".join(sentence_buffer).strip())

	merged_chunks: list[str] = []
	current = ""

	for paragraph in normalized_paragraphs:
		if not current:
			current = paragraph
			continue

		candidate = f"{current}\n\n{paragraph}"
		if len(candidate) <= max_chunk_size:
			current = candidate
		else:
			merged_chunks.append(current)
			current = paragraph

	if current:
		merged_chunks.append(current)

	logger.info("Created %s paragraph-based chunks", len(merged_chunks))
	return merged_chunks
