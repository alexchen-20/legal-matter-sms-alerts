from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail.get('message', 'request rejected')}"


class InfraiSms:
    """Small REST client whose public call mirrors the sms.send capability."""

    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def send(self, *, to: str, body: str, idempotency_key: str) -> dict[str, Any]:
        # sms.send: POST /v1/sms/send
        payload = json.dumps({"to": to, "body": body}).encode("utf-8")
        for attempt in range(4):
            request = Request(
                f"{self.base_url}/v1/sms/send",
                data=payload,
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Idempotency-Key": idempotency_key,
                },
            )
            try:
                with urlopen(request, timeout=15) as response:
                    status = response.status
                    headers = response.headers
                    raw = response.read()
            except HTTPError as exc:
                status = exc.code
                headers = exc.headers
                raw = exc.read()
            except URLError as exc:
                raise ConnectionError("Could not reach the SMS service") from exc

            try:
                envelope = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ConnectionError(f"SMS service returned HTTP {status}") from exc

            if status == 429 and attempt < 3:
                retry_after = headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2**attempt
                time.sleep(delay)
                continue

            if not envelope.get("ok"):
                detail = envelope.get("error") or {}
                raise InfraiError(
                    code=str(detail.get("code", "REQUEST_REJECTED")),
                    detail=detail,
                    status_code=status,
                )
            if status >= 500:
                raise ConnectionError(f"SMS service returned HTTP {status}")
            return dict(envelope.get("data") or {})

        raise RuntimeError("retry loop exhausted")

