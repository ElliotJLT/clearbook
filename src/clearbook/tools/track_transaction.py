"""Map a conveyancing update to the transaction timeline."""

from typing import Annotated, Literal

from pydantic import Field

from clearbook.app import mcp

try:
    from mcp.types import ToolAnnotations
except ImportError:
    ToolAnnotations = None  # type: ignore[assignment,misc]


_tool_kwargs: dict = {}
if ToolAnnotations is not None:
    _tool_kwargs["annotations"] = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

STAGES = {
    "instruction": {
        "number": 1,
        "name": "Instruction",
        "description": "Solicitor instructed and ID/source-of-funds checks underway.",
        "typical_week": "Week 1",
        "next_steps": [
            "Provide ID documents and proof of funds to your solicitor",
            "Confirm your mortgage agreement in principle",
            "Your solicitor will write to the seller's solicitor",
        ],
        "typical_weeks_remaining": "11–15 weeks to completion",
    },
    "searches_ordered": {
        "number": 2,
        "name": "Searches ordered",
        "description": (
            "Your solicitor has ordered property searches (local authority, "
            "environmental, drainage, chancel repair). Results take 2–6 weeks "
            "depending on the council."
        ),
        "typical_week": "Week 2",
        "next_steps": [
            "No action needed from you — wait for results",
            "Your solicitor may also request the title documents from Land Registry",
            "Good time to arrange your survey if not already done",
        ],
        "typical_weeks_remaining": "10–14 weeks to completion",
    },
    "searches_received": {
        "number": 3,
        "name": "Search results received",
        "description": "Search results are back. Your solicitor will review them for any issues.",
        "typical_week": "Weeks 4–6",
        "next_steps": [
            "Your solicitor will flag any concerns from the searches",
            "If issues are found, they'll raise enquiries with the seller's solicitor",
            "Review any concerns flagged by your solicitor",
        ],
        "typical_weeks_remaining": "8–12 weeks to completion",
    },
    "enquiries_raised": {
        "number": 4,
        "name": "Enquiries raised",
        "description": (
            "Your solicitor has sent pre-contract enquiries to the seller's solicitor. "
            "These are questions about the property, boundaries, disputes, and planning."
        ),
        "typical_week": "Weeks 3–5",
        "next_steps": [
            "Wait for replies — this can take 2–4 weeks",
            "Your solicitor may have follow-up questions",
            "Review the property information form (TA6) when available",
        ],
        "typical_weeks_remaining": "8–12 weeks to completion",
    },
    "survey_complete": {
        "number": 5,
        "name": "Survey completed",
        "description": (
            "Your property survey has been completed and the report is available."
        ),
        "typical_week": "Weeks 3–5",
        "next_steps": [
            "Review the survey report carefully",
            "Discuss any Condition 3 (urgent) items with your solicitor",
            "Consider specialist reports if recommended by the surveyor",
            "If significant defects, consider renegotiating the price",
        ],
        "typical_weeks_remaining": "8–12 weeks to completion",
    },
    "mortgage_offer": {
        "number": 6,
        "name": "Mortgage offer received",
        "description": (
            "Your lender has issued a formal mortgage offer. This confirms the "
            "amount they'll lend and the conditions."
        ),
        "typical_week": "Weeks 4–6",
        "next_steps": [
            "Review the mortgage offer carefully (check rate, term, conditions)",
            "Sign and return the mortgage offer if required",
            "Your solicitor will review the mortgage conditions",
            "Check the offer expiry date — typically valid for 3–6 months",
        ],
        "typical_weeks_remaining": "6–10 weeks to completion",
    },
    "report_on_title": {
        "number": 7,
        "name": "Report on title sent",
        "description": (
            "Your solicitor has sent their comprehensive report covering title, "
            "searches, survey findings, and mortgage conditions. This is your "
            "key decision point."
        ),
        "typical_week": "Weeks 6–8",
        "next_steps": [
            "Read the report thoroughly — this is important",
            "Ask questions about anything you don't understand",
            "Confirm you're happy to proceed to exchange",
            "Arrange buildings insurance (needed from exchange)",
        ],
        "typical_weeks_remaining": "4–8 weeks to completion",
    },
    "ready_to_exchange": {
        "number": 8,
        "name": "Ready to exchange",
        "description": (
            "All enquiries resolved, searches clear, mortgage offer in place, "
            "contracts signed. Ready for exchange when all parties in the chain "
            "are also ready."
        ),
        "typical_week": "Weeks 8–12",
        "next_steps": [
            "Transfer your deposit to your solicitor's client account",
            "Sign the contract and mortgage deed",
            "Confirm buildings insurance is in place from exchange date",
            "Agree a completion date",
        ],
        "typical_weeks_remaining": "2–4 weeks to completion",
    },
    "exchanged": {
        "number": 9,
        "name": "Contracts exchanged",
        "description": (
            "Contracts have been exchanged — the purchase is now legally binding. "
            "Neither party can pull out without financial penalty. "
            "The completion date is fixed."
        ),
        "typical_week": "Weeks 10–14",
        "next_steps": [
            "Buildings insurance must now be active",
            "Transfer remaining balance to your solicitor before completion",
            "Book removal company for completion day",
            "Arrange utility transfers and redirected post",
            "Read meters at your current property",
        ],
        "typical_weeks_remaining": "1–4 weeks to completion",
    },
    "completion": {
        "number": 10,
        "name": "Completion",
        "description": (
            "Completion day! Your solicitor sends the purchase money to the "
            "seller's solicitor. Once received, the keys are released. "
            "The property is now yours."
        ),
        "typical_week": "Weeks 12–16",
        "next_steps": [
            "Collect keys from the estate agent",
            "Read meters at the new property",
            "Register for council tax at the new address",
            "Update your address with bank, DVLA, HMRC, GP",
        ],
        "typical_weeks_remaining": "Done! Post-completion registration takes 4–6 weeks.",
    },
    "post_completion": {
        "number": 11,
        "name": "Post-completion",
        "description": (
            "Your solicitor is handling post-completion formalities: filing the "
            "SDLT return, paying stamp duty, and registering you as the new owner "
            "at HM Land Registry."
        ),
        "typical_week": "Weeks 12–20",
        "next_steps": [
            "No action needed — your solicitor handles everything",
            "SDLT must be filed within 14 days of completion",
            "Land Registry registration takes 4–6 weeks",
            "Keep all documents for your records",
        ],
        "typical_weeks_remaining": "Registration completes in 4–6 weeks.",
    },
}


