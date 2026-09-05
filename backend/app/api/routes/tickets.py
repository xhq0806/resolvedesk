from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.ticket import (
    CustomerReplyCreate,
    DeleteTicketRequest,
    TicketAssign,
    TicketAttributesUpdate,
    TicketCreate,
    TicketDetailPublic,
    TicketFilters,
    TicketMessageCreate,
    TicketMessagePublic,
    TicketsPublic,
    TicketStatisticsPublic,
    TicketStatusUpdate,
)
from app.services.statistics_service import StatisticsService
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("/statistics", response_model=TicketStatisticsPublic)
def read_ticket_statistics(
    session: SessionDep,
    current_user: CurrentUser,
) -> TicketStatisticsPublic:
    return StatisticsService(session).get_ticket_statistics(current_user)


@router.post("", response_model=TicketDetailPublic, status_code=status.HTTP_201_CREATED)
def create_ticket(
    session: SessionDep,
    current_user: CurrentUser,
    payload: TicketCreate,
) -> TicketDetailPublic:
    return TicketService(session).create_ticket(current_user, payload)


@router.get("", response_model=TicketsPublic)
def list_tickets(
    session: SessionDep,
    current_user: CurrentUser,
    filters: Annotated[TicketFilters, Depends()],
) -> TicketsPublic:
    return TicketService(session).list_tickets(current_user, filters)


@router.get("/{ticket_id}", response_model=TicketDetailPublic)
def read_ticket(
    session: SessionDep,
    current_user: CurrentUser,
    ticket_id: uuid.UUID,
) -> TicketDetailPublic:
    return TicketService(session).get_ticket(current_user, ticket_id)


@router.post("/{ticket_id}/claim", response_model=TicketDetailPublic)
def claim_ticket(
    session: SessionDep,
    current_user: CurrentUser,
    ticket_id: uuid.UUID,
) -> TicketDetailPublic:
    return TicketService(session).claim_ticket(current_user, ticket_id)


@router.put("/{ticket_id}/assignee", response_model=TicketDetailPublic)
def assign_ticket(
    session: SessionDep,
    current_user: CurrentUser,
    ticket_id: uuid.UUID,
    payload: TicketAssign,
) -> TicketDetailPublic:
    return TicketService(session).assign_ticket(current_user, ticket_id, payload)


@router.delete("/{ticket_id}/assignee", response_model=TicketDetailPublic)
def unassign_ticket(
    session: SessionDep,
    current_user: CurrentUser,
    ticket_id: uuid.UUID,
) -> TicketDetailPublic:
    return TicketService(session).unassign_ticket(current_user, ticket_id)


@router.post(
    "/{ticket_id}/replies",
    response_model=TicketMessagePublic,
    status_code=status.HTTP_201_CREATED,
)
def add_customer_reply(
    session: SessionDep,
    current_user: CurrentUser,
    ticket_id: uuid.UUID,
    payload: CustomerReplyCreate,
) -> TicketMessagePublic:
    return TicketService(session).add_customer_reply(current_user, ticket_id, payload)


@router.post(
    "/{ticket_id}/messages",
    response_model=TicketMessagePublic,
    status_code=status.HTTP_201_CREATED,
)
def add_staff_message(
    session: SessionDep,
    current_user: CurrentUser,
    ticket_id: uuid.UUID,
    payload: TicketMessageCreate,
) -> TicketMessagePublic:
    return TicketService(session).add_staff_message(current_user, ticket_id, payload)


@router.patch("/{ticket_id}/status", response_model=TicketDetailPublic)
def update_status(
    session: SessionDep,
    current_user: CurrentUser,
    ticket_id: uuid.UUID,
    payload: TicketStatusUpdate,
) -> TicketDetailPublic:
    return TicketService(session).update_status(current_user, ticket_id, payload)


@router.patch("/{ticket_id}/attributes", response_model=TicketDetailPublic)
def update_attributes(
    session: SessionDep,
    current_user: CurrentUser,
    ticket_id: uuid.UUID,
    payload: TicketAttributesUpdate,
) -> TicketDetailPublic:
    return TicketService(session).update_attributes(current_user, ticket_id, payload)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(
    session: SessionDep,
    current_user: CurrentUser,
    ticket_id: uuid.UUID,
    payload: DeleteTicketRequest,
) -> Response:
    TicketService(session).delete_ticket(current_user, ticket_id, payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
