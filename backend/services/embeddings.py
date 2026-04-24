"""Embedding orchestration service for contract analysis workflows."""

from __future__ import annotations

import logging
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

from services.vector_store import PineconeVectorStore
from services.weaviate_store import WeaviateVectorStore

logger = logging.getLogger(__name__)


class EmbeddingsService:
	"""Coordinate document and clause embeddings across Pinecone and Weaviate."""

	def __init__(self) -> None:
		"""Initialize embedding clients and backing vector stores."""

		load_dotenv()

		openai_api_key = os.getenv("OPENAI_API_KEY")
		self.embedding_model = "text-embedding-3-small"
		self.openai_client = OpenAI(api_key=openai_api_key)
		self.pinecone: PineconeVectorStore | None = None
		self.weaviate: WeaviateVectorStore | None = None

		pinecone_error = None
		weaviate_error = None

		try:
			self.pinecone = PineconeVectorStore()
		except Exception as exc:
			pinecone_error = str(exc)
			logger.warning("PineconeVectorStore initialization failed: %s", exc)

		try:
			self.weaviate = WeaviateVectorStore()
		except Exception as exc:
			weaviate_error = str(exc)
			logger.warning("WeaviateVectorStore initialization failed: %s", exc)

		logger.info(
			"EmbeddingsService initialized (pinecone=%s, weaviate=%s)",
			"ready" if self.pinecone is not None else "unavailable",
			"ready" if self.weaviate is not None else "unavailable",
		)

		self.initialization_status = {
			"pinecone": "success" if self.pinecone is not None else "failed",
			"weaviate": "success" if self.weaviate is not None else "failed",
			"pinecone_error": pinecone_error,
			"weaviate_error": weaviate_error,
		}

	def embed_and_store_document(
		self,
		contract_id: str,
		chunks: list[str],
		metadata: dict | None = None,
	) -> dict:
		"""Store contract chunks in Pinecone for full-text search.

		Weaviate is intentionally skipped here because clauses are stored separately.
		"""

		start_time = time.time()
		pinecone_status = "skipped"
		weaviate_status = "skipped"

		try:
			if self.pinecone is None:
				raise RuntimeError("PineconeVectorStore is unavailable")

			result = self.pinecone.upsert_document(
				contract_id=contract_id,
				chunks=chunks,
				metadata=metadata,
			)
			pinecone_status = str(result.get("status", "failed"))
			logger.info(
				"Stored %s document chunks in Pinecone for contract_id=%s",
				len(chunks),
				contract_id,
			)
		except Exception as exc:
			pinecone_status = "failed"
			logger.exception("Failed to store document chunks in Pinecone for contract_id=%s", contract_id)
			logger.warning("Pinecone document embedding error: %s", exc)

		total_duration = time.time() - start_time
		if pinecone_status == "success":
			overall_status = "success"
		elif pinecone_status == "failed":
			overall_status = "failed"
		else:
			overall_status = "partial"

		return {
			"contract_id": contract_id,
			"chunks_embedded": len(chunks),
			"pinecone_status": pinecone_status,
			"weaviate_status": weaviate_status,
			"total_duration": total_duration,
			"status": overall_status,
		}

	def embed_and_store_clauses(
		self,
		contract_id: str,
		clauses: list[dict],
	) -> dict:
		"""Store extracted clauses in Weaviate and mirror clause text in Pinecone."""

		start_time = time.time()
		pinecone_status = "skipped"
		weaviate_status = "skipped"
		clauses_embedded = len(clauses)

		clause_chunks = [str(clause.get("clause_text", "")).strip() for clause in clauses if str(clause.get("clause_text", "")).strip()]

		try:
			if self.weaviate is None:
				raise RuntimeError("WeaviateVectorStore is unavailable")

			weaviate_result = self.weaviate.upsert_clauses(contract_id=contract_id, clauses=clauses)
			weaviate_status = str(weaviate_result.get("status", "failed"))
			logger.info(
				"Stored %s clauses in Weaviate for contract_id=%s",
				clauses_embedded,
				contract_id,
			)
		except Exception as exc:
			weaviate_status = "failed"
			logger.exception("Failed to store clauses in Weaviate for contract_id=%s", contract_id)
			logger.warning("Weaviate clause embedding error: %s", exc)

		try:
			if self.pinecone is None:
				raise RuntimeError("PineconeVectorStore is unavailable")

			pinecone_result = self.pinecone.upsert_document(
				contract_id=contract_id,
				chunks=clause_chunks,
				metadata={"source": "clauses"},
			)
			pinecone_status = str(pinecone_result.get("status", "failed"))
			logger.info(
				"Mirrored %s clause texts into Pinecone for contract_id=%s",
				len(clause_chunks),
				contract_id,
			)
		except Exception as exc:
			pinecone_status = "failed"
			logger.exception("Failed to store clause texts in Pinecone for contract_id=%s", contract_id)
			logger.warning("Pinecone clause embedding error: %s", exc)

		total_duration = time.time() - start_time
		if pinecone_status == "success" and weaviate_status == "success":
			overall_status = "success"
		elif pinecone_status == "failed" and weaviate_status == "failed":
			overall_status = "failed"
		else:
			overall_status = "partial"

		return {
			"contract_id": contract_id,
			"clauses_embedded": clauses_embedded,
			"pinecone_status": pinecone_status,
			"weaviate_status": weaviate_status,
			"total_duration": total_duration,
			"status": overall_status,
		}

	def search_contract(
		self,
		query: str,
		contract_id: str | None = None,
		search_type: str = "both",
		top_k: int = 5,
	) -> dict:
		"""Search contract knowledge across Pinecone, Weaviate, or both."""

		pinecone_results: list[dict] = []
		weaviate_results: list[dict] = []
		combined_results: list[dict] = []

		def _score_value(item: dict) -> float:
			score = item.get("score")
			if score is None:
				score = item.get("certainty", 0.0)
			try:
				return float(score)
			except (TypeError, ValueError):
				return 0.0

		def _dedupe(items: list[dict]) -> list[dict]:
			seen: set[str] = set()
			unique: list[dict] = []
			for item in items:
				dedupe_key = str(
					item.get("id")
					or item.get("chunk_text")
					or item.get("clause_text")
					or item.get("metadata", {}).get("chunk_text", "")
				)
				if dedupe_key in seen:
					continue
				seen.add(dedupe_key)
				unique.append(item)
			return unique

		if search_type in {"pinecone", "both"}:
			try:
				if self.pinecone is None:
					raise RuntimeError("PineconeVectorStore is unavailable")
				pinecone_results = self.pinecone.search_similar(
					query=query,
					contract_id=contract_id,
					top_k=top_k,
				)
			except Exception as exc:
				logger.exception("Pinecone search failed")
				pinecone_results = [{"status": "failed", "error_message": str(exc)}]

		if search_type in {"weaviate", "both"}:
			try:
				if self.weaviate is None:
					raise RuntimeError("WeaviateVectorStore is unavailable")
				weaviate_results = self.weaviate.search_clauses(
					query=query,
					clause_type=None,
					contract_id=contract_id,
					top_k=top_k,
				)
			except Exception as exc:
				logger.exception("Weaviate search failed")
				weaviate_results = [{"status": "failed", "error_message": str(exc)}]

		if search_type == "pinecone":
			combined_results = sorted(pinecone_results, key=_score_value, reverse=True)
		elif search_type == "weaviate":
			combined_results = sorted(weaviate_results, key=_score_value, reverse=True)
		else:
			combined_results = sorted(
				_dedupe(pinecone_results + weaviate_results),
				key=_score_value,
				reverse=True,
			)

		logger.info(
			"Search completed for query on contract_id=%s (type=%s, results=%s)",
			contract_id,
			search_type,
			len(combined_results),
		)

		return {
			"query": query,
			"pinecone_results": pinecone_results,
			"weaviate_results": weaviate_results,
			"combined_results": combined_results,
			"total_results": len(combined_results),
		}

	def delete_contract_embeddings(self, contract_id: str) -> dict:
		"""Delete embeddings for a contract from both Pinecone and Weaviate."""

		pinecone_result: dict = {"status": "skipped", "deleted_count": 0}
		weaviate_result: dict = {"status": "skipped", "deleted_count": 0}

		try:
			if self.pinecone is None:
				raise RuntimeError("PineconeVectorStore is unavailable")
			pinecone_result = self.pinecone.delete_document(contract_id)
		except Exception as exc:
			pinecone_result = {"status": "failed", "deleted_count": 0, "error_message": str(exc)}
			logger.exception("Failed to delete Pinecone embeddings for contract_id=%s", contract_id)

		try:
			if self.weaviate is None:
				raise RuntimeError("WeaviateVectorStore is unavailable")
			weaviate_result = self.weaviate.delete_contract_clauses(contract_id)
		except Exception as exc:
			weaviate_result = {"status": "failed", "deleted_count": 0, "error_message": str(exc)}
			logger.exception("Failed to delete Weaviate embeddings for contract_id=%s", contract_id)

		status_values = {str(pinecone_result.get("status", "")), str(weaviate_result.get("status", ""))}
		if status_values == {"success"}:
			overall_status = "success"
		elif "failed" in status_values:
			overall_status = "partial" if "success" in status_values or "skipped" in status_values else "failed"
		else:
			overall_status = "partial"

		return {
			"contract_id": contract_id,
			"pinecone": pinecone_result,
			"weaviate": weaviate_result,
			"status": overall_status,
		}

	def get_embedding(self, text: str) -> list[float]:
		"""Generate a single embedding vector using OpenAI."""

		try:
			response = self.openai_client.embeddings.create(
				model=self.embedding_model,
				input=text,
			)
			embedding = list(response.data[0].embedding)
			logger.info("Generated embedding for text length %s", len(text))
			return embedding
		except Exception as exc:
			logger.exception("Failed to generate embedding")
			logger.warning("Embedding generation failed: %s", exc)
			return []

	def batch_get_embeddings(
		self,
		texts: list[str],
		batch_size: int = 100,
	) -> list[list[float]]:
		"""Generate embeddings in batches to reduce API pressure."""

		embeddings: list[list[float]] = []
		for offset in range(0, len(texts), batch_size):
			batch = texts[offset : offset + batch_size]
			try:
				response = self.openai_client.embeddings.create(
					model=self.embedding_model,
					input=batch,
				)
				batch_embeddings = [list(item.embedding) for item in response.data]
				embeddings.extend(batch_embeddings)
				logger.info("Generated %s embeddings in batch starting at %s", len(batch_embeddings), offset)
			except Exception as exc:
				logger.exception("Batch embedding request failed at offset %s", offset)
				logger.warning("Falling back to per-text embedding generation: %s", exc)
				for text in batch:
					embeddings.append(self.get_embedding(text))

		return embeddings
