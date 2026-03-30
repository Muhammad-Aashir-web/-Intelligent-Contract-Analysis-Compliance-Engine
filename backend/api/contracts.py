from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.contract import Contract
from models.user import User

router = APIRouter(prefix="/contracts", tags=["Contracts"])

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


@router.post("/upload", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
async def upload_contract(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Contract:
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

    user = _get_or_create_placeholder_user(db)

    contract = Contract(
        title=Path(file.filename or "untitled").stem,
        file_name=file.filename or "untitled",
        file_path=None,
        file_size=file_size,
        contract_type="DOCX" if extension == ".docx" else "PDF",
        status="pending",
        user_id=user.id,
    )

    try:
        db.add(contract)
        db.commit()
        db.refresh(contract)
        return contract
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save contract metadata.",
        )
    finally:
        await file.close()


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

    if contract.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail="Analysis not complete yet.",
        )

    # Placeholder result payload until analysis outputs are persisted.
    return {
        "contract_id": contract.id,
        "status": contract.status,
        "risk_score": contract.risk_score,
        "risk_level": contract.risk_level,
        "summary": contract.summary,
    }


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
