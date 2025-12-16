Agentic CDD Case – MVP Documentation
1. Overview

This project implements an agentic Customer Due Diligence (CDD) workflow for a gaming and betting company operating under EU and UK regulations.

Unlike traditional rule-based automation (RPA / low-code), this system delegates decision authority to an AI agent, while keeping execution, auditability, and compliance controls in the backend.

The agent:

Evaluates customer risk

Identifies missing evidence

Decides whether to request information or escalate

Triggers human workflows (Slack, Zendesk) via tools

2. Why This Is Agentic (and Not RPA + LLM)
Traditional Automation (RPA + LLM)

Rules are pre-defined in code

LLM is used only for extraction or summarisation

Actions are deterministic and always executed

No notion of uncertainty or deferral

This System

The agent owns the decision

Tools are optional actions, not fixed steps

The agent can:

Act (create case)

Defer (request evidence)

Escalate (EDD)

Refuse to act

Control flow emerges from reasoning, not scripts

This marks a shift from automation to decision delegation.

3. High-Level Architecture
User / System Trigger
        ↓
   CDD Agent (LLM)
        ↓
Decision + Justification (JSON)
        ↓
┌───────────────┬─────────────────┐
│ Slack Tool    │ Zendesk Tool    │
│ (Info Request)│ (Case Creation)│
└───────────────┴─────────────────┘

Key Separation of Concerns
Layer	Responsibility
Agent (LLM)	Reasoning & decision
Tools	Side effects
Backend (Python)	Secrets, retries, idempotency
External Systems	Slack, Zendesk
4. Agent Responsibilities

The agent evaluates:

Identity verification (KYC)

Transaction behaviour

AML alerts

Source of funds / wealth

PEP status

Evidence completeness

The agent outputs structured JSON and never free text.

5. Decision Model
Risk Levels

LOW

MEDIUM

HIGH

Decisions

CLEAR

MANUAL_REVIEW_REQUIRED

EDD_RECOMMENDED

6. Evidence Awareness (Key Agentic Capability)

The agent explicitly tracks what is missing, using a constrained vocabulary:

"missing_evidence": [
  "SOURCE_OF_FUNDS",
  "PEP_STATUS",
  "OCCUPATION",
  "ADDRESS_PROOF"
]


This allows the agent to:

Ask for information instead of escalating

Avoid premature ticket creation

Explain why action is blocked

7. Action Policy (Core Logic)
Rule 1 – Missing Evidence

If missing_evidence is non-empty:

✅ Send Slack message requesting documents

❌ Do NOT create Zendesk case

Decision remains MANUAL_REVIEW_REQUIRED

Rule 2 – Normal Escalation

If evidence is complete AND decision requires review:

Create Zendesk case

Return case_id and case_url

Rule 3 – Mandatory Override

Even if evidence is missing, always create a Zendesk case if:

Risk level is HIGH, OR

An active AML alert exists

This mirrors real AML operations.

8. Slack Integration (Human-in-the-Loop)

Slack is used for information gathering, not escalation.

Messages are:

Natural language

Written as a compliance analyst

Explicit about what is missing

Actionable

Example:

CDD review initiated for Customer 2022.

The following information is required to proceed:
• Source of Funds
• PEP Status
• Occupation
• Address Proof

Please request these documents from the customer and update the case once received.

9. Zendesk Integration (Formal Case Management)

Zendesk cases are created only when justified.

Each case:

Is idempotent (no duplicates)

Contains reasoning context

Links back to the agent’s decision

This ensures:

Auditability

Traceability

Human override capability

10. Example Final Agent Output
{
  "customer_id": "2022",
  "risk_level": "MEDIUM",
  "decision": "MANUAL_REVIEW_REQUIRED",
  "reason_codes": [
    "INCOMPLETE_CDD",
    "MISSING_SOURCE_OF_FUNDS"
  ],
  "missing_evidence": [
    "SOURCE_OF_FUNDS",
    "PEP_STATUS"
  ],
  "summary": "Customer 2022 has incomplete CDD data. No transaction alerts present.",
  "action_note": "Evidence requested via Slack. Await documents before opening a case."
}

11. What Makes This Production-Ready (Even as MVP)

Structured outputs (no prompt parsing)

Tool execution outside the model

Secrets never exposed to the agent

Idempotent case creation

Human-in-the-loop by design

Clear escalation boundaries

12. What This Enables Next

This foundation can be extended to:

Time-based escalation (no response → auto case)

Re-evaluation when evidence arrives

Cross-case memory

Confidence scoring

Multi-jurisdiction policy tuning

13. One-Line Summary

This system demonstrates a true agentic CDD workflow, where an AI agent owns risk decisions and selectively triggers human and system actions, rather than executing a predefined automation script.
