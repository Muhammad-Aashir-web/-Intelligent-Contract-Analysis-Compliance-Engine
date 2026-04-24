from datetime import datetime
from pathlib import Path
from typing import List, Optional
import logging
import shutil
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

try:
    from celery_app import celery_app
except Exception:  # pragma: no cover - celery module may be introduced later
    celery_app = None
from config import settings
from database import get_db
from models.clause import Clause
from models.contract import Contract
from models.user import User
from services.embeddings import EmbeddingsService
from services.rag import RAGService
from workflows.contract_analysis import run_contract_analysis

router = APIRouter(prefix="/contracts", tags=["Contracts"])
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


class ContractResponse(BaseModel):
    id: int
    title: str
    file_name: str
    contract_type: Optional[str] = None
    status: str
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContractListResponse(BaseModel):
    contracts: List[ContractResponse]
    total: int


class AnalysisRequest(BaseModel):
    contract_id: int
    priority: Optional[str] = None


class AskRequest(BaseModel):
    question: str


def _get_or_create_placeholder_user(db: Session) -> User:
    # Placeholder owner for uploads until full user auth is integrated.
    placeholder_email = "system@local.dev"
    user = db.query(User).filter(User.email == placeholder_email).first()
    if user is None:
        user = User(
            email=placeholder_email,
            hashed_password="placeholder",
            full_name="System User",
            company="System",
            role="admin",
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_contract(
    file: UploadFile = File(...),
    frameworks: str = "GENERAL",
    negotiation_stance: str = "balanced",
    db: Session = Depends(get_db),
) -> dict[str, object]:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only PDF and DOCX are allowed.",
        )

    content = await file.read()
    file_size = len(content)
    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB.",
        )

    await file.seek(0)
    user = _get_or_create_placeholder_user(db)

    contract = Contract(
        title=Path(file.filename or "untitled").stem,
        file_name=file.filename or "untitled",
        file_path=None,
        file_size=file_size,
        contract_type="DOCX" if extension == ".docx" else "PDF",
        status="uploaded",
        user_id=user.id,
    )

    try:
        db.add(contract)
        db.commit()
        db.refresh(contract)

        uploads_dir = Path(__file__).resolve().parents[2] / "data" / "uploads" / str(contract.id)
        uploads_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = f"{uuid.uuid4()}_{file.filename or 'contract'}"
        saved_path = uploads_dir / safe_filename

        with saved_path.open("wb") as out_file:
            shutil.copyfileobj(file.file, out_file)

        contract.file_path = str(saved_path)
        contract.file_size = saved_path.stat().st_size
        db.commit()

        framework_list = [item.strip().upper() for item in frameworks.split(",") if item.strip()] or ["GENERAL"]

        if celery_app is None:
            raise RuntimeError("celery_app is not configured")

        process_task = celery_app.tasks.get("process_contract_task") if hasattr(celery_app, "tasks") else None
        if process_task is not None:
            process_task.delay(contract.id, str(saved_path), framework_list, negotiation_stance)
        else:
            celery_app.send_task(
                "process_contract_task",
                args=[contract.id, str(saved_path), framework_list, negotiation_stance],
            )

        logger.info(
            "Upload accepted and processing enqueued for contract_id=%s file=%s",
            contract.id,
            saved_path,
        )

        return {
            "contract_id": contract.id,
            "filename": contract.file_name,
            "status": contract.status,
            "message": "Contract uploaded and processing started.",
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to upload/process contract file")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload contract: {exc}",
        )
    finally:
        await file.close()


@router.get("/{contract_id}/status")
def get_contract_status(contract_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    """Return current processing status and timestamps for a contract."""

    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found.",
        )

    return {
        "contract_id": contract.id,
        "status": contract.status,
        "created_at": contract.created_at,
        "updated_at": contract.updated_at,
    }


@router.get("", response_model=ContractListResponse)
def list_contracts(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
) -> ContractListResponse:
    if skip < 0 or limit < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="skip must be >= 0 and limit must be >= 1.",
        )

    total = db.query(Contract).count()
    contracts = db.query(Contract).offset(skip).limit(limit).all()
    return ContractListResponse(contracts=contracts, total=total)


@router.get("/{contract_id}", response_model=ContractResponse)
def get_contract(contract_id: int, db: Session = Depends(get_db)) -> Contract:
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found.",
        )
    return contract


@router.post("/{contract_id}/analyze")
def analyze_contract(
    contract_id: int,
    analysis_request: AnalysisRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if analysis_request.contract_id != contract_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="contract_id in body must match path parameter.",
        )

    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found.",
        )

    # Placeholder status transition while external analysis pipeline is pending.
    contract.status = "processing"
    db.commit()
    return {"message": "Analysis started"}


@router.get("/{contract_id}/results")
def get_contract_results(contract_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found.",
        )

    clauses = db.query(Clause).filter(Clause.contract_id == contract.id).all()

    if contract.status != "completed":
        return {
            "contract_id": contract.id,
            "status": contract.status,
            "message": "Analysis is still processing.",
        }

    return {
        "contract_id": contract.id,
        "status": contract.status,
        "title": contract.title,
        "file_name": contract.file_name,
        "contract_type": contract.contract_type,
        "risk_score": contract.risk_score,
        "risk_level": contract.risk_level,
        "summary": contract.summary,
        "raw_text": contract.raw_text,
        "clauses": [
            {
                "id": clause.id,
                "clause_type": clause.clause_type,
                "clause_text": clause.clause_text,
                "risk_score": clause.risk_score,
                "risk_level": clause.risk_level,
                "risk_explanation": clause.risk_explanation,
                "compliance_status": clause.compliance_status,
                "compliance_notes": clause.compliance_notes,
                "negotiation_suggestion": clause.negotiation_suggestion,
                "is_flagged": clause.is_flagged,
                "page_number": clause.page_number,
                "position_start": clause.position_start,
                "position_end": clause.position_end,
            }
            for clause in clauses
        ],
    }


@router.post("/{contract_id}/ask")
def ask_contract_question(
    contract_id: int,
    payload: AskRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Answer a question about a contract using RAG retrieval."""

    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found.",
        )

    try:
        rag = RAGService()
        result = rag.answer_question(
            question=payload.question,
            contract_id=str(contract_id),
            search_type="both",
        )
        return {
            "question": result.get("question", payload.question),
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "confidence": result.get("confidence", 0.0),
        }
    except Exception as exc:
        logger.exception("Failed to answer question for contract_id=%s", contract_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to answer question: {exc}",
        )


@router.get("/{contract_id}/summary")
def get_contract_summary(contract_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    """Generate a contract summary using RAG retrieval and LLM synthesis."""

    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found.",
        )

    try:
        rag = RAGService()
        summary_result = rag.summarize_contract(contract_id=str(contract_id))
        return {
            "summary": summary_result.get("summary", ""),
            "key_points": summary_result.get("key_points", []),
            "parties": summary_result.get("parties", []),
        }
    except Exception as exc:
        logger.exception("Failed to summarize contract_id=%s", contract_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to summarize contract: {exc}",
        )


@router.delete("/{contract_id}")
def delete_contract(contract_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found.",
        )

    # Remove child clauses first since cascade rules are not configured yet.
    for clause in list(contract.clauses):
        db.delete(clause)

    db.delete(contract)
    db.commit()
    return {"message": "Contract deleted successfully"}
