"""Analyse structured title register data for red flags."""

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

# Domain knowledge for common title entries
RESTRICTION_KNOWLEDGE = {
    "mortgage_restriction": {
        "severity": "LOW",
        "explanation": (
            "Standard restriction placed by the mortgage lender. This will be "
            "removed when the seller pays off their mortgage on completion. "
            "Your solicitor handles this routinely."
        ),
        "action": "No action needed — your solicitor will ensure this is removed on completion.",
    },
    "joint_proprietor_restriction": {
        "severity": "LOW",
        "explanation": (
            "A Form A restriction requiring that any sale proceeds are paid to "
            "at least two trustees. Standard for jointly owned properties. "
            "Ensures one owner can't sell without the other's knowledge."
        ),
        "action": "Standard restriction — no concern. Removed when title transfers.",
    },
    "lease_restriction": {
        "severity": "LOW",
        "explanation": (
            "Restriction noting that the property is subject to a lease. "
            "Normal for leasehold properties. The lease terms are what matter."
        ),
        "action": "Review the lease terms separately (use the check_lease_terms tool).",
    },
    "bankruptcy_restriction": {
        "severity": "HIGH",
        "explanation": (
            "A restriction related to bankruptcy proceedings. This may mean "
            "the property cannot be sold or transferred without the trustee "
            "in bankruptcy's consent."
        ),
        "action": (
            "Your solicitor must investigate immediately. The sale may not "
            "be able to proceed until this is resolved."
        ),
    },
    "charging_order": {
        "severity": "HIGH",
        "explanation": (
            "A charging order has been placed against the property, usually "
            "by a creditor who obtained a court judgment. This is a claim "
            "against the property's equity."
        ),
        "action": (
            "This must be paid off from the sale proceeds on completion. "
            "Your solicitor will ensure this is handled."
        ),
    },
    "caution": {
        "severity": "MEDIUM",
        "explanation": (
            "A caution has been registered against the title. This is a "
            "warning that someone claims an interest in the property. "
            "It must be investigated before purchase."
        ),
        "action": "Your solicitor must investigate the basis of the caution and seek its removal.",
    },
    "unilateral_notice": {
        "severity": "MEDIUM",
        "explanation": (
            "A unilateral notice has been registered, claiming an interest "
            "in the property (e.g., a beneficial interest, option to purchase, "
            "or right of pre-emption). The claimed interest may or may not be valid."
        ),
        "action": "Your solicitor must investigate and ensure removal before completion.",
    },
}

CHARGE_KNOWLEDGE = {
    "mortgage": {
        "severity": "LOW",
        "explanation": "Standard mortgage charge. Will be paid off from sale proceeds on completion.",
        "action": "No action needed — your solicitor handles mortgage redemption.",
    },
    "second_charge": {
        "severity": "MEDIUM",
        "explanation": (
            "A second charge (e.g., secured loan, second mortgage) exists. "
            "This will also need to be paid off from sale proceeds."
        ),
        "action": (
            "Your solicitor will check that the total charges don't exceed "
            "the sale price (negative equity risk)."
        ),
    },
    "legal_aid_charge": {
        "severity": "MEDIUM",
        "explanation": (
            "A Legal Aid charge exists against the property. The Legal Aid Agency "
            "may be entitled to repayment from the sale proceeds."
        ),
        "action": "Your solicitor will contact the Legal Aid Agency to confirm the amount owed.",
    },
}


