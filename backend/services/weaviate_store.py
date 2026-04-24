"""Weaviate vector store service for contract clause storage and retrieval."""

from __future__ import annotations

import logging
import os
import uuid

from dotenv import load_dotenv
from openai import OpenAI
import weaviate
from weaviate.classes.config import Configure, DataType, Property
from weaviate.classes.init import Auth
from weaviate.classes.query import Filter

logger = logging.getLogger(__name__)


class WeaviateVectorStore:
	"""Service for storing, searching, and deleting contract clauses in Weaviate."""

	def __init__(self) -> None:
		"""Load configuration, initialize clients, and ensure the collection exists."""

		load_dotenv()

		openai_api_key = os.getenv("OPENAI_API_KEY")
		weaviate_url = os.getenv("WEAVIATE_URL")
		weaviate_api_key = os.getenv("WEAVIATE_API_KEY")

		if not openai_api_key:
			raise ValueError("OPENAI_API_KEY is not set")
		if not weaviate_url:
			raise ValueError("WEAVIATE_URL is not set")
		if not weaviate_api_key:
			raise ValueError("WEAVIATE_API_KEY is not set")

		self.embedding_model = "text-embedding-3-small"
		self.collection_name = "ContractClause"
		self.client = None
		self.collection = None
		self._weaviate_url = weaviate_url
		self._weaviate_api_key = weaviate_api_key
		self.openai_client = OpenAI(api_key=openai_api_key)

		self._connect()
		self._initialize_collection()

	def _connect(self) -> None:
		"""Connect to Weaviate Cloud using configured credentials."""

		if self.client is not None:
			return

		self.client = weaviate.connect_to_weaviate_cloud(
			cluster_url=self._weaviate_url,
			auth_credentials=Auth.api_key(self._weaviate_api_key),
		)
		logger.info("Connected to Weaviate cloud for collection %s", self.collection_name)

	def _initialize_collection(self) -> None:
		"""Create the ContractClause collection when it does not already exist."""

		try:
			try:
				exists = self.client.collections.exists(self.collection_name)
			except Exception:
				exists = False

			if not exists:
				logger.info("Creating Weaviate collection %s", self.collection_name)
				self.client.collections.create(
					name=self.collection_name,
					properties=[
						Property(name="contract_id", data_type=DataType.TEXT),
						Property(name="clause_type", data_type=DataType.TEXT),
						Property(name="clause_text", data_type=DataType.TEXT),
						Property(name="summary", data_type=DataType.TEXT),
						Property(name="risk_score", data_type=DataType.NUMBER),
						Property(name="confidence", data_type=DataType.NUMBER),
						Property(name="page_hint", data_type=DataType.NUMBER),
					],
					vectorizer_config=Configure.Vectorizer.none(),
				)

			self.collection = self.client.collections.get(self.collection_name)
			logger.info("Weaviate collection ready: %s", self.collection_name)
		except Exception:
			logger.exception("Failed to initialize Weaviate collection %s", self.collection_name)
			self.close()
			raise

	def _ensure_connection(self) -> None:
		"""Reconnect if the client has been closed by a previous operation."""

		if self.client is None or self.collection is None:
			self._connect()
			self._initialize_collection()

	def get_embedding(self, text: str) -> list[float]:
		"""Generate an embedding vector for a text input."""

		try:
			response = self.openai_client.embeddings.create(
				model=self.embedding_model,
				input=text,
			)
			return list(response.data[0].embedding)
		except Exception:
			logger.exception("Failed to generate embedding for Weaviate operation")
			raise

	def upsert_clauses(self, contract_id: str, clauses: list[dict]) -> dict:
		"""Upsert contract clauses and their embeddings into Weaviate."""

		self._ensure_connection()
		try:
			upserted = 0
			for clause in clauses:
				clause_text = str(clause.get("clause_text", "")).strip()
				embedding = self.get_embedding(clause_text)
				clause_payload = {
					"contract_id": contract_id,
					"clause_type": str(clause.get("clause_type", "")).strip(),
					"clause_text": clause_text,
					"summary": str(clause.get("summary", "")).strip(),
					"risk_score": float(clause.get("risk_score", 0.0)),
					"confidence": float(clause.get("confidence", 0.0)),
					"page_hint": float(clause.get("page_hint", 0.0)),
				}

				self.collection.data.insert(
					uuid=str(uuid.uuid4()),
					properties=clause_payload,
					vector=embedding,
				)
				upserted += 1

			logger.info("Upserted %s clauses for contract_id=%s", upserted, contract_id)
			return {
				"clauses_upserted": upserted,
				"contract_id": contract_id,
				"status": "success",
			}
		except Exception as exc:
			logger.exception("Failed to upsert clauses for contract_id=%s", contract_id)
			return {
				"clauses_upserted": 0,
				"contract_id": contract_id,
				"status": "failed",
				"error_message": str(exc),
			}
		finally:
			self.close()

	def search_clauses(
		self,
		query: str,
		clause_type: str | None = None,
		contract_id: str | None = None,
		top_k: int = 5,
	) -> list[dict]:
		"""Search for semantically similar clauses in Weaviate."""

		self._ensure_connection()
		try:
			embedding = self.get_embedding(query)
			filters = None

			if clause_type and contract_id:
				filters = Filter.all_of(
					[
						Filter.by_property("clause_type").equal(clause_type),
						Filter.by_property("contract_id").equal(contract_id),
					]
				)
			elif clause_type:
				filters = Filter.by_property("clause_type").equal(clause_type)
			elif contract_id:
				filters = Filter.by_property("contract_id").equal(contract_id)

			result = self.collection.query.near_vector(
				near_vector=embedding,
				limit=top_k,
				filters=filters,
			)

			matches: list[dict] = []
			for item in getattr(result, "objects", []) or []:
				metadata = {}
				certainty = None

				if hasattr(item, "metadata") and item.metadata is not None:
					metadata = dict(getattr(item, "metadata", {}) or {})
					certainty = getattr(item.metadata, "certainty", None)
					if certainty is None and isinstance(item.metadata, dict):
						certainty = item.metadata.get("certainty")

				properties = dict(getattr(item, "properties", {}) or {})
				matches.append(
					{
						"id": str(getattr(item, "uuid", "")),
						"score": float(certainty if certainty is not None else 0.0),
						"clause_text": properties.get("clause_text", ""),
						"clause_type": properties.get("clause_type", ""),
						"contract_id": properties.get("contract_id", ""),
						"summary": properties.get("summary", ""),
						"risk_score": properties.get("risk_score"),
						"confidence": properties.get("confidence"),
						"page_hint": properties.get("page_hint"),
						"metadata": {**properties, **metadata},
					}
				)

			logger.info(
				"Search returned %s clauses (clause_type=%s, contract_id=%s)",
				len(matches),
				clause_type,
				contract_id,
			)
			return matches
		except Exception as exc:
			logger.exception("Failed to search clauses")
			return [{"status": "failed", "error_message": str(exc)}]
		finally:
			self.close()

	def search_by_risk(self, contract_id: str, min_risk_score: float = 0.5) -> list[dict]:
		"""Return clauses for a contract with risk scores above a minimum threshold."""

		self._ensure_connection()
		try:
			filters = Filter.all_of(
				[
					Filter.by_property("contract_id").equal(contract_id),
					Filter.by_property("risk_score").greater_or_equal(min_risk_score),
				]
			)

			result = self.collection.query.fetch_objects(filters=filters, limit=1000)
			clauses: list[dict] = []

			for item in getattr(result, "objects", []) or []:
				properties = dict(getattr(item, "properties", {}) or {})
				clauses.append(
					{
						"id": str(getattr(item, "uuid", "")),
						"contract_id": properties.get("contract_id", ""),
						"clause_type": properties.get("clause_type", ""),
						"clause_text": properties.get("clause_text", ""),
						"summary": properties.get("summary", ""),
						"risk_score": float(properties.get("risk_score", 0.0)),
						"confidence": float(properties.get("confidence", 0.0)),
						"page_hint": float(properties.get("page_hint", 0.0)),
					}
				)

			clauses.sort(key=lambda item: float(item.get("risk_score", 0.0)), reverse=True)
			logger.info(
				"Retrieved %s high-risk clauses for contract_id=%s",
				len(clauses),
				contract_id,
			)
			return clauses
		except Exception as exc:
			logger.exception("Failed to search clauses by risk for contract_id=%s", contract_id)
			return [{"status": "failed", "error_message": str(exc)}]
		finally:
			self.close()

	def delete_contract_clauses(self, contract_id: str) -> dict:
		"""Delete all clauses stored for a given contract identifier."""

		self._ensure_connection()
		try:
			filters = Filter.by_property("contract_id").equal(contract_id)
			existing = self.collection.query.fetch_objects(filters=filters, limit=1000)
			deleted_count = len(getattr(existing, "objects", []) or [])

			try:
				self.collection.data.delete_many(filters=filters)
			except TypeError:
				self.collection.data.delete_many(where=filters)

			logger.info("Deleted %s clauses for contract_id=%s", deleted_count, contract_id)
			return {
				"deleted_count": deleted_count,
				"contract_id": contract_id,
				"status": "success",
			}
		except Exception as exc:
			logger.exception("Failed to delete clauses for contract_id=%s", contract_id)
			return {
				"deleted_count": 0,
				"contract_id": contract_id,
				"status": "failed",
				"error_message": str(exc),
			}
		finally:
			self.close()

	def get_index_stats(self) -> dict:
		"""Return collection statistics for the contract clause index."""

		self._ensure_connection()
		try:
			stats = self.client.collections.get(self.collection_name).aggregate.over_all()
			total_vectors = int(getattr(stats, "total_count", 0) or 0)
			logger.info(
				"Weaviate stats retrieved for collection %s: %s vectors",
				self.collection_name,
				total_vectors,
			)
			return {
				"total_vectors": total_vectors,
				"collection_name": self.collection_name,
			}
		except Exception as exc:
			logger.exception("Failed to retrieve Weaviate stats for collection %s", self.collection_name)
			return {
				"total_vectors": 0,
				"collection_name": self.collection_name,
				"status": "failed",
				"error_message": str(exc),
			}
		finally:
			self.close()

	def close(self) -> None:
		"""Close the Weaviate client connection."""

		if self.client is not None:
			try:
				self.client.close()
				logger.info("Closed Weaviate connection for collection %s", self.collection_name)
			finally:
				self.client = None
				self.collection = None
