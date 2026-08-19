from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Protocol


class MatterEvent(str, Enum):
    INTAKE = "matter_intake"
    SIGNED_DOCUMENT = "signed_document_delivery"
    DEADLINE = "deadline_follow_up"


@dataclass(frozen=True)
class AlertRequest:
    matter_id: str
    client_name: str
    phone_number: str
    event: MatterEvent
    document_name: str | None = None
    deadline: date | None = None


@dataclass(frozen=True)
class AlertResult:
    status: str
    message_id: str | None
    reason: str | None = None


class SmsSender(Protocol):
    def send(self, *, to: str, body: str, idempotency_key: str) -> dict[str, object]: ...


def deliver_matter_alert(
    alert: AlertRequest, sender: SmsSender, *, today: date | None = None
) -> AlertResult:
    """Choose the legal notification, then make the delivery decision observable."""
    current_day = today or date.today()

    if alert.event is MatterEvent.INTAKE:
        body = f"{alert.client_name}, matter {alert.matter_id} has been opened."
    elif alert.event is MatterEvent.SIGNED_DOCUMENT:
        document = alert.document_name or "Your signed document"
        body = f"{alert.client_name}, {document} is ready for matter {alert.matter_id}."
    else:
        if alert.deadline is None:
            raise ValueError("deadline is required for deadline follow-up")
        days_remaining = (alert.deadline - current_day).days
        if days_remaining > 3:
            return AlertResult("skipped", None, "deadline is outside the three-day window")
        body = (
            f"{alert.client_name}, matter {alert.matter_id} has a deadline on "
            f"{alert.deadline.isoformat()}. Please review the next steps."
        )

    delivery = sender.send(
        to=alert.phone_number,
        body=body,
        idempotency_key=f"matter:{alert.matter_id}:{alert.event.value}",
    )
    return AlertResult("sent", str(delivery["message_id"]))

