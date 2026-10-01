"""RFP upload routes. Agent decisions live in data.pipelines.rfp_intake."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlmodel import Session

from app.core.deps import get_current_user
from app.db.database import get_db, get_engine
from app.schemas.rfp import RfpTicketCreated, RfpTicketPublic
from app.schemas.user import UserInDB
from app.services import rfp_service

router = APIRouter(prefix="/rfp", tags=["rfp-intake"])


def _run_in_background(ticket_id: str, pdf_bytes: bytes) -> None:
    """Open a new session. The request session is already closed."""
    with Session(get_engine()) as session:
        rfp_service.run_ticket(session, ticket_id, pdf_bytes)


@router.post("/tickets", response_model=RfpTicketCreated, status_code=status.HTTP_202_ACCEPTED)
async def create_rfp_ticket(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
    _current_user: UserInDB = Depends(get_current_user),
) -> RfpTicketCreated:
    """Accept a PDF, store an analyzing ticket, and return before the pipeline finishes."""
    filename = (file.filename or "").lower()
    if not filename.endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only PDF uploads are accepted.")
    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The PDF is empty.")
    ticket = rfp_service.create_ticket(session)
    background_tasks.add_task(_run_in_background, ticket.ticket_id, pdf_bytes)
    return RfpTicketCreated(ticket_id=ticket.ticket_id, status=ticket.status)


def _run_response_in_background(ticket_id: str) -> None:
    """Open a new session. The request session is already closed."""
    with Session(get_engine()) as session:
        rfp_service.run_response(session, ticket_id)


@router.post(
    "/tickets/{ticket_id}/response",
    response_model=RfpTicketCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_rfp_response(
    ticket_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
    _current_user: UserInDB = Depends(get_current_user),
) -> RfpTicketCreated:
    """Start Part 2 from the stored handoff. This route does not read the PDF."""
    try:
        ticket = rfp_service.begin_response(session, ticket_id)
    except rfp_service.ResponseNotReady as exc:
        if exc.code == "ticket_missing":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.") from exc
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.code) from exc
    background_tasks.add_task(_run_response_in_background, ticket.ticket_id)
    return RfpTicketCreated(ticket_id=ticket.ticket_id, status=ticket.status)


@router.get("/tickets/{ticket_id}", response_model=RfpTicketPublic)
def read_rfp_ticket(
    ticket_id: str,
    session: Session = Depends(get_db),
    _current_user: UserInDB = Depends(get_current_user),
) -> RfpTicketPublic:
    """Return the current ticket. A stalled flag does not change the stored status."""
    ticket = rfp_service.get_ticket(session, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")
    return ticket
