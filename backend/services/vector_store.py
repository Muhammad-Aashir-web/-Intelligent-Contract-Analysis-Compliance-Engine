"""Pinecone vector store service for contract chunk indexing and retrieval."""

from __future__ import annotations

import logging
import os
import time

from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

logger = logging.getLogger(__name__)


class PineconeVectorStore:
	"""Service wrapper for Pinecone operations used by contract analysis workflows."""

	def __init__(self) -> None:
		"""Initialize Pinecone and OpenAI clients and connect to the target index."""

		load_dotenv()

		pinecone_api_key = os.getenv("PINECONE_API_KEY")
		openai_api_key = os.getenv("OPENAI_API_KEY")

		if not pinecone_api_key:
			raise ValueError("PINECONE_API_KEY is not set")
		if not openai_api_key:
			raise ValueError("OPENAI_API_KEY is not set")

		self.pc = Pinecone(api_key=pinecone_api_key)
		self.openai_client = OpenAI(api_key=openai_api_key)

		self.index_name = os.getenv("PINECONE_INDEX_NAME", "contract-intelligence")
		self.embedding_model = "text-embedding-3-small"
		self.dimension = 1536
		self.index = None

		self._initialize_index()

	def _initialize_index(self) -> None:
		"""Create the index if needed and connect to it."""

		start_time = time.time()

		try:
			existing_indexes = self.pc.list_indexes()
			if hasattr(existing_indexes, "names"):
				existing_names = set(existing_indexes.names())
			else:
				existing_names = {
					item.get("name")
					for item in existing_indexes
					if isinstance(item, dict) and item.get("name")
				}

			if self.index_name not in existing_names:
				logger.info("Pinecone index '%s' not found. Creating index.", self.index_name)
				self.pc.create_index(
					name=self.index_name,
					dimension=self.dimension,
					metric="cosine",
					spec=ServerlessSpec(
						cloud="aws",
						region=os.getenv("PINECONE_ENVIRONMENT", "us-east-1"),
					),
				)

			self.index = self.pc.Index(self.index_name)
			logger.info(
				"Pinecone index ready: %s (initialized in %.4fs)",
				self.index_name,
				time.time() - start_time,
			)
		except Exception as exc:
			logger.exception("Failed to initialize Pinecone index '%s'", self.index_name)
			raise exc

	def get_embedding(self, text: str) -> list[float]:
		"""Generate an embedding vector for the input text.

		Args:
			text: Source text for embedding.

		Returns:
			Embedding vector represented as a list of floats.
		"""

		try:
			response = self.openai_client.embeddings.create(
				model=self.embedding_model,
				input=text,
			)
			return list(response.data[0].embedding)
		except Exception as exc:
			logger.exception("Failed to generate embedding")
			raise exc

	def upsert_document(
		self,
		contract_id: str,
		chunks: list[str],
		metadata: dict | None = None,
	) -> dict:
		"""Create embeddings for chunks and upsert vectors into Pinecone.

		Args:
			contract_id: Contract identifier used in vector ids and metadata.
			chunks: Chunked contract text.
			metadata: Optional metadata merged into each vector metadata payload.

		Returns:
			Summary dictionary with upsert result details.
		"""

		start_time = time.time()
		base_metadata = dict(metadata or {})
		vectors: list[tuple[str, list[float], dict]] = []

		for i, chunk_text in enumerate(chunks):
			embedding = self.get_embedding(chunk_text)
			vector_id = f"{contract_id}_chunk_{i}"
			vector_metadata = {
				**base_metadata,
				"contract_id": contract_id,
				"chunk_index": i,
				"chunk_text": chunk_text,
			}
			vectors.append((vector_id, embedding, vector_metadata))

		total_upserted = 0
		for offset in range(0, len(vectors), 100):
			batch = vectors[offset : offset + 100]
			self.index.upsert(vectors=batch)
			total_upserted += len(batch)

		duration = time.time() - start_time
		logger.info(
			"Upserted %s vectors for contract_id=%s in %.4fs",
			total_upserted,
			contract_id,
			duration,
		)

		return {
			"vectors_upserted": total_upserted,
			"contract_id": contract_id,
			"status": "success",
		}

	def search_similar(
		self,
		query: str,
		contract_id: str | None = None,
		top_k: int = 5,
	) -> list[dict]:
		"""Search Pinecone for vectors semantically similar to a query.

		Args:
			query: Query text.
			contract_id: Optional contract id filter.
			top_k: Maximum number of matches to return.

		Returns:
			List of match dictionaries with id, score, chunk_text, and metadata.
		"""

		embedding = self.get_embedding(query)
		search_filter = {"contract_id": {"$eq": contract_id}} if contract_id else None

		response = self.index.query(
			vector=embedding,
			top_k=top_k,
			include_metadata=True,
			filter=search_filter,
		)

		matches = []
		for match in getattr(response, "matches", []) or []:
			metadata = getattr(match, "metadata", {}) or {}
			matches.append(
				{
					"id": getattr(match, "id", ""),
					"score": float(getattr(match, "score", 0.0)),
					"chunk_text": metadata.get("chunk_text", ""),
					"metadata": metadata,
				}
			)

		logger.info("Found %s similar vectors (contract_id=%s)", len(matches), contract_id)
		return matches

	def delete_document(self, contract_id: str) -> dict:
		"""Delete vectors belonging to a contract.

		Vectors are identified by id prefix ``{contract_id}_chunk_``. If id-prefix
		listing is unavailable, metadata-filter deletion is attempted as fallback.
		"""

		prefix = f"{contract_id}_chunk_"
		deleted_count = 0

		try:
			listed_ids: list[str] = []
			for page in self.index.list(prefix=prefix):
				if isinstance(page, list):
					listed_ids.extend([str(item) for item in page])
				elif hasattr(page, "ids"):
					listed_ids.extend([str(item) for item in page.ids])

			if listed_ids:
				self.index.delete(ids=listed_ids)
				deleted_count = len(listed_ids)
			else:
				self.index.delete(filter={"contract_id": {"$eq": contract_id}})

			logger.info(
				"Deleted vectors for contract_id=%s (deleted_count=%s)",
				contract_id,
				deleted_count,
			)
			return {
				"deleted_count": deleted_count,
				"contract_id": contract_id,
				"status": "success",
			}
		except Exception as exc:
			logger.exception("Failed to delete vectors for contract_id=%s", contract_id)
			return {
				"deleted_count": 0,
				"contract_id": contract_id,
				"status": "failed",
				"error_message": str(exc),
			}

	def get_index_stats(self) -> dict:
		"""Fetch index-level statistics from Pinecone."""

		try:
			stats = self.index.describe_index_stats()
			total_vectors = int(getattr(stats, "total_vector_count", 0) or 0)
			return {
				"total_vectors": total_vectors,
				"dimension": self.dimension,
				"index_name": self.index_name,
			}
		except Exception as exc:
			logger.exception("Failed to retrieve index stats for index=%s", self.index_name)
			return {
				"total_vectors": 0,
				"dimension": self.dimension,
				"index_name": self.index_name,
				"status": "failed",
				"error_message": str(exc),
			}
