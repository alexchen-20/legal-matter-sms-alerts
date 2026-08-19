from datetime import date

from legal_sms.matter_alerts import AlertRequest, MatterEvent, deliver_matter_alert


class RecordingSender:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def send(self, *, to: str, body: str, idempotency_key: str) -> dict[str, object]:
        self.calls.append({"to": to, "body": body, "idempotency_key": idempotency_key})
        return {"message_id": "msg_legal_42"}


def test_deadline_alert_is_sent_inside_three_day_window() -> None:
    sender = RecordingSender()
    alert = AlertRequest(
        matter_id="MAT-204",
        client_name="Avery Chen",
        phone_number="+15551234567",
        event=MatterEvent.DEADLINE,
        deadline=date(2026, 8, 22),
    )

    result = deliver_matter_alert(alert, sender, today=date(2026, 8, 19))

    assert result.status == "sent"
    assert result.message_id == "msg_legal_42"
    assert sender.calls == [
        {
            "to": "+15551234567",
            "body": (
                "Avery Chen, matter MAT-204 has a deadline on 2026-08-22. "
                "Please review the next steps."
            ),
            "idempotency_key": "matter:MAT-204:deadline_follow_up",
        }
    ]


def test_deadline_alert_is_skipped_before_window_opens() -> None:
    sender = RecordingSender()
    alert = AlertRequest(
        matter_id="MAT-204",
        client_name="Avery Chen",
        phone_number="+15551234567",
        event=MatterEvent.DEADLINE,
        deadline=date(2026, 8, 30),
    )

    result = deliver_matter_alert(alert, sender, today=date(2026, 8, 19))

    assert result.status == "skipped"
    assert result.reason == "deadline is outside the three-day window"
    assert sender.calls == []

