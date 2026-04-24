"""Retrieval Augmented Generation service for contract analysis questions and comparisons."""

from __future__ import annotations

import logging
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

from services.embeddings import EmbeddingsService

logger = logging.getLogger(__name__)


class RAGService:
	"""Provide retrieval-augmented generation capabilities over contract content."""

	def __init__(self) -> None:
		"""Load configuration and initialize the embeddings and LLM clients."""

		load_dotenv()

		openai_api_key = os.getenv("OPENAI_API_KEY")
		self.embeddings = EmbeddingsService()
		self.openai_client = OpenAI(api_key=openai_api_key)
		self.model = "gpt-4o-mini"
		self.max_context_chunks = 5

		logger.info("RAGService initialized with model=%s max_context_chunks=%s", self.model, self.max_context_chunks)

	def answer_question(
		self,
		question: str,
		contract_id: str,
		search_type: str = "both",
	) -> dict:
		"""Answer a question about a specific contract using retrieved context."""

		start_time = time.time()

		try:
			search_results = self.embeddings.search_contract(
				query=question,
				contract_id=contract_id,
				search_type=search_type,
				top_k=self.max_context_chunks,
			)
			context = self._build_context(search_results)
			sources = self._extract_sources(search_results)
			confidence = self._calculate_confidence(search_results)

			response = self.openai_client.chat.completions.create(
				model=self.model,
				messages=[
					{
						"role": "system",
						"content": (
							"You are a legal contract analyst assistant. Answer questions about\n"
							"contracts based ONLY on the provided contract context. If the answer\n"
							"is not found in the context, say 'This information is not found in\n"
							"the contract.' Be precise and cite specific clause language."
						),
					},
					{
						"role": "user",
						"content": f"Context:\n{context}\n\nQuestion: {question}",
					},
				],
				temperature=0,
			)

			answer = (response.choices[0].message.content or "").strip()
			duration = time.time() - start_time

			logger.info("Answered question for contract_id=%s in %.4fs", contract_id, duration)
			return {
				"question": question,
				"answer": answer,
				"sources": sources,
				"contract_id": contract_id,
				"confidence": confidence,
				"processing_time": duration,
			}
		except Exception as exc:
			duration = time.time() - start_time
			logger.exception("Failed to answer question for contract_id=%s", contract_id)
			return {
				"question": question,
				"answer": f"Unable to answer question: {exc}",
				"sources": [],
				"contract_id": contract_id,
				"confidence": 0.0,
				"processing_time": duration,
				"status": "failed",
				"error_message": str(exc),
			}

	def summarize_contract(self, contract_id: str) -> dict:
		"""Generate a concise but comprehensive summary of a contract."""

		start_time = time.time()

		try:
			search_results = self.embeddings.search_contract(
				query="contract summary overview parties obligations",
				contract_id=contract_id,
				search_type="both",
				top_k=10,
			)
			context = self._build_context(search_results, max_chunks=10)

			response = self.openai_client.chat.completions.create(
				model=self.model,
				messages=[
					{
						"role": "system",
						"content": (
							"You are a legal contract analyst. Create a comprehensive but concise\n"
							"summary of this contract. Include: parties involved, main purpose,\n"
							"key obligations, important dates, financial terms, and any notable\n"
							"risks or unusual clauses."
						),
					},
					{
						"role": "user",
						"content": f"Context:\n{context}",
					},
				],
				temperature=0,
			)

			raw_summary = (response.choices[0].message.content or "").strip()
			summary_data = self._parse_json_like_payload(raw_summary)
			summary_text = summary_data.get("summary") or raw_summary
			key_points = summary_data.get("key_points") or []
			parties = summary_data.get("parties") or []

			duration = time.time() - start_time
			logger.info("Summarized contract_id=%s in %.4fs", contract_id, duration)
			return {
				"contract_id": contract_id,
				"summary": summary_text,
				"key_points": key_points,
				"parties": parties,
				"processing_time": duration,
			}
		except Exception as exc:
			duration = time.time() - start_time
			logger.exception("Failed to summarize contract_id=%s", contract_id)
			return {
				"contract_id": contract_id,
				"summary": f"Unable to summarize contract: {exc}",
				"key_points": [],
				"parties": [],
				"processing_time": duration,
				"status": "failed",
				"error_message": str(exc),
			}

	def find_similar_clauses(
		self,
		clause_text: str,
		contract_id: str | None = None,
		top_k: int = 5,
	) -> dict:
		"""Find clauses similar to the provided clause text across both vector stores."""

		try:
			search_results = self.embeddings.search_contract(
				query=clause_text,
				contract_id=contract_id,
				search_type="both",
				top_k=top_k,
			)
			similar_clauses = search_results.get("combined_results", [])
			logger.info(
				"Found %s similar clauses for contract_id=%s",
				len(similar_clauses),
				contract_id,
			)
			return {
				"query_clause": clause_text,
				"similar_clauses": similar_clauses,
				"total_found": len(similar_clauses),
			}
		except Exception as exc:
			logger.exception("Failed to find similar clauses")
			return {
				"query_clause": clause_text,
				"similar_clauses": [],
				"total_found": 0,
				"status": "failed",
				"error_message": str(exc),
			}

	def compare_contracts(
		self,
		contract_id_1: str,
		contract_id_2: str,
		aspect: str = "overall",
	) -> dict:
		"""Compare two contracts on a chosen aspect using retrieved contract context."""

		start_time = time.time()
		comparison_query = self._aspect_to_query(aspect)

		try:
			contract_1_results = self.embeddings.search_contract(
				query=comparison_query,
				contract_id=contract_id_1,
				search_type="both",
				top_k=self.max_context_chunks,
			)
			contract_2_results = self.embeddings.search_contract(
				query=comparison_query,
				contract_id=contract_id_2,
				search_type="both",
				top_k=self.max_context_chunks,
			)

			context_1 = self._build_context(contract_1_results)
			context_2 = self._build_context(contract_2_results)

			prompt = (
				f"Contract A ({contract_id_1}):\n{context_1}\n\n"
				f"Contract B ({contract_id_2}):\n{context_2}"
			)

			response = self.openai_client.chat.completions.create(
				model=self.model,
				messages=[
					{
						"role": "system",
						"content": (
							f"Compare these two contracts focusing on {aspect}. \n"
							"Highlight key differences, similarities, and which contract\n"
							"is more favorable. Return JSON with: differences (list),\n"
							"similarities (list), more_favorable (contract_id),\n"
							"reasoning (string)"
						),
					},
					{"role": "user", "content": prompt},
				],
				temperature=0,
			)

			raw_output = (response.choices[0].message.content or "").strip()
			parsed = self._parse_json_like_payload(raw_output)
			duration = time.time() - start_time

			result = {
				"contract_id_1": contract_id_1,
				"contract_id_2": contract_id_2,
				"aspect": aspect,
				"differences": parsed.get("differences", []),
				"similarities": parsed.get("similarities", []),
				"more_favorable": parsed.get("more_favorable", ""),
				"reasoning": parsed.get("reasoning", raw_output),
				"processing_time": duration,
			}
			logger.info(
				"Compared contracts %s and %s on aspect=%s in %.4fs",
				contract_id_1,
				contract_id_2,
				aspect,
				duration,
			)
			return result
		except Exception as exc:
			duration = time.time() - start_time
			logger.exception("Failed to compare contracts %s and %s", contract_id_1, contract_id_2)
			return {
				"contract_id_1": contract_id_1,
				"contract_id_2": contract_id_2,
				"aspect": aspect,
				"differences": [],
				"similarities": [],
				"more_favorable": "",
				"reasoning": f"Unable to compare contracts: {exc}",
				"processing_time": duration,
				"status": "failed",
				"error_message": str(exc),
			}

	def _build_context(
		self,
		search_results: dict,
		max_chunks: int | None = None,
	) -> str:
		"""Build a numbered context string from combined search results."""

		limit = max_chunks or self.max_context_chunks
		combined_results = self._merge_search_results(search_results)

		deduped: list[dict] = []
		seen_normalized: set[str] = set()

		for item in combined_results:
			text = self._extract_text(item)
			normalized = self._normalize_text(text)
			if not normalized or normalized in seen_normalized:
				continue
			seen_normalized.add(normalized)
			deduped.append(item)
			if len(deduped) >= limit:
				break

		lines: list[str] = []
		for index, item in enumerate(deduped, start=1):
			text = self._extract_text(item)
			source_label = self._source_label(item)
			lines.append(f"{index}. [{source_label}] {text}")

		context = "\n\n".join(lines)
		logger.info("Built context with %s chunks", len(deduped))
		return context

	def _merge_search_results(self, search_results: dict) -> list[dict]:
		"""Merge and sort Pinecone and Weaviate results by relevance score."""

		pinecone_results = list(search_results.get("pinecone_results", []) or [])
		weaviate_results = list(search_results.get("weaviate_results", []) or [])
		combined = pinecone_results + weaviate_results

		def _score(item: dict) -> float:
			for key in ("score", "certainty", "relevance_score"):
				value = item.get(key)
				if value is not None:
					try:
						return float(value)
					except (TypeError, ValueError):
						continue
			return 0.0

		combined.sort(key=_score, reverse=True)
		return combined

	def _extract_text(self, item: dict) -> str:
		"""Extract searchable text from a result item."""

		metadata = item.get("metadata", {}) if isinstance(item.get("metadata", {}), dict) else {}
		for key in ("chunk_text", "clause_text", "text"):
			value = item.get(key) or metadata.get(key)
			if value:
				return str(value).strip()
		return str(metadata.get("summary", "")).strip()

	def _source_label(self, item: dict) -> str:
		"""Create a human-readable source label for a chunk."""

		metadata = item.get("metadata", {}) if isinstance(item.get("metadata", {}), dict) else {}
		contract_id = metadata.get("contract_id") or item.get("contract_id") or "unknown"
		clause_type = metadata.get("clause_type") or item.get("clause_type") or "document"
		return f"{contract_id}:{clause_type}"

	def _normalize_text(self, text: str) -> str:
		"""Normalize text for duplicate detection."""

		return " ".join(text.lower().split())

	def _calculate_confidence(self, search_results: dict) -> float:
		"""Estimate answer confidence from source relevance scores."""

		scores: list[float] = []
		for item in self._merge_search_results(search_results)[: self.max_context_chunks]:
			for key in ("score", "certainty", "relevance_score"):
				value = item.get(key)
				if value is not None:
					try:
						scores.append(float(value))
						break
					except (TypeError, ValueError):
						continue

		if not scores:
			return 0.0

		average = sum(scores) / len(scores)
		return max(0.0, min(1.0, average))

	def _extract_sources(self, search_results: dict) -> list[dict]:
		"""Return the top retrieved chunks as source metadata."""

		sources: list[dict] = []
		for item in self._merge_search_results(search_results)[: self.max_context_chunks]:
			sources.append(
				{
					"id": item.get("id", ""),
					"score": item.get("score", item.get("certainty", 0.0)),
					"chunk_text": self._extract_text(item),
					"metadata": item.get("metadata", {}),
				}
			)
		return sources

	def _parse_json_like_payload(self, payload: str) -> dict:
		"""Parse a JSON payload from an LLM response with safe fallbacks."""

		import json

		try:
			parsed = json.loads(payload)
			return parsed if isinstance(parsed, dict) else {"summary": payload}
		except Exception:
			pass

		start = payload.find("{")
		end = payload.rfind("}")
		if start != -1 and end != -1 and end > start:
			try:
				parsed = json.loads(payload[start : end + 1])
				return parsed if isinstance(parsed, dict) else {"summary": payload}
			except Exception:
				pass

		return {"summary": payload}

	def _aspect_to_query(self, aspect: str) -> str:
		"""Map a comparison aspect to a retrieval query."""

		aspect_map = {
			"overall": "contract overview obligations payment termination liability",
			"risk": "risk liability indemnification termination notice breach",
			"payment": "payment fees invoice pricing late fees currency tax",
			"termination": "termination convenience cause notice renewal expiration",
			"liability": "liability indemnification warranty disclaimer insurance cap",
		}
		return aspect_map.get(aspect, aspect_map["overall"])
