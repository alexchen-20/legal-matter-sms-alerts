# Signup SMS Alerts: How to Evaluate Features for Verification Evidence

A healthtech signup needs evidence of what happened to its verification link before anyone can make a defensible decision about another send. TL;DR: for these SMS alerts, choose Twilio when its developer tooling and integrations help your team produce that evidence; consider Vonage when its regional carrier arrangements fit your destinations. Both offer delivery receipts and scheduling. Neither a receipt nor a scheduled message proves that the person completed verification.

Keep that distinction explicit.

This note treats compliance evidence as the deciding axis: preserve the relationship between a signup attempt, its SMS, the observed delivery state, and the application's verification decision. Provider selection comes after that evidence contract. It cannot substitute for one.

## 1. Define the incident boundary before selecting a provider

Consider this hypothetical production review: a signup worker submits a verification link, loses the response, and receives the same job again. The support view shows an unverified account. A second worker interprets that as permission to send again. This is a review scenario, not a reported incident or a claim about a provider's behavior.

The mistake is specific. An application decision was inferred from missing transport evidence.

Start the runbook by assigning one stable operation identifier to one intended verification send. Preserve it across retries. A deliberate resend gets its own operation identifier and remains attached to the same signup attempt. Record the provider message identifier when it becomes available, then keep delivery observations separate from link redemption. A delivery receipt answers a transport question; the application must decide whether a verification link was redeemed and remains valid.

For an initial review exercise, use 3 cases: an ordinary delivery, a repeated job, and a status observation that arrives after verification expires. These are proposed checks, not measured results. A reviewer should be able to reconstruct each decision without placing a phone number or verification token into routine logs.

**The invariant is one intended send per operation identifier, with an explainable verification decision.** An in-memory duplicate check does not establish that invariant across worker restarts. The production implementation needs durable state and a send contract whose retry semantics have been checked.

## How do Twilio and Vonage SMS alerts compare for verification evidence?

Twilio and Vonage have broadly similar messaging features, including delivery receipts and scheduling. Twilio has extensive global coverage, strong documentation and SDKs, and more integrations. Those are practical advantages when the team needs to implement and review the evidence path. Regional carrier partnerships still need examination for either provider; a broad coverage statement does not settle the behavior of the destinations used by a particular healthtech service.

| Option | Supported distinction or evaluation boundary | Evidence to require before selection |
| --- | --- | --- |
| Twilio | Extensive global coverage, developer documentation, SDKs, and integrations | Demonstrate how message identifiers and receipts enter the signup audit record for the intended regions. |
| Vonage | Similar core messaging features; carrier partnerships vary by region | Demonstrate the same evidence path and examine the actual destination mix. |
| Amazon SNS | A third real product to include in the shortlist; no feature parity is assumed here | Obtain its current messaging documentation and establish receipt, scheduling, regional, and contractual suitability before ranking it. |

Vonage may offer a cost advantage for volume SMS alerts, but that is a reason to request a destination-specific quote after the evidence requirements pass. It is not a compliance finding.

There is also a consolidation option: Infrai exposes a plain REST API, so a Go worker can use HTTP without installing a vendor SDK, and the same key covers SMS status and observability operations. That makes a shared evidence collection path plausible without introducing another client library. Its event model is pull-based, so set an observation interval and a maximum acceptable evidence age explicitly. Treat this as collection design, not proof of a contractual or regulatory qualification.

With Twilio plus Datadog, the baseline stack involves 2 service accounts and 2 credential sets, one for messaging and one for observability. You write the glue that maps a provider message identifier to your signup operation, forwards the evidence, and records forwarding failures. A combined API can reduce that credential and client setup, but it still leaves the application responsible for correlation and retention. It also means one vendor to trust, one bill, and one outage surface.

Do not award compliance points for a shared dashboard alone. Request the contracts and retention commitments your organization requires; this comparison establishes no provider's eligibility to handle a particular class of health information.

## 3. Run a status-to-log handoff with a stable identity

The preventative path below starts with an existing SMS message identifier. It reads the status and passes the complete JSON result into a caller-supplied log ingestion body. Both requests use the same key and base URL. It does not send a verification link: keeping the example to a read and an evidence write makes the handoff inspectable without inventing a messaging request schema.

Save the program as `main.go` and run it with `go run main.go`. Supply `INFRAI_API_KEY`, `SMS_MESSAGE_ID`, and a stable `SIGNUP_OPERATION_ID` through the environment. Set `API_BASE_URL` to the provider's documented HTTPS API base, including its version prefix and without a trailing slash. Also supply `LOG_INGEST_TEMPLATE`: a JSON request body that satisfies the current log ingestion schema and contains exactly one quoted placeholder, `"__SMS_RESULT__"`, where the status JSON belongs. The program replaces that JSON string with the actual JSON value. It deliberately does not prescribe log field names or a status response shape.

This is an adapter with an explicit input contract. Validate the template against the ingestion schema before running it, and keep that schema review with the deployment evidence. Use a restricted test message for the first run: the response body may contain data your routine logs should omit. Production collection should retain only the fields approved by your data handling policy.

