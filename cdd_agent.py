import os
import json
import httpx
from pydantic import BaseModel
from agents import (
    function_tool,
    FileSearchTool,
    Agent,
    ModelSettings,
    TResponseInputItem,
    Runner,
    RunConfig,
    trace,
)

# ---- Tool: Create case (calls your local case-service stub) ----
CASE_SERVICE_URL = os.getenv("CASE_SERVICE_URL", "http://127.0.0.1:5056/create-case")

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")


@function_tool
async def create_case(
    customer_id: str,
    risk_level: str,
    decision: str,
    reason_codes: list[str],
    cdd_summary: str,
):
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            CASE_SERVICE_URL,
            json={
                "customer_id": customer_id,
                "risk_level": risk_level,
                "decision": decision,
                "reason_codes": reason_codes,
                "cdd_summary": cdd_summary,
            },
        )
        resp.raise_for_status()
        return resp.json()

@function_tool
async def send_slack_message(
    channel: str,
    message: str
):
    """
    Send a message to Slack to request missing evidence or human input.
    """
    if not SLACK_WEBHOOK_URL:
        raise RuntimeError("SLACK_WEBHOOK_URL not set")

    payload = {
        "text": f"*CDD Evidence Request*\n{message}"
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(SLACK_WEBHOOK_URL, json=payload)
        resp.raise_for_status()

    return {"status": "sent"}

# ---- File search tool ----
file_search = FileSearchTool(
    vector_store_ids=["vs_693aa6ca38508191a2068912f304054c"]
)

# ---- Agent ----
cddagent = Agent(
    name="CDDAgent",
    instructions="""
Context: We are developing a Customer Due Diligence process for a gaming and betting company.

Role: You are a compliance expert in Gaming and betting industry who is well aware of the rules in EU and UK. You also know Agentic AI well.

Expectation: Evaluate the customer profile based on provided factors (e.g., identity, transactions, source of funds). Classify risk as LOW, MEDIUM, or HIGH. Identify cases needing review/intervention (e.g., EDD for PEPs). Ask for more details if data is incomplete. Be concise and factual. Avoid speculation.

Output format (MANDATORY):
Return a JSON object with keys:
- customer_id (string)
- risk_level ("LOW"|"MEDIUM"|"HIGH")
- decision ("CLEAR"|"MANUAL_REVIEW_REQUIRED"|"EDD_RECOMMENDED")
- reason_codes (array of strings)
- missing_evidence (array of strings)
- summary (string, concise)
- action_note (string)
- case_id (string, optional)
- case_url (string, optional)

Evidence rules (MANDATORY):
1) missing_evidence must list what is required but not present, chosen only from:
   - "SOURCE_OF_FUNDS"
   - "SOURCE_OF_WEALTH"
   - "PEP_STATUS"
   - "OCCUPATION"
   - "ADDRESS_PROOF"
   - "BENEFICIAL_OWNER"
2) If missing_evidence is non-empty:
   - Call send_slack_message with:
     channel="#cdd-reviews"
     message including customer_id, decision, risk_level, missing_evidence, and a 1-line ask.
3) If decision is MANUAL_REVIEW_REQUIRED or EDD_RECOMMENDED:
   - Call create_case (as before) and include case_id/case_url in final JSON.
4) Final output must be valid JSON (no extra text).
Slack message composition rules (MANDATORY):
When calling send_slack_message:
- Write a natural, professional message as a compliance analyst.
- Mention the Zendesk ticket ID and ticket URL.
- Clearly list the missing evidence in plain language.
- End with a clear ask and next step.

Slack message template guidance (do not quote verbatim):
"CDD review initiated for Customer <customer_id>.
A Zendesk case (<case_id>) has been created: <case_url>.
The following information is missing and required to proceed:
- <missing evidence items in plain English>
Please request these documents from the customer and update the case once received."
""",
    model="gpt-4.1",
    tools=[create_case,send_slack_message,file_search],
    model_settings=ModelSettings(
        temperature=0.2,
        top_p=1,
        parallel_tool_calls=True,
        max_tokens=1200,
        store=True,
    ),
)

class WorkflowInput(BaseModel):
    input_as_text: str

async def run_workflow(workflow_input: WorkflowInput):
    with trace("CDD"):
        conversation_history: list[TResponseInputItem] = [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": workflow_input.input_as_text}],
            }
        ]

        result = await Runner.run(
            cddagent,
            input=conversation_history,
            run_config=RunConfig(
                trace_metadata={
                    "__trace_source__": "local-api",
                    "workflow_id": "wf_69414bd0461c81908fda94ed7cb38a420fd79b5725e6aab4",
                }
            ),
        )

        # Return the agent's final output (should be JSON per instructions)
        return json.loads(result.final_output_as(str))
