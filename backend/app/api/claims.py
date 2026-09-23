import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db
from app.database.claim_schemas import (
    AdminInterventionRequest,
    ClaimDecisionRequest,
    ClaimDetailResponse,
    ClaimSummaryResponse,
    CreateClaimRequest,
    ProcessReturnRequest,
)
from app.services.claim_service import (
    ClaimNotFoundError,
    ClaimServiceError,
    DuplicateClaimError,
    InvalidClaimStateError,
    UnauthorizedClaimActionError,
    admin_override_claim,
    get_claim_detail,
    get_user_claims,
    process_claim_decision,
    process_item_return,
    request_claim,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/claims", tags=["claims"])


@router.post("", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
def create_claim(
    request: CreateClaimRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Request a claim on a suggested match."""
    user_id = db.ensure_user(current_user.uid)

    try:
        return request_claim(
            claimant_user_id=user_id,
            match_id=request.match_id,
            verification_notes=request.verification_notes,
            claim_explanation=request.claim_explanation,
        )
    except DuplicateClaimError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except UnauthorizedClaimActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ClaimNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Claim creation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create claim.",
        ) from exc


@router.get("/my-claims", response_model=list[ClaimSummaryResponse])
def list_my_claims(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List all claims involving the authenticated user."""
    user_id = db.ensure_user(current_user.uid)
    return get_user_claims(user_id)


@router.get("/{claim_id}", response_model=ClaimDetailResponse)
def get_claim(
    claim_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Get full details of a claim, associated items, and audit history."""
    user_id = db.ensure_user(current_user.uid)

    try:
        return get_claim_detail(claim_id, user_id)
    except ClaimNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except UnauthorizedClaimActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to retrieve claim detail: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve claim detail.",
        ) from exc


@router.post("/{claim_id}/decision", response_model=ClaimDetailResponse)
def handle_claim_decision(
    claim_id: int,
    request: ClaimDecisionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Approve, reject, or escalate a claim to administrator review."""
    user_id = db.ensure_user(current_user.uid)

    try:
        return process_claim_decision(
            claim_id=claim_id,
            user_id=user_id,
            decision=request.decision,
            notes=request.notes,
        )
    except ClaimNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except UnauthorizedClaimActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except InvalidClaimStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Claim decision failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process claim decision.",
        ) from exc


@router.post("/{claim_id}/admin-override", response_model=ClaimDetailResponse)
def handle_admin_override(
    claim_id: int,
    request: AdminInterventionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Administrative intervention to moderate and update claim status."""
    user_id = db.ensure_user(current_user.uid)

    try:
        return admin_override_claim(
            claim_id=claim_id,
            admin_user_id=user_id,
            new_status=request.new_status,
            admin_notes=request.admin_notes,
        )
    except ClaimNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Admin intervention failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process administrative intervention.",
        ) from exc


@router.post("/{claim_id}/return", response_model=ClaimDetailResponse)
@router.post("/{claim_id}/handover", response_model=ClaimDetailResponse)
def handle_item_return(
    claim_id: int,
    request: ProcessReturnRequest | None = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Process verified physical return and transition claim and items to RETURNED."""
    user_id = db.ensure_user(current_user.uid)
    handover_notes = request.handover_notes if request else None
    handover_location = request.handover_location if request else None

    try:
        return process_item_return(
            claim_id=claim_id,
            user_id=user_id,
            handover_notes=handover_notes,
            handover_location=handover_location,
        )
    except ClaimNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except UnauthorizedClaimActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except InvalidClaimStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Item return processing failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process item return.",
        ) from exc


@router.get("/{claim_id}/history", response_model=list[dict[str, Any]])
@router.get("/{claim_id}/audit", response_model=list[dict[str, Any]])
def get_claim_audit_history(
    claim_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Retrieve immutable audit history for a claim and its lifecycle."""
    user_id = db.ensure_user(current_user.uid)

    try:
        detail = get_claim_detail(claim_id, user_id)
        return detail.get("audit_history", [])
    except ClaimNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except UnauthorizedClaimActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to retrieve claim history: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve claim history.",
        ) from exc

