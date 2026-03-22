"""Check leasehold terms for red flags and risks."""

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


@mcp.tool(
    title="Leasehold Terms Checker",
    **_tool_kwargs,
)
def check_lease_terms(
    remaining_years: Annotated[
        int,
        Field(description="Remaining years on the lease. Example: 82"),
    ],
    ground_rent_annual: Annotated[
        int,
        Field(
            description=(
                "Current annual ground rent in GBP. "
                "Use 0 for peppercorn rent."
            ),
        ),
    ] = 0,
    ground_rent_escalation: Annotated[
        Literal["none", "fixed", "rpi", "doubling", "unknown"],
        Field(
            description=(
                "How the ground rent increases over time. "
                "'none' = stays the same, 'fixed' = fixed increments, "
                "'rpi' = linked to RPI/CPI, 'doubling' = doubles periodically, "
                "'unknown' = not specified or unclear."
            ),
        ),
    ] = "none",
    service_charge_annual: Annotated[
        int,
        Field(description="Current annual service charge in GBP. Use 0 if unknown."),
    ] = 0,
    has_sinking_fund: Annotated[
        bool,
        Field(description="Whether the building has a reserve/sinking fund for major works."),
    ] = False,
    lease_type: Annotated[
        Literal["flat", "house", "maisonette"],
        Field(description="Type of leasehold property."),
    ] = "flat",
    share_of_freehold: Annotated[
        bool,
        Field(description="Whether the leaseholder has a share of the freehold."),
    ] = False,
) -> dict:
    """Analyse leasehold terms and flag risks, red flags, and things to negotiate.

    Use this when a buyer is purchasing a leasehold property and wants to understand
    whether the lease terms are acceptable. Returns a risk assessment with severity
    ratings, explanations, and recommended actions.

    Not suitable for commonhold or freehold properties.
    """
    flags: list[dict] = []

    # --- Lease length assessment ---
    if remaining_years < 80:
        flags.append({
            "issue": "Short lease — below 80 years",
            "severity": "HIGH",
            "detail": (
                f"At {remaining_years} years, this lease is critically short. "
                "Most mortgage lenders require at least 70-80 years remaining. "
                "Below 80 years, the 'marriage value' kicks in, making extension "
                "significantly more expensive."
            ),
            "action": (
                "Get a lease extension valuation before committing. "
                "Consider negotiating the extension as a condition of purchase. "
                "Budget £10,000–£30,000+ for the extension depending on property value."
            ),
        })
    elif remaining_years < 90:
        flags.append({
            "issue": "Lease approaching critical threshold",
            "severity": "MEDIUM",
            "detail": (
                f"At {remaining_years} years, the lease is getting short. "
                "While still mortgageable, you should plan to extend within "
                "2 years of purchase (you gain the statutory right after 2 years). "
                "Extending before it drops below 80 saves significant cost."
            ),
            "action": "Budget for a lease extension. Get a valuation now to understand the cost.",
        })
    elif remaining_years < 125:
        flags.append({
            "issue": "Lease length adequate but not ideal",
            "severity": "LOW",
            "detail": (
                f"At {remaining_years} years, the lease is fine for mortgage purposes "
                "and won't need immediate attention. The Leasehold and Freehold Reform "
                "Act 2024 will allow 990-year extensions at lower cost when fully in force."
            ),
            "action": "No immediate action needed. Consider extending when the new legislation is in force.",
        })

    # --- Ground rent assessment ---
    if ground_rent_annual > 0:
        if ground_rent_escalation == "doubling":
            flags.append({
                "issue": "Doubling ground rent clause",
                "severity": "HIGH",
                "detail": (
                    f"Ground rent of £{ground_rent_annual:,}/year with a doubling clause "
                    "is a serious red flag. This was the pattern that led to the leasehold "
                    "scandal. Some lenders (including Nationwide and Santander) refuse to lend "
                    "on properties with doubling ground rent clauses."
                ),
                "action": (
                    "Check if the freeholder will agree to vary the clause to RPI-linked or fixed. "
                    "If not, consider whether you can get a mortgage — check with your lender first. "
                    "This may significantly affect resale value."
                ),
            })
        elif ground_rent_escalation == "rpi":
            flags.append({
                "issue": "RPI-linked ground rent",
                "severity": "MEDIUM",
                "detail": (
                    f"Ground rent of £{ground_rent_annual:,}/year linked to RPI will increase "
                    "with inflation. At 3% average inflation, it roughly doubles every 24 years. "
                    "Less concerning than a doubling clause but still an ongoing cost."
                ),
                "action": "Factor increasing ground rent into long-term costs. Most lenders accept RPI-linked.",
            })

        if ground_rent_annual >= 250:
            flags.append({
                "issue": "Ground rent at or above £250/year",
                "severity": "MEDIUM",
                "detail": (
                    f"Ground rent of £{ground_rent_annual:,}/year is above the £250 threshold. "
                    "If ground rent reaches £250+ (or £1,000+ in London), the lease could "
                    "technically be treated as an Assured Shorthold Tenancy under the Housing "
                    "Act 1988, giving the freeholder potential forfeiture rights."
                ),
                "action": (
                    "Ask your solicitor to advise on AST risk. "
                    "The Leasehold Reform (Ground Rent) Act 2022 caps new leases at peppercorn "
                    "but doesn't apply to existing leases."
                ),
            })

        if ground_rent_escalation == "unknown":
            flags.append({
                "issue": "Ground rent escalation unclear",
                "severity": "MEDIUM",
                "detail": (
                    "The ground rent review mechanism is not clear. Your solicitor must "
                    "identify exactly how and when ground rent increases before you commit."
                ),
                "action": "Ask your solicitor to clarify the ground rent review clause in the lease.",
            })

    # --- Service charge assessment ---
    if service_charge_annual > 0 and not has_sinking_fund:
        flags.append({
            "issue": "No reserve/sinking fund",
            "severity": "MEDIUM",
            "detail": (
                "The building has no reserve fund for major works. This means when "
                "significant repairs are needed (roof, windows, external decoration), "
                "leaseholders will face a large one-off bill, potentially £5,000–£20,000+."
            ),
            "action": (
                "Ask to see any planned major works. Ask the management company about "
                "the building's condition and when major works are expected."
            ),
        })

    if service_charge_annual > 5_000:
        flags.append({
            "issue": "High annual service charge",
            "severity": "LOW",
            "detail": (
                f"Service charge of £{service_charge_annual:,}/year is above average. "
                "Check what's included — concierge, gym, swimming pool, and 24-hour "
                "security will push this up. Make sure it's justified by the services provided."
            ),
            "action": "Request the last 3 years' service charge accounts and any budget forecasts.",
        })

    # --- Leasehold house warning ---
    if lease_type == "house":
        flags.append({
            "issue": "Leasehold house",
            "severity": "MEDIUM",
            "detail": (
                "Leasehold houses are increasingly rare and controversial. "
                "The Leasehold and Freehold Reform Act 2024 includes provisions to "
                "ban new leasehold houses (with limited exceptions). Existing leasehold "
                "houses have the right to enfranchise (buy the freehold)."
            ),
            "action": (
                "Consider buying the freehold — you have a statutory right. "
                "Get a valuation for enfranchisement. This removes ground rent "
                "and gives you full control."
            ),
        })

    # --- Share of freehold positive ---
    share_note = None
    if share_of_freehold:
        share_note = (
            "Share of freehold is a positive — you have collective control over "
            "the building, can grant yourself a lease extension at minimal cost, "
            "and are not subject to an external freeholder's decisions."
        )

    # --- Overall assessment ---
    high_count = sum(1 for f in flags if f["severity"] == "HIGH")
    med_count = sum(1 for f in flags if f["severity"] == "MEDIUM")

    if high_count > 0:
        overall = "CONCERNING — address high-severity issues before proceeding"
    elif med_count >= 2:
        overall = "CAUTION — several medium-severity issues to investigate"
    elif med_count == 1:
        overall = "MOSTLY OK — one issue to clarify with your solicitor"
    else:
        overall = "LOW RISK — no major concerns identified"

    return {
        "overall_assessment": overall,
        "remaining_years": remaining_years,
        "flags": flags,
        "flag_count": {"high": high_count, "medium": med_count, "low": len(flags) - high_count - med_count},
        "share_of_freehold_note": share_note,
    }
