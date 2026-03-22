"""Explain a conveyancing search result in plain English."""

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

# Domain knowledge: common search findings and their significance
SEARCH_FINDINGS = {
    "local_authority": {
        "planning_permission": {
            "severity": "LOW",
            "explanation": (
                "Planning permissions granted on or near the property. This is "
                "usually informational — it shows approved works. Check whether "
                "the works were completed and signed off with building control."
            ),
            "action": "Ask seller for completion certificates for any building work.",
        },
        "building_control": {
            "severity": "MEDIUM",
            "explanation": (
                "Building control records show whether works had proper approval "
                "and were inspected. Missing completion certificates mean the council "
                "never confirmed the work meets Building Regulations."
            ),
            "action": (
                "If completion certificates are missing, consider indemnity insurance "
                "or request the seller obtains retrospective sign-off."
            ),
        },
        "conservation_area": {
            "severity": "LOW",
            "explanation": (
                "The property is in a conservation area. This limits what external "
                "changes you can make (e.g., replacement windows, satellite dishes, "
                "demolition) without planning permission. Permitted development rights "
                "are restricted."
            ),
            "action": "Check specific restrictions. Factor this in if you plan exterior changes.",
        },
        "listed_building": {
            "severity": "MEDIUM",
            "explanation": (
                "The property is a listed building (Grade I, II*, or II). Any "
                "alterations — internal or external — that affect the building's "
                "character require Listed Building Consent. Unauthorised works are a "
                "criminal offence. Insurance and maintenance costs may be higher."
            ),
            "action": (
                "Check for any unauthorised alterations. Ensure your insurance covers "
                "listed building requirements. Budget more for maintenance."
            ),
        },
        "tree_preservation_order": {
            "severity": "LOW",
            "explanation": (
                "One or more trees on or near the property are protected by a Tree "
                "Preservation Order. You cannot cut down, top, lop, or uproot protected "
                "trees without the council's consent."
            ),
            "action": "Be aware of the restriction. Factor in if you plan garden or extension work.",
        },
        "road_not_adopted": {
            "severity": "MEDIUM",
            "explanation": (
                "The road serving the property is not adopted (not maintained at "
                "public expense). This means residents may be liable for road "
                "maintenance and repair costs. This can be expensive, especially if "
                "the road surface deteriorates."
            ),
            "action": (
                "Check if there's a road maintenance agreement. Consider the potential cost. "
                "This may affect mortgage lenders' willingness to lend."
            ),
        },
        "smoke_control_zone": {
            "severity": "LOW",
            "explanation": (
                "The property is in a smoke control area. You can only burn "
                "authorised fuels or use exempt appliances (e.g., DEFRA-approved "
                "wood burners). Standard open fires burning coal are not permitted."
            ),
            "action": "Informational only. Check if any existing wood burner is DEFRA-approved.",
        },
        "contaminated_land": {
            "severity": "HIGH",
            "explanation": (
                "The property is on or near land identified as contaminated. "
                "This can affect health, restrict development, and require expensive "
                "remediation. The local authority may serve a remediation notice "
                "requiring the owner to clean up the contamination."
            ),
            "action": (
                "Get a detailed contamination report. This may affect mortgage "
                "availability and insurance. Consider carefully before proceeding."
            ),
        },
        "compulsory_purchase": {
            "severity": "HIGH",
            "explanation": (
                "There is a compulsory purchase order affecting the property or "
                "nearby land. This means a public body has the power to acquire "
                "the land, potentially including your property, for infrastructure "
                "or development projects."
            ),
            "action": (
                "Investigate the scope and timeline of the order. This is a serious "
                "concern — seek specific legal advice before proceeding."
            ),
        },
    },
    "environmental": {
        "flood_zone_2": {
            "severity": "MEDIUM",
            "explanation": (
                "The property is in Flood Zone 2 (medium risk: 0.1%–1% annual "
                "chance of river flooding, or 0.1%–0.5% for sea flooding). "
                "Insurance should be available but may cost more."
            ),
            "action": (
                "Check insurance availability and cost before exchange. "
                "Check if the property benefits from flood defences."
            ),
        },
        "flood_zone_3": {
            "severity": "HIGH",
            "explanation": (
                "The property is in Flood Zone 3 (high risk: >1% annual chance of "
                "river flooding, or >0.5% for sea flooding). Some insurers won't "
                "cover this, and some lenders won't lend. The Flood Re scheme may "
                "help with insurance availability."
            ),
            "action": (
                "Check Flood Re eligibility. Get insurance quotes before committing. "
                "Check flood history. Consider carefully — this significantly affects value."
            ),
        },
        "contamination_risk": {
            "severity": "MEDIUM",
            "explanation": (
                "Historical land use suggests potential contamination risk (e.g., "
                "former industrial site, petrol station, landfill nearby). This is "
                "a risk flag, not a confirmed finding."
            ),
            "action": "Consider a Phase 1 or Phase 2 contamination report for confirmation.",
        },
        "subsidence_risk": {
            "severity": "MEDIUM",
            "explanation": (
                "The area has elevated subsidence risk, often due to clay soil, "
                "mining history, or geological factors. This doesn't mean the "
                "property is affected, but the risk is higher than average."
            ),
            "action": (
                "Check the survey for signs of movement. Consider a structural "
                "engineer's report if the surveyor flags concerns."
            ),
        },
        "radon_affected_area": {
            "severity": "LOW",
            "explanation": (
                "The property is in an area where radon gas levels may be elevated. "
                "Radon is a naturally occurring radioactive gas that can accumulate "
                "in buildings. Long-term exposure increases lung cancer risk."
            ),
            "action": (
                "A radon test costs around £50 and takes 3 months. If levels are high, "
                "remediation (a radon sump) costs £800–£1,500. Not a dealbreaker."
            ),
        },
    },
    "drainage": {
        "public_sewer_under_property": {
            "severity": "MEDIUM",
            "explanation": (
                "A public sewer runs under or very close to the property. Building "
                "over or near a public sewer requires a Build Over Agreement from "
                "the water company. This can restrict extensions and outbuildings."
            ),
            "action": (
                "Check the sewer map for exact location. Factor this in if you "
                "plan any building work. The water company has right of access for "
                "maintenance."
            ),
        },
        "not_connected_to_mains": {
            "severity": "MEDIUM",
            "explanation": (
                "The property is not connected to mains drainage and relies on a "
                "private system (septic tank, cesspit, or treatment plant). These "
                "require regular maintenance, emptying, and comply with Environment "
                "Agency rules."
            ),
            "action": (
                "Check the type and condition of the private drainage system. "
                "Budget for ongoing maintenance (£200–£400/year for emptying). "
                "Ensure it complies with the General Binding Rules."
            ),
        },
    },
    "chancel_repair": {
        "liability_identified": {
            "severity": "MEDIUM",
            "explanation": (
                "The property may be subject to chancel repair liability — an "
                "obligation to contribute to Church of England chancel repairs. "
                "This is an ancient liability that can result in very large costs "
                "(there have been cases exceeding £100,000)."
            ),
            "action": (
                "Take out chancel repair liability indemnity insurance (typically "
                "£20–£50 one-off). This is standard practice and covers the risk."
            ),
        },
    },
}


