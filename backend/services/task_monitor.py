"""Task monitoring utilities for Celery-based contract analysis workflows."""

from __future__ import annotations

import logging
import time
from typing import Any

from celery.result import AsyncResult
from dotenv import load_dotenv

from celery_app import celery_app


class TaskMonitorService:
	"""Monitor and manage Celery background tasks for contract analysis."""

	def __init__(self) -> None:
		"""Initialize task monitor resources and logger."""

		load_dotenv()
		self.logger = logging.getLogger(__name__)
		self.logger.info("TaskMonitorService initialized successfully")

	def get_task_status(self, task_id: str) -> dict[str, Any]:
		"""Return status details for a given Celery task.

		Args:
			task_id: Celery task identifier.

		Returns:
			Dictionary with task_id, status, result/error, and progress estimate.
		"""

		start_time = time.time()
		self.logger.info("Fetching task status for task_id=%s", task_id)

		async_result = AsyncResult(task_id, app=celery_app)
		status = str(async_result.status)

		progress_map = {
			"PENDING": 0,
			"STARTED": 25,
			"RETRY": 50,
			"SUCCESS": 100,
			"FAILURE": 0,
		}
		progress = progress_map.get(status, 0)

		result_payload: dict[str, Any] | None = None
		error_payload: str | None = None

		if status == "SUCCESS":
			if isinstance(async_result.result, dict):
				result_payload = async_result.result
			elif async_result.result is not None:
				result_payload = {"value": async_result.result}
		elif status == "FAILURE":
			error_payload = str(async_result.result)

		response: dict[str, Any] = {
			"task_id": task_id,
			"status": status,
			"result": result_payload,
			"error": error_payload,
			"progress": progress,
		}

		duration = time.time() - start_time
		self.logger.info(
			"Task status fetched task_id=%s status=%s progress=%s duration=%.3fs",
			task_id,
			status,
			progress,
			duration,
		)
		return response

	def get_all_active_tasks(self) -> list[dict[str, str]]:
		"""Return currently active Celery tasks across workers.

		Returns:
			List of task dictionaries with task_id and status.
		"""

		self.logger.info("Fetching all active Celery tasks")
		active_tasks: list[dict[str, str]] = []

		try:
			inspector = celery_app.control.inspect()
			active_by_worker = inspector.active() or {}

			for worker_name, tasks in active_by_worker.items():
				for task in tasks:
					task_id = str(task.get("id") or "")
					if not task_id:
						continue
					active_tasks.append({"task_id": task_id, "status": "STARTED"})

			self.logger.info(
				"Active task inspection complete workers=%s active_tasks=%s",
				len(active_by_worker),
				len(active_tasks),
			)
			return active_tasks
		except Exception:
			self.logger.exception("Failed to inspect active Celery tasks")
			return []

	def cancel_task(self, task_id: str) -> dict[str, str]:
		"""Revoke a Celery task.

		Args:
			task_id: Celery task identifier.

		Returns:
			Dictionary containing task_id, status, and human-readable message.
		"""

		self.logger.info("Attempting to cancel task task_id=%s", task_id)
		try:
			celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
			message = "Task cancellation requested"
			self.logger.info("Task revoke requested task_id=%s", task_id)
			return {"task_id": task_id, "status": "cancelled", "message": message}
		except Exception as exc:
			self.logger.exception("Task cancellation failed task_id=%s", task_id)
			return {
				"task_id": task_id,
				"status": "error",
				"message": f"Failed to cancel task: {exc}",
			}

	def get_task_result(self, task_id: str) -> dict[str, Any] | None:
		"""Return task result payload when task has completed successfully.

		Args:
			task_id: Celery task identifier.

		Returns:
			Task result dictionary for successful completion, else None.
		"""

		self.logger.info("Fetching task result for task_id=%s", task_id)
		result = AsyncResult(task_id, app=celery_app)

		if not result.ready():
			self.logger.info("Task not ready task_id=%s status=%s", task_id, result.status)
			return None

		if not result.successful():
			self.logger.info("Task completed without success task_id=%s status=%s", task_id, result.status)
			return None

		if isinstance(result.result, dict):
			return result.result

		if result.result is None:
			return None

		return {"value": result.result}
