from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


class WebhookPayload(BaseModel):
    event_type: str
    data: Dict[str, Any]
    timestamp: str


@router.post("/docusign")
async def docusign_webhook(payload: WebhookPayload, request: Request) -> Dict[str, str]:
    try:
        # Placeholder logging for incoming DocuSign events.
        print(
            "DocuSign webhook received",
            {"event_type": payload.event_type, "client": str(request.client)},
        )
        return {"message": "DocuSign webhook acknowledged"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process DocuSign webhook",
        ) from exc


@router.post("/n8n")
async def n8n_webhook(payload: WebhookPayload, request: Request) -> Dict[str, str]:
    try:
        # Placeholder workflow completion handling.
        print(
            "n8n webhook received",
            {"event_type": payload.event_type, "client": str(request.client)},
        )
        return {"message": "n8n webhook acknowledged"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process n8n webhook",
        ) from exc


@router.get("/health")
def webhooks_health() -> Dict[str, str]:
    return {"status": "ok"}