@mcp.tool(
    title="Search Result Explainer",
    **_tool_kwargs,
)
def explain_search_result(
    search_type: Annotated[
        Literal[
            "local_authority",
            "environmental",
            "drainage",
            "chancel_repair",
        ],
        Field(description="The type of conveyancing search this result came from."),
    ],
    finding: Annotated[
        str,
        Field(
            description=(
                "The specific finding to explain. Use a key like "
                "'planning_permission', 'flood_zone_3', 'contaminated_land', etc. "
                "See the tool's knowledge base for known findings."
            ),
        ),
    ],
    detail: Annotated[
        str,
        Field(description="Any additional context from the search result."),
    ] = "",
) -> dict:
    """Explain a conveyancing search result in plain English with severity rating.

    Use this when a buyer has received search results and wants to understand what
    a specific finding means, how serious it is, and what to do about it.

    Known findings include: planning_permission, building_control, conservation_area,
    listed_building, tree_preservation_order, road_not_adopted, smoke_control_zone,
    contaminated_land, compulsory_purchase, flood_zone_2, flood_zone_3,
    contamination_risk, subsidence_risk, radon_affected_area, public_sewer_under_property,
    not_connected_to_mains, liability_identified.

    For findings not in the knowledge base, returns general guidance for the search type.
    """
    search_data = SEARCH_FINDINGS.get(search_type, {})
    finding_key = finding.lower().replace(" ", "_").replace("-", "_")
    finding_data = search_data.get(finding_key)

    if finding_data:
        result = {
            "search_type": search_type,
            "finding": finding,
            "severity": finding_data["severity"],
            "explanation": finding_data["explanation"],
            "recommended_action": finding_data["action"],
        }
    else:
        result = {
            "search_type": search_type,
            "finding": finding,
            "severity": "UNKNOWN",
            "explanation": (
                f"This finding ('{finding}') is not in the built-in knowledge base "
                f"for {search_type} searches. The detail provided was: "
                f"'{detail}'. Ask your solicitor to explain the significance."
            ),
            "recommended_action": (
                "Ask your solicitor to explain this specific finding and whether "
                "it affects the property or your intended use of it."
            ),
        }

    if detail:
        result["additional_context"] = detail

    return result
