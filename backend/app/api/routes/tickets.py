from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentUser, SessionDep, WorkspaceContextDep
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
    context: WorkspaceContextDep,
) -> TicketStatisticsPublic:
    return StatisticsService(session).get_ticket_statistics(current_user, context=context)


@router.post("", response_model=TicketDetailPublic, status_code=status.HTTP_201_CREATED)
def create_ticket(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    payload: TicketCreate,
) -> TicketDetailPublic:
    return TicketService(session).create_ticket(current_user, payload, context=context)


@router.get("", response_model=TicketsPublic)
def list_tickets(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    filters: Annotated[TicketFilters, Depends()],
) -> TicketsPublic:
    return TicketService(session).list_tickets(current_user, filters, context=context)


@router.get("/{ticket_id}", response_model=TicketDetailPublic)
def read_ticket(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    ticket_id: uuid.UUID,
) -> TicketDetailPublic:
    return TicketService(session).get_ticket(current_user, ticket_id, context=context)


@router.post("/{ticket_id}/claim", response_model=TicketDetailPublic)
def claim_ticket(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    ticket_id: uuid.UUID,
) -> TicketDetailPublic:
    return TicketService(session).claim_ticket(current_user, ticket_id, context=context)


@router.put("/{ticket_id}/assignee", response_model=TicketDetailPublic)
def assign_ticket(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    ticket_id: uuid.UUID,
    payload: TicketAssign,
) -> TicketDetailPublic:
    return TicketService(session).assign_ticket(
        current_user, ticket_id, payload, context=context
    )


@router.delete("/{ticket_id}/assignee", response_model=TicketDetailPublic)
def unassign_ticket(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    ticket_id: uuid.UUID,
) -> TicketDetailPublic:
    return TicketService(session).unassign_ticket(
        current_user, ticket_id, context=context
    )


@router.post(
    "/{ticket_id}/replies",
    response_model=TicketMessagePublic,
    status_code=status.HTTP_201_CREATED,
)
def add_customer_reply(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    ticket_id: uuid.UUID,
    payload: CustomerReplyCreate,
) -> TicketMessagePublic:
    return TicketService(session).add_customer_reply(
        current_user, ticket_id, payload, context=context
    )


@router.post(
    "/{ticket_id}/messages",
    response_model=TicketMessagePublic,
    status_code=status.HTTP_201_CREATED,
)
def add_staff_message(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    ticket_id: uuid.UUID,
    payload: TicketMessageCreate,
) -> TicketMessagePublic:
    return TicketService(session).add_staff_message(
        current_user, ticket_id, payload, context=context
    )


@router.patch("/{ticket_id}/status", response_model=TicketDetailPublic)
def update_status(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    ticket_id: uuid.UUID,
    payload: TicketStatusUpdate,
) -> TicketDetailPublic:
    return TicketService(session).update_status(
        current_user, ticket_id, payload, context=context
    )


@router.patch("/{ticket_id}/attributes", response_model=TicketDetailPublic)
def update_attributes(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    ticket_id: uuid.UUID,
    payload: TicketAttributesUpdate,
) -> TicketDetailPublic:
    return TicketService(session).update_attributes(
        current_user, ticket_id, payload, context=context
    )


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(
    session: SessionDep,
    current_user: CurrentUser,
    context: WorkspaceContextDep,
    ticket_id: uuid.UUID,
    payload: DeleteTicketRequest,
) -> Response:
    TicketService(session).delete_ticket(
        current_user, ticket_id, payload, context=context
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
