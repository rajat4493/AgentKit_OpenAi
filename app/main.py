from fastapi import FastAPI
from pydantic import BaseModel
from cdd_agent import run_workflow, WorkflowInput
import os
import base64
import httpx

CASE_REGISTRY = {}
app = FastAPI()

ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN")
ZENDESK_EMAIL = os.getenv("ZENDESK_EMAIL")
ZENDESK_API_TOKEN = os.getenv("ZENDESK_API_TOKEN")

class RunCDDRequest(BaseModel):
    customer_id: str

@app.post("/run-cdd")
async def run_cdd(req: RunCDDRequest):
    return await run_workflow(
        WorkflowInput(input_as_text=f"Run CDD for customer {req.customer_id} using available sources.")
    )

@app.post("/create-case")
async def create_case(payload: dict):
    customer_id = payload.get("customer_id")
    decision = payload.get("decision")
    risk_level = payload.get("risk_level")
    reason_codes = sorted(payload.get("reason_codes", []))
    cdd_summary = payload.get("cdd_summary", "")

    # Idempotency key (local + also send to Zendesk)
    case_key = f"{customer_id}:{decision}:{'|'.join(reason_codes)}"
    if case_key in CASE_REGISTRY:
        return CASE_REGISTRY[case_key]

    if not (ZENDESK_SUBDOMAIN and ZENDESK_EMAIL and ZENDESK_API_TOKEN):
        raise RuntimeError("Zendesk env vars missing: ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, ZENDESK_API_TOKEN")

    url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/tickets.json"

    subject = f"CDD {decision}: Customer {customer_id} ({risk_level}) - " + ", ".join(reason_codes[:2])
    body = (
        f"CDD Case\n\n"
        f"Customer: {customer_id}\n"
        f"Decision: {decision}\n"
        f"Risk: {risk_level}\n"
        f"Reasons: {', '.join(reason_codes)}\n\n"
        f"Summary:\n{cdd_summary}\n"
    )

    # Basic auth: email/token + api_token :contentReference[oaicite:3]{index=3}
    auth_str = f"{ZENDESK_EMAIL}/token:{ZENDESK_API_TOKEN}"
    b64 = base64.b64encode(auth_str.encode()).decode()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            headers={
                "Authorization": f"Basic {b64}",
                "Content-Type": "application/json",
                "Idempotency-Key": case_key,  # Zendesk idempotency :contentReference[oaicite:4]{index=4}
            },
            json={
                "ticket": {
                    "subject": subject,
                    "comment": {"body": body},
                    "tags": ["cdd", "aml", decision.lower(), f"risk_{risk_level.lower()}", f"customer_{customer_id}"],
                    "priority": "normal",
                }
            },
        )
        resp.raise_for_status()
        data = resp.json()

    ticket_id = str(data["ticket"]["id"])
    case = {
        "case_id": ticket_id,
        "case_url": f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/agent/tickets/{ticket_id}",
        "provider": "zendesk",
    }

    CASE_REGISTRY[case_key] = case
    return case
