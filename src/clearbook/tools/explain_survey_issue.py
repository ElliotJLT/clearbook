"""Explain a property survey issue in plain English."""

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

# Surveyor condition ratings (RICS Home Survey Standard)
CONDITION_RATINGS = {
    1: {
        "label": "No repair needed",
        "meaning": "No immediate concerns. Normal maintenance only.",
    },
    2: {
        "label": "Defects that need repairing or replacing",
        "meaning": (
            "Defects present but not urgent. May need attention in the "
            "near future to prevent deterioration."
        ),
    },
    3: {
        "label": "Serious defects — urgent repairs needed",
        "meaning": (
            "Significant defects that need urgent attention. May be affecting "
            "other parts of the building or pose a safety risk. Get specialist "
            "advice before exchanging contracts."
        ),
    },
}

# Domain knowledge for common survey defects
DEFECT_KNOWLEDGE = {
    "subsidence": {
        "plain_english": (
            "The building's foundations are sinking unevenly, causing the structure "
            "to move. This is different from 'settlement' (which is normal, gradual, "
            "and usually stops)."
        ),
        "typical_signs": [
            "Diagonal cracks wider than 5mm, especially around windows and doors",
            "Cracks wider at the top than the bottom",
            "Doors and windows sticking or not closing properly",
            "Sloping floors",
        ],
        "typical_cost": "£5,000–£50,000+",
        "urgency": "HIGH",
        "specialist_needed": "Structural engineer",
        "impact_on_insurance": (
            "May trigger excess of £1,000+ on subsidence claims. "
            "Previous subsidence claims must be disclosed to insurers."
        ),
    },
    "rising_damp": {
        "plain_english": (
            "Moisture is being drawn up from the ground into the walls through "
            "capillary action, usually because the damp-proof course (DPC) has "
            "failed or been bridged."
        ),
        "typical_signs": [
            "Tide mark on walls up to about 1 metre high",
            "Peeling wallpaper or paint near the base of walls",
            "Salt deposits (white crystals) on walls",
            "Musty smell at ground floor level",
        ],
        "typical_cost": "£2,000–£8,000",
        "urgency": "MEDIUM",
        "specialist_needed": "Damp specialist (PCA-registered)",
        "impact_on_insurance": "No direct impact, but untreated damp leads to timber decay.",
    },
    "penetrating_damp": {
        "plain_english": (
            "Water is getting through the walls or roof from outside, usually "
            "through defective pointing, cracked render, leaking gutters, or "
            "damaged roof coverings."
        ),
        "typical_signs": [
            "Damp patches on walls, especially after rain",
            "Staining or discolouration on internal walls or ceilings",
            "Blown plaster",
            "Mould growth on walls",
        ],
        "typical_cost": "£500–£5,000",
        "urgency": "MEDIUM",
        "specialist_needed": "Roofer or builder depending on source",
        "impact_on_insurance": "Gradual deterioration usually excluded from buildings insurance.",
    },
    "dry_rot": {
        "plain_english": (
            "A serious fungal infection (Serpula lacrymans) that destroys timber. "
            "Unlike wet rot, dry rot can spread through masonry and affect areas "
            "far from the original moisture source. It needs urgent treatment."
        ),
        "typical_signs": [
            "Crumbling, brittle timber that breaks into cubes",
            "White or grey cotton-wool-like mycelium",
            "Mushroom-like fruiting bodies (rusty red colour)",
            "Musty, damp smell",
        ],
        "typical_cost": "£5,000–£30,000+",
        "urgency": "HIGH",
        "specialist_needed": "Timber and damp specialist (PCA-registered)",
        "impact_on_insurance": "May be covered under buildings insurance if caused by an insured event.",
    },
    "wet_rot": {
        "plain_english": (
            "Fungal decay of timber caused by prolonged exposure to moisture. "
            "Less serious than dry rot because it doesn't spread through masonry — "
            "it stays localised to the wet area."
        ),
        "typical_signs": [
            "Soft, spongy timber",
            "Timber that darkens and cracks along the grain",
            "Paint flaking off window frames or door frames",
            "Localised dampness near the affected timber",
        ],
        "typical_cost": "£500–£5,000",
        "urgency": "MEDIUM",
        "specialist_needed": "Builder or timber specialist",
        "impact_on_insurance": "Usually not covered — treated as maintenance.",
    },
    "woodworm": {
        "plain_english": (
            "Small holes in timber caused by wood-boring beetle larvae. Very common "
            "in older properties. Often historic (inactive) — the beetles have left. "
            "Active infestation shows fresh bore dust (frass) around the holes."
        ),
        "typical_signs": [
            "Small round holes (1-2mm) in timber",
            "Fine powdery dust (frass) near holes — indicates active infestation",
            "Weakened or crumbly timber in severe cases",
        ],
        "typical_cost": "£500–£3,000",
        "urgency": "LOW",
        "specialist_needed": "Timber specialist (only if active)",
        "impact_on_insurance": "Not covered — treated as pre-existing condition or maintenance.",
    },
    "asbestos": {
        "plain_english": (
            "Asbestos-containing materials are present. Common in properties built "
            "or renovated before 2000. Asbestos is only dangerous when disturbed — "
            "intact asbestos in good condition can be safely left in place."
        ),
        "typical_signs": [
            "Artex-style textured ceilings (pre-2000)",
            "Corrugated cement roof sheets",
            "Old pipe lagging",
            "Vinyl floor tiles (9x9 inch tiles are a common indicator)",
        ],
        "typical_cost": "£500–£5,000 (removal)",
        "urgency": "LOW",
        "specialist_needed": "Licensed asbestos removal contractor (if disturbing)",
        "impact_on_insurance": "No impact if undisturbed. Removal costs not covered.",
    },
    "japanese_knotweed": {
        "plain_english": (
            "An invasive plant that can grow through concrete, tarmac, and drains. "
            "It's not a structural risk to solid foundations but can exploit existing "
            "cracks. It's an offence to cause it to spread."
        ),
        "typical_signs": [
            "Bamboo-like stems with purple speckles",
            "Shield-shaped leaves",
            "Dead brown canes in winter",
            "Grows extremely fast in spring/summer (up to 10cm/day)",
        ],
        "typical_cost": "£2,000–£15,000 (treatment plan)",
        "urgency": "HIGH",
        "specialist_needed": "PCA-accredited Japanese knotweed specialist",
        "impact_on_insurance": (
            "Most lenders will lend with an insurance-backed treatment plan. "
            "Must be declared on TA6 form."
        ),
    },
    "roof_defects": {
        "plain_english": (
            "Problems with the roof covering, structure, or associated components. "
            "The roof is the building's primary defence against weather — defects "
            "here lead to water ingress, damp, and timber decay if not addressed."
        ),
        "typical_signs": [
            "Missing, slipped, or cracked tiles/slates",
            "Sagging ridge or roof line",
            "Defective flashing around chimneys or abutments",
            "Daylight visible from inside the loft",
        ],
        "typical_cost": "£500–£20,000",
        "urgency": "MEDIUM",
        "specialist_needed": "Roofer",
        "impact_on_insurance": (
            "Storm damage may be covered. Wear and tear is not. "
            "Lenders may require repairs before lending."
        ),
    },
    "electrical": {
        "plain_english": (
            "The electrical installation may be outdated or non-compliant. "
            "A surveyor can only make visual observations — a full EICR "
            "(Electrical Installation Condition Report) is needed for a "
            "definitive assessment."
        ),
        "typical_signs": [
            "Old-style fuse box (rewirable fuses) instead of modern consumer unit",
            "No RCD protection",
            "Surface-mounted wiring",
            "Round-pin sockets or bakelite switches",
        ],
        "typical_cost": "£3,000–£8,000 (full rewire)",
        "urgency": "MEDIUM",
        "specialist_needed": "NICEIC or NAPIT registered electrician",
        "impact_on_insurance": "Faulty wiring may invalidate fire cover if known and not addressed.",
    },
}