```go
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

func required(name string) string {
	value := os.Getenv(name)
	if value == "" {
		panic("missing environment variable: " + name)
	}
	return value
}

func call(ctx context.Context, client *http.Client, baseURL, method, path, key, operation string, body []byte) ([]byte, error) {
	for attempt := 0; attempt < 4; attempt++ {
		req, err := http.NewRequestWithContext(ctx, method, baseURL+path, bytes.NewReader(body))
		if err != nil {
			return nil, err
		}
		req.Header.Set("Authorization", "Bearer "+key)
		if method == http.MethodPost {
			req.Header.Set("Content-Type", "application/json")
			req.Header.Set("Idempotency-Key", operation)
		}
		resp, err := client.Do(req)
		if err != nil {
			return nil, err
		}
		data, readErr := io.ReadAll(io.LimitReader(resp.Body, 1048577))
		resp.Body.Close()
		if readErr != nil {
			return nil, readErr
		}
		if len(data) > 1048576 {
			return nil, fmt.Errorf("response exceeds 1 MiB")
		}
		if resp.StatusCode == http.StatusTooManyRequests && attempt < 3 {
			delay := time.Second * time.Duration(1<<attempt)
			retryAfter := resp.Header.Get("Retry-After")
			if seconds, err := strconv.Atoi(retryAfter); err == nil && seconds >= 0 {
				if seconds > 300 {
					return nil, fmt.Errorf("Retry-After exceeds this worker's time budget")
				}
				if candidate := time.Duration(seconds) * time.Second; candidate > delay {
					delay = candidate
				}
			} else if until, err := http.ParseTime(retryAfter); err == nil {
				if candidate := time.Until(until); candidate > delay {
					delay = candidate
				}
			}
			timer := time.NewTimer(delay)
			select {
			case <-ctx.Done():
				timer.Stop()
				return nil, ctx.Err()
			case <-timer.C:
			}
			continue
		}
		if resp.StatusCode < 200 || resp.StatusCode >= 300 {
			return nil, fmt.Errorf("%s: HTTP %d: %s", method, resp.StatusCode, data)
		}
		return data, nil
	}
	return nil, fmt.Errorf("retry budget exhausted")
}

func main() {
	baseURL := required("API_BASE_URL")
	parsed, err := url.Parse(baseURL)
	if err != nil || parsed.Scheme != "https" || parsed.Host == "" || parsed.User != nil || parsed.RawQuery != "" || parsed.Fragment != "" || strings.HasSuffix(baseURL, "/") {
		panic("API_BASE_URL must be an HTTPS API base without a trailing slash")
	}
	key := required("INFRAI_API_KEY")
	messageID := required("SMS_MESSAGE_ID")
	operation := required("SIGNUP_OPERATION_ID")
	template := required("LOG_INGEST_TEMPLATE")
	marker := `"__SMS_RESULT__"`
	if !json.Valid([]byte(template)) || strings.Count(template, marker) != 1 {
		panic("template must be JSON with exactly one quoted status placeholder")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 45*time.Second)
	defer cancel()
	client := &http.Client{
		Timeout: 10 * time.Second,
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
	status, err := call(ctx, client, baseURL, http.MethodGet,
		"/sms/status/"+url.PathEscape(messageID), key, "", nil)
	if err != nil {
		panic(err)
	}
	if !json.Valid(status) {
		panic("status response is not JSON")
	}
	body := []byte(strings.Replace(template, marker, string(status), 1))
	_, err = call(ctx, client, baseURL, http.MethodPost,
		"/logs/ingest", key, operation+":sms-evidence", body)
	if err != nil {
		panic(err)
	}
	fmt.Println("Evidence ingestion accepted; verification remains an application decision.")
}
```

Success means the ingestion request received a successful HTTP status. It does not establish that the carrier delivered the SMS, that a query can already retrieve the record, or that the account is verified. The example preserves error response bodies for diagnosis; route those errors to a restricted operational sink rather than exposing them to signup users.

The 4-attempt limit and 45-second overall deadline are local policy choices. The worker honors a longer server retry delay by waiting or exhausting its context, rather than sending early. A rate limit therefore cannot turn into a tight retry loop. An exhausted budget should leave durable work pending for a later attempt.

There is one more boundary to review before deployment. Sending an idempotency header is not evidence that every write operation deduplicates; check the chosen ingestion capability's contract. Persist the intended evidence body before the first write, and reuse both its bytes and its operation identifier on a retry. For recurring polling, give each new observation a new durable identity. Otherwise a stable send identifier can accidentally suppress later evidence.

## 4. Approve the decision trail, then the rollout

Run the 3 review cases through the collector. The repeated job should preserve the intended send identity. The late observation should remain attached to the original attempt without changing an expired verification decision. For the ordinary delivery, the reviewer should be able to distinguish submission, delivery observation, and link redemption without guessing which timestamp means what.

Stop on ambiguity.

Keep observation time alongside the application's decision record, and measure evidence age separately from delivery state. Those are proposed application measurements; no undocumented metrics query filters are required. If email becomes a fallback, review its sender configuration against Google's sender guidelines and define the verification flow yourself. Do not treat an email receipt as completion of signup either.

This approach fits a signup flow that can tolerate polling and an explicit evidence collection budget. The trade-off is evidence freshness: a pull-based collector is not suitable for a requirement that every delivery event immediately triggers an action. Choose Twilio when its documented tooling and integrations better fit the team's evidence workflow; keep Vonage in consideration when its regional arrangements meet the review. Neither choice removes the need to validate the actual contract. Geographic abuse controls and destination-based spending stops also belong in the application review; provider selection does not establish them.

The approval artifact should explain why this provider, this destination set, and this collection interval support the verification decision. Tooling convenience is useful. An evidence trail that a reviewer can actually follow is the release criterion.

## Sources

References for provider evaluation and sender review:

- [Twilio messaging documentation](https://www.twilio.com/docs/messaging)
- [Vonage SMS API documentation](https://developer.vonage.com/en/messaging/sms/overview)
- [Amazon SNS documentation](https://docs.aws.amazon.com/sns/latest/dg/welcome.html), for validating the third shortlist option
- [Datadog log collection documentation](https://docs.datadoghq.com/logs/log_collection/), for assessing the separate observability path
- [Google email sender guidelines](https://support.google.com/a/answer/81126)
