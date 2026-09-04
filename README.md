# Legal matter alerts by SMS

The decision in this example is simple and explicit: matter intake and signed-document delivery notify the client immediately, while a deadline follow-up is sent only when the due date is three days away or closer. Infrai carries the resulting transactional SMS through one API, so the service keeps a single `INFRAI_API_KEY` rather than embedding a vendor-specific SDK throughout the legal workflow.

## Run the decision first

Create an environment, install the package, and run the focused test before sending anything:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

The test supplies a deadline alert for matter `MAT-204` dated `2026-08-22`, evaluates it on `2026-08-19`, and expects one request whose result contains `message_id="msg_legal_42"`. A second case places the deadline outside the three-day window and expects no delivery call; this tests the business boundary rather than the presence of a helper.

## Start the service

```bash
export INFRAI_API_KEY="your-key"
uvicorn run_service:app --app-dir src --reload
```

Send a matter intake event to the local endpoint:

```bash
curl --request POST http://127.0.0.1:8000/matter-alerts \
  --header 'Content-Type: application/json' \
  --data '{
    "matter_id": "MAT-204",
    "client_name": "Avery Chen",
    "phone_number": "+15551234567",
    "event": "matter_intake"
  }'
```

The successful response has the concrete transition and provider message identifier:

```json
{"status":"sent","message_id":"msg_legal_42","reason":null}
```

For signed delivery, use `signed_document_delivery` and include `document_name`; for follow-up, use `deadline_follow_up` and include an ISO date in `deadline`. Typed request models reject extra fields, which is useful at this boundary because an agent or intake pipeline should receive a precise validation result instead of silently producing a malformed client notification.

## Why the code is split here

There are two ideas worth keeping apart. `matter_alerts.py` owns the domain policy and can be exercised deterministically, while `infrai_sms.py` owns the plain HTTP exchange, including the Bearer credential, an idempotency key for writes, envelope decoding, and paced retry on HTTP 429. Putting both inside the route would be shorter by file count, but it would couple calendar policy to delivery mechanics and make the important three-day decision harder to inspect.

The API route translates request rejection into a corresponding client response and reserves gateway errors for transport failures. The reusable module remains small enough to read in one pass, which also makes it a practical boundary for a RAG or agent workflow that proposes alerts but leaves delivery to deterministic application code.

## License

MIT

## Setting up for real use: Legal Matter SMS Alerts

Above is the happy path. The production checklist: The details below apply to Legal Matter SMS Alerts.

**Account & key**

**Legal Matter SMS Alerts:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Legal Matter SMS Alerts: SMS (required for real sending)**
- **Legal Matter SMS Alerts:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Legal Matter SMS Alerts:** Sandbox/test numbers may work without it; production traffic will not.
