"""Unified LLM service for contract analysis interactions."""

from __future__ import annotations

import json
import logging
import os
import time

from anthropic import Anthropic
from dotenv import load_dotenv
from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMService:
	"""Provide a single interface for LLM completions across providers."""

	def __init__(self) -> None:
		"""Initialize OpenAI and Anthropic clients from environment variables."""

		load_dotenv()

		self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
		self.anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
		self.default_model = "gpt-4o-mini"
		self.fallback_model = "claude-haiku-4-5-20251001"

		logger.info(
			"LLMService initialized with default_model=%s fallback_model=%s",
			self.default_model,
			self.fallback_model,
		)

	def complete(
		self,
		prompt: str,
		system: str | None = None,
		model: str | None = None,
		max_tokens: int = 1000,
	) -> str:
		"""Generate a completion with OpenAI and fallback to Anthropic on failure.

		Args:
			prompt: User prompt content.
			system: Optional system instruction.
			model: Optional explicit OpenAI model override.
			max_tokens: Maximum output tokens.

		Returns:
			Model response text.
		"""

		selected_model = model or self.default_model
		start_time = time.time()

		try:
			messages = []
			if system:
				messages.append({"role": "system", "content": system})
			messages.append({"role": "user", "content": prompt})

			response = self.openai_client.chat.completions.create(
				model=selected_model,
				messages=messages,
				max_tokens=max_tokens,
			)
			text = (response.choices[0].message.content or "").strip()
			logger.info(
				"Completion succeeded using OpenAI model=%s in %.4fs",
				selected_model,
				time.time() - start_time,
			)
			return text
		except Exception as openai_exc:
			logger.warning(
				"OpenAI completion failed for model=%s; falling back to Anthropic: %s",
				selected_model,
				openai_exc,
			)

		try:
			response = self.anthropic_client.messages.create(
				model=self.fallback_model,
				system=system or "You are a helpful legal contract analysis assistant.",
				max_tokens=max_tokens,
				messages=[{"role": "user", "content": prompt}],
			)

			parts = []
			for block in getattr(response, "content", []) or []:
				text_value = getattr(block, "text", None)
				if text_value:
					parts.append(str(text_value))

			fallback_text = "\n".join(parts).strip()
			logger.info(
				"Completion succeeded using Anthropic model=%s in %.4fs",
				self.fallback_model,
				time.time() - start_time,
			)
			return fallback_text
		except Exception as anthropic_exc:
			logger.exception("Anthropic fallback completion failed")
			return f"LLM completion failed: {anthropic_exc}"

	def complete_json(
		self,
		prompt: str,
		system: str | None = None,
		model: str | None = None,
	) -> dict:
		"""Generate a completion expected to be JSON and parse it safely.

		Args:
			prompt: User prompt content.
			system: Optional system instruction.
			model: Optional explicit OpenAI model override.

		Returns:
			Parsed JSON object, or an empty dictionary if parsing fails.
		"""

		json_system = (
			"Return only valid JSON. Do not include markdown, code fences, or extra text."
		)
		composed_system = f"{system}\n\n{json_system}" if system else json_system

		raw_text = self.complete(
			prompt=prompt,
			system=composed_system,
			model=model,
			max_tokens=1000,
		)

		try:
			parsed = json.loads(raw_text)
			if isinstance(parsed, dict):
				return parsed
			return {}
		except json.JSONDecodeError:
			start = raw_text.find("{")
			end = raw_text.rfind("}")
			if start != -1 and end != -1 and end > start:
				try:
					parsed = json.loads(raw_text[start : end + 1])
					return parsed if isinstance(parsed, dict) else {}
				except json.JSONDecodeError:
					pass

		logger.warning("Failed to parse JSON completion output")
		return {}