@mcp.tool(
    title="Transaction Stage Tracker",
    **_tool_kwargs,
)
def track_transaction_status(
    current_stage: Annotated[
        Literal[
            "instruction",
            "searches_ordered",
            "searches_received",
            "enquiries_raised",
            "survey_complete",
            "mortgage_offer",
            "report_on_title",
            "ready_to_exchange",
            "exchanged",
            "completion",
            "post_completion",
        ],
        Field(
            description=(
                "The current stage of the conveyancing transaction. "
                "Pick the stage that best matches the most recent update."
            ),
        ),
    ],
    weeks_since_offer: Annotated[
        int,
        Field(
            description="Number of weeks since the offer was accepted. Helps assess if on track.",
        ),
    ] = 0,
    chain_length: Annotated[
        int,
        Field(
            description="Number of properties in the chain (1 = no chain, just your purchase).",
        ),
    ] = 1,
) -> dict:
    """Map a conveyancing update to the transaction timeline with next steps.

    Use this when a buyer wants to know where they are in the process, what
    comes next, and whether they're on track. Takes the current stage and
    returns detailed information about that stage plus upcoming milestones.
    """
    stage = STAGES.get(current_stage)
    if not stage:
        return {"error": f"Unknown stage: {current_stage}"}

    # Assess pace
    pace_note = None
    if weeks_since_offer > 0:
        expected_week_map = {
            "instruction": 1,
            "searches_ordered": 2,
            "searches_received": 5,
            "enquiries_raised": 4,
            "survey_complete": 4,
            "mortgage_offer": 5,
            "report_on_title": 7,
            "ready_to_exchange": 10,
            "exchanged": 12,
            "completion": 14,
            "post_completion": 16,
        }
        expected = expected_week_map.get(current_stage, 8)
        if weeks_since_offer <= expected:
            pace_note = "On track — progressing at a normal pace."
        elif weeks_since_offer <= expected + 3:
            pace_note = (
                "Slightly behind typical timeline, but not unusual. "
                "Chase your solicitor if you haven't heard from them in a week."
            )
        else:
            pace_note = (
                f"Behind typical timeline (week {weeks_since_offer}, usually "
                f"at this stage by week {expected}). Contact your solicitor "
                "to understand what's causing the delay."
            )

    # Chain impact
    chain_note = None
    if chain_length > 1:
        chain_note = (
            f"You're in a chain of {chain_length} properties. Exchange requires "
            "all parties to be ready simultaneously, which typically adds "
            f"2–4 weeks. Communication delays multiply across the chain."
        )

    # Remaining stages
    all_stage_keys = list(STAGES.keys())
    current_idx = all_stage_keys.index(current_stage)
    remaining = [
        {"stage": STAGES[k]["name"], "typical_week": STAGES[k]["typical_week"]}
        for k in all_stage_keys[current_idx + 1:]
    ]

    return {
        "current_stage": stage["name"],
        "stage_number": stage["number"],
        "total_stages": len(STAGES),
        "description": stage["description"],
        "next_steps": stage["next_steps"],
        "typical_weeks_remaining": stage["typical_weeks_remaining"],
        "pace_assessment": pace_note,
        "chain_note": chain_note,
        "remaining_stages": remaining,
    }