@mcp.tool(
    title="Survey Issue Explainer",
    **_tool_kwargs,
)
def explain_survey_issue(
    issue_type: Annotated[
        Literal[
            "subsidence",
            "rising_damp",
            "penetrating_damp",
            "dry_rot",
            "wet_rot",
            "woodworm",
            "asbestos",
            "japanese_knotweed",
            "roof_defects",
            "electrical",
        ],
        Field(
            description="The type of defect found in the survey.",
        ),
    ],
    condition_rating: Annotated[
        Literal[1, 2, 3],
        Field(
            description=(
                "RICS condition rating from the survey: "
                "1 = no repair needed, 2 = repairs needed, 3 = urgent/serious."
            ),
        ),
    ] = 2,
    surveyor_notes: Annotated[
        str,
        Field(description="Any specific notes from the surveyor about this issue."),
    ] = "",
) -> dict:
    """Translate a property survey finding into plain English with severity, cost estimate, and action.

    Use this when a buyer has received a survey report and wants to understand what
    a specific defect means. Covers the most common residential survey issues including
    structural movement, damp, timber defects, asbestos, and Japanese knotweed.

    Uses RICS condition ratings (1-3) as used in Level 2 and Level 3 surveys.
    """
    defect = DEFECT_KNOWLEDGE.get(issue_type)
    if not defect:
        return {"error": f"Unknown issue type: {issue_type}"}

    rating_info = CONDITION_RATINGS.get(condition_rating, CONDITION_RATINGS[2])

    result = {
        "issue_type": issue_type,
        "condition_rating": condition_rating,
        "condition_label": rating_info["label"],
        "condition_meaning": rating_info["meaning"],
        "plain_english": defect["plain_english"],
        "typical_signs": defect["typical_signs"],
        "estimated_cost": defect["typical_cost"],
        "urgency": defect["urgency"],
        "specialist_needed": defect["specialist_needed"],
        "insurance_impact": defect["impact_on_insurance"],
        "recommendation": _build_recommendation(
            issue_type, condition_rating, defect
        ),
    }

    if surveyor_notes:
        result["surveyor_notes"] = surveyor_notes

    return result


def _build_recommendation(
    issue_type: str, condition_rating: int, defect: dict
) -> str:
    """Build a contextual recommendation based on the issue and rating."""
    if condition_rating == 3:
        return (
            f"This is rated Condition 3 (urgent). Get a {defect['specialist_needed']} "
            f"report before exchange. Consider negotiating a price reduction or "
            f"making repair a condition of purchase. Estimated cost: {defect['typical_cost']}."
        )
    elif condition_rating == 2:
        return (
            f"This is rated Condition 2 (needs attention). Get a "
            f"{defect['specialist_needed']} quote so you know the cost. "
            f"Consider negotiating a price reduction. "
            f"Estimated cost: {defect['typical_cost']}."
        )
    else:
        return (
            "Rated Condition 1 — no immediate action needed. "
            "Monitor as part of routine maintenance."
        )