@mcp.tool(
    title="Title Register Analyser",
    **_tool_kwargs,
)
def parse_title_register(
    tenure: Annotated[
        Literal["freehold", "leasehold"],
        Field(description="Whether the title is freehold or leasehold."),
    ],
    proprietor_count: Annotated[
        int,
        Field(description="Number of registered proprietors (owners). Usually 1 or 2."),
    ] = 1,
    has_charges: Annotated[
        bool,
        Field(description="Whether the charges register (Section C) contains any entries."),
    ] = False,
    charge_types: Annotated[
        str,
        Field(
            description=(
                "Comma-separated list of charge types found. "
                "Known types: mortgage, second_charge, legal_aid_charge. "
                "Example: 'mortgage' or 'mortgage,second_charge'"
            ),
        ),
    ] = "",
    restrictions: Annotated[
        str,
        Field(
            description=(
                "Comma-separated list of restriction types found. "
                "Known types: mortgage_restriction, joint_proprietor_restriction, "
                "lease_restriction, bankruptcy_restriction, charging_order, "
                "caution, unilateral_notice. "
                "Example: 'mortgage_restriction,joint_proprietor_restriction'"
            ),
        ),
    ] = "",
    has_easements: Annotated[
        bool,
        Field(
            description="Whether the property register mentions easements (rights of way, drainage rights, etc.).",
        ),
    ] = False,
    has_restrictive_covenants: Annotated[
        bool,
        Field(
            description="Whether the property is subject to restrictive covenants.",
        ),
    ] = False,
    title_class: Annotated[
        Literal["absolute", "qualified", "possessory", "good_leasehold"],
        Field(
            description=(
                "The class of title. 'absolute' is best and most common. "
                "'possessory' or 'qualified' titles have caveats."
            ),
        ),
    ] = "absolute",
) -> dict:
    """Analyse a title register and flag potential issues.

    Use this when a buyer wants to understand what's on the title register
    for a property they're purchasing. Takes structured data about the title
    entries and returns a risk assessment with explanations.

    The title register has three sections: A (Property Register — what you're
    buying), B (Proprietorship Register — who owns it), C (Charges Register —
    mortgages and other financial claims).
    """
    flags: list[dict] = []

    # --- Title class assessment ---
    if title_class == "possessory":
        flags.append({
            "section": "B — Proprietorship",
            "issue": "Possessory title",
            "severity": "HIGH",
            "detail": (
                "Possessory title means the Land Registry hasn't verified "
                "the owner's right to the land (e.g., deeds were lost). "
                "Someone could come forward claiming to be the true owner. "
                "Some lenders won't lend on possessory titles."
            ),
            "action": (
                "Check if the title can be upgraded to absolute (possible after "
                "12 years of undisturbed possession). Your solicitor should "
                "advise on indemnity insurance."
            ),
        })
    elif title_class == "qualified":
        flags.append({
            "section": "B — Proprietorship",
            "issue": "Qualified title",
            "severity": "MEDIUM",
            "detail": (
                "Qualified title means the Land Registry has a specific "
                "reservation about the title (noted in the register). "
                "This is rare and should be investigated."
            ),
            "action": "Your solicitor must review the qualification and advise on its impact.",
        })
    elif title_class == "good_leasehold":
        flags.append({
            "section": "B — Proprietorship",
            "issue": "Good leasehold title (not absolute)",
            "severity": "LOW",
            "detail": (
                "Good leasehold means the leasehold title is registered but "
                "the freeholder's title hasn't been verified. This is common "
                "for older leasehold properties and usually not a problem in "
                "practice."
            ),
            "action": (
                "Most lenders accept good leasehold title. Your solicitor may "
                "recommend indemnity insurance as a precaution."
            ),
        })

    # --- Charges assessment ---
    if has_charges and charge_types:
        for charge_type in charge_types.split(","):
            charge_type = charge_type.strip().lower()
            charge_info = CHARGE_KNOWLEDGE.get(charge_type)
            if charge_info:
                flags.append({
                    "section": "C — Charges",
                    "issue": charge_type.replace("_", " ").title(),
                    "severity": charge_info["severity"],
                    "detail": charge_info["explanation"],
                    "action": charge_info["action"],
                })
            elif charge_type:
                flags.append({
                    "section": "C — Charges",
                    "issue": f"Unknown charge: {charge_type}",
                    "severity": "MEDIUM",
                    "detail": (
                        f"A charge of type '{charge_type}' was found. "
                        "Your solicitor should investigate this."
                    ),
                    "action": "Ask your solicitor to explain this charge and its implications.",
                })

    # --- Restrictions assessment ---
    if restrictions:
        for restriction in restrictions.split(","):
            restriction = restriction.strip().lower()
            restriction_info = RESTRICTION_KNOWLEDGE.get(restriction)
            if restriction_info:
                flags.append({
                    "section": "B — Proprietorship",
                    "issue": restriction.replace("_", " ").title(),
                    "severity": restriction_info["severity"],
                    "detail": restriction_info["explanation"],
                    "action": restriction_info["action"],
                })
            elif restriction:
                flags.append({
                    "section": "B — Proprietorship",
                    "issue": f"Unknown restriction: {restriction}",
                    "severity": "MEDIUM",
                    "detail": (
                        f"A restriction of type '{restriction}' was found. "
                        "Your solicitor should investigate this."
                    ),
                    "action": "Ask your solicitor to explain this restriction.",
                })

    # --- Easements and covenants ---
    if has_easements:
        flags.append({
            "section": "A — Property",
            "issue": "Easements noted",
            "severity": "LOW",
            "detail": (
                "The property benefits from or is subject to easements "
                "(e.g., rights of way, drainage rights, access rights). "
                "Easements benefiting the property are positive. Easements "
                "burdening the property (others' rights over your land) "
                "need checking."
            ),
            "action": (
                "Ask your solicitor whether the easements benefit or burden "
                "the property, and whether they affect your intended use."
            ),
        })

    if has_restrictive_covenants:
        flags.append({
            "section": "A — Property",
            "issue": "Restrictive covenants",
            "severity": "LOW",
            "detail": (
                "The property is subject to restrictive covenants — rules about "
                "what you can and can't do with the property (e.g., no commercial "
                "use, no further building, maintain fences). Many are historic "
                "and rarely enforced, but technically still binding."
            ),
            "action": (
                "Review the specific covenants with your solicitor. Check if any "
                "would prevent your planned use. Indemnity insurance is available "
                "for breaches of historic covenants."
            ),
        })

    # --- Overall assessment ---
    high_count = sum(1 for f in flags if f["severity"] == "HIGH")
    med_count = sum(1 for f in flags if f["severity"] == "MEDIUM")

    if high_count > 0:
        overall = "INVESTIGATE — high-severity issues require solicitor attention"
    elif med_count >= 2:
        overall = "REVIEW — several items for your solicitor to check"
    elif len(flags) == 0:
        overall = "CLEAN — no issues identified (standard entries only)"
    else:
        overall = "STANDARD — minor items, nothing unusual"

    return {
        "overall_assessment": overall,
        "title_class": title_class,
        "tenure": tenure,
        "proprietor_count": proprietor_count,
        "flags": flags,
        "flag_count": {
            "high": high_count,
            "medium": med_count,
            "low": len(flags) - high_count - med_count,
        },
    }
