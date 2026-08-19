from __future__ import annotations

import os
from datetime import date
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

from legal_sms.infrai_sms import InfraiError, InfraiSms
from legal_sms.matter_alerts import AlertRequest, MatterEvent, deliver_matter_alert


class MatterAlertBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    matter_id: str
    client_name: str
    phone_number: str
    event: Literal["matter_intake", "signed_document_delivery", "deadline_follow_up"]
    document_name: str | None = None
    deadline: date | None = None


class MatterAlertResponse(BaseModel):
    status: Literal["sent", "skipped"]
    message_id: str | None
    reason: str | None


app = FastAPI(title="Legal matter SMS alerts")


@app.post("/matter-alerts", response_model=MatterAlertResponse)
def create_matter_alert(body: MatterAlertBody) -> MatterAlertResponse:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="INFRAI_API_KEY is not configured")

    alert = AlertRequest(
        matter_id=body.matter_id,
        client_name=body.client_name,
        phone_number=body.phone_number,
        event=MatterEvent(body.event),
        document_name=body.document_name,
        deadline=body.deadline,
    )
    try:
        result = deliver_matter_alert(alert, InfraiSms(api_key))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail=exc.detail) from exc

    return MatterAlertResponse(
        status=result.status,
        message_id=result.message_id,
        reason=result.reason,
    )

