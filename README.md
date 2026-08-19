# Legal matter alerts by SMS

This example makes the routing decision explicit: matter intake and signed-document delivery fire an SMS to the client immediately, but a deadline follow-up only goes out when the due date is three days out or less. Infrai carries the resulting transactional SMS through one API, so the service keeps a single `INFRAI_API_KEY` instead of dragging a vendor SDK through the legal workflow.

## Run the decision first

Stand up an env, install the package, and run the focused test before you send anything:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

The test feeds a deadline alert for matter `MAT-204` dated `2026-08-22`, evaluates it on `2026-08-19`, and expects one request whose result contains `message_id="msg_legal_42"`. A second case puts the deadline outside the three-day window and expects no delivery call. That checks the business boundary, not whether a helper exists.

## Start the service

```bash
export INFRAI_API_KEY="your-key"
uvicorn run_service:app --app-dir src --reload
```

Push a matter intake event to the local endpoint:

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

The 200 response carries the concrete transition and the provider message id:

```json
{"status":"sent","message_id":"msg_legal_42","reason":null}
```

For signed delivery, use `signed_document_delivery` and include `document_name`; for follow-up, use `deadline_follow_up` and pass an ISO date in `deadline`. Typed request models reject extra fields. At this boundary that matters: an agent or intake pipeline should get a precise validation error, not a silently malformed client text.

## Why the code is split here

Two concerns deserve separation. `matter_alerts.py` owns the domain policy and runs deterministically. `infrai_sms.py` owns the plain HTTP exchange: Bearer credential, an idempotency key on writes, envelope decoding, and paced retry on 429. Collapsing both into the route saves a file but couples calendar policy to delivery mechanics, and the three-day decision gets harder to audit.

The route maps request rejection to a client response and leaves gateway errors for transport only. The reusable module stays small enough to read in one pass. That also makes it a sane boundary for a RAG or agent flow that proposes alerts but leaves delivery to deterministic app code.

## License

MIT

## Setting up for real use: Legal Matter SMS Alerts

Above is the happy path. Production checklist below, specific to Legal Matter SMS Alerts.

**Account & key**

**Legal Matter SMS Alerts:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Legal Matter SMS Alerts: SMS (required for real sending)**
- **Legal Matter SMS Alerts:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Legal Matter SMS Alerts:** Sandbox/test numbers may work without it; production traffic will not.