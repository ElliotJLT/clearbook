"""Settle MCP Server — UK regulated professional services discovery."""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from settle.models import ProviderType, SearchFilters
from settle.service import SettleService

mcp = FastMCP(
    "Settle",
    instructions=(
        "Discover and evaluate UK regulated professional service providers. "
        "Search conveyancers, mortgage brokers, and financial advisers with "
        "regulatory status, disciplinary history, and company health data."
    ),
)

_service: SettleService | None = None


def get_service() -> SettleService:
    global _service
    if _service is None:
        _service = SettleService(
            sra_api_key=os.getenv("SRA_API_KEY", ""),
            fca_email=os.getenv("FCA_AUTH_EMAIL", ""),
            fca_key=os.getenv("FCA_AUTH_KEY", ""),
            companies_house_key=os.getenv("COMPANIES_HOUSE_API_KEY", ""),
        )
    return _service


@mcp.tool()
async def search_conveyancers(
    postcode: str,
    radius_miles: int = 10,
    authorised_only: bool = True,
    max_results: int = 10,
) -> dict[str, Any]:
    """Search for conveyancing firms near a UK postcode.

    Returns SRA-regulated conveyancers with regulatory status,
    disciplinary history, and company health data. Results are
    factual — no evaluative rankings or recommendations.

    Args:
        postcode: UK postcode to search near (e.g. "SE15 4QN")
        radius_miles: Search radius in miles (default 10)
        authorised_only: Only return currently authorised firms (default True)
        max_results: Maximum number of results (default 10, max 50)
    """
    service = get_service()
    filters = SearchFilters(
        provider_type=ProviderType.CONVEYANCER,
        postcode=postcode,
        radius_miles=radius_miles,
        authorised_only=authorised_only,
        max_results=min(max_results, 50),
    )
    result = await service.search(filters)
    return result.model_dump()


@mcp.tool()
async def search_mortgage_brokers(
    postcode: str,
    radius_miles: int = 10,
    authorised_only: bool = True,
    max_results: int = 10,
) -> dict[str, Any]:
    """Search for FCA-authorised mortgage brokers near a UK postcode.

    Returns mortgage brokers/advisers with FCA permissions,
    disciplinary history, and company health data. Results are
    factual — no evaluative rankings or recommendations.

    Args:
        postcode: UK postcode to search near (e.g. "SE15 4QN")
        radius_miles: Search radius in miles (default 10)
        authorised_only: Only return currently authorised firms (default True)
        max_results: Maximum number of results (default 10, max 50)
    """
    service = get_service()
    filters = SearchFilters(
        provider_type=ProviderType.MORTGAGE_BROKER,
        postcode=postcode,
        radius_miles=radius_miles,
        authorised_only=authorised_only,
        max_results=min(max_results, 50),
    )
    result = await service.search(filters)
    return result.model_dump()


@mcp.tool()
async def get_provider_profile(
    regulator: str,
    reference_number: str,
) -> dict[str, Any]:
    """Get a full enriched profile for a specific provider.

    Cross-references regulatory data (SRA/FCA) with Companies House
    for a complete picture: regulatory status, disciplinary history,
    company health, insolvency data, and officer information.

    Args:
        regulator: "SRA" or "FCA"
        reference_number: The SRA number or FCA FRN
    """
    service = get_service()
    provider = await service.get_provider(regulator, reference_number)
    if provider is None:
        return {"error": f"Provider not found: {regulator} {reference_number}"}
    return provider.model_dump()


@mcp.tool()
async def get_disciplinary_history(
    regulator: str,
    reference_number: str,
) -> dict[str, Any]:
    """Check disciplinary/enforcement history for a provider.

    Returns any regulatory actions taken by the SRA or FCA against
    this firm. Essential for due diligence.

    Args:
        regulator: "SRA" or "FCA"
        reference_number: The SRA number or FCA FRN
    """
    service = get_service()
    actions = await service.get_disciplinary_history(regulator, reference_number)
    return {
        "regulator": regulator,
        "reference_number": reference_number,
        "actions": [a.model_dump() for a in actions],
        "has_history": len(actions) > 0,
    }


@mcp.tool()
async def compare_providers(
    regulator: str,
    reference_numbers: list[str],
) -> dict[str, Any]:
    """Compare multiple providers side-by-side on factual criteria.

    Returns regulatory status, disciplinary history, company health,
    and trust signals for each provider. No evaluative judgment —
    the comparison presents facts for the user to decide.

    Args:
        regulator: "SRA" or "FCA" (all providers must be same regulator)
        reference_numbers: List of SRA numbers or FCA FRNs to compare (max 5)
    """
    service = get_service()
    if len(reference_numbers) > 5:
        return {"error": "Maximum 5 providers per comparison"}

    providers = []
    for ref in reference_numbers:
        provider = await service.get_provider(regulator, ref)
        if provider:
            providers.append({
                "name": provider.name,
                "reference_number": ref,
                "trust_signals": provider.trust_signals,
                "regulatory_status": (
                    provider.regulatory_profiles[0].status.value
                    if provider.regulatory_profiles
                    else "unknown"
                ),
                "company_health": (
                    provider.company_health.model_dump()
                    if provider.company_health
                    else None
                ),
            })

    return {
        "regulator": regulator,
        "providers": providers,
        "note": "Factual comparison only. No evaluative ranking.",
    }


# MCP Resources — static reference data

@mcp.resource("settle://about")
def about() -> str:
    """What Settle is and how to use it."""
    return """# Settle — UK Professional Services Discovery

Settle helps AI agents find and evaluate UK regulated professional
service providers using data from official regulatory registers.

## Available Tools
- search_conveyancers — Find SRA-regulated conveyancing firms by postcode
- search_mortgage_brokers — Find FCA-authorised mortgage brokers by postcode
- get_provider_profile — Full enriched profile for a specific provider
- get_disciplinary_history — Check regulatory enforcement actions
- compare_providers — Side-by-side factual comparison

## Data Sources
- SRA (Solicitors Regulation Authority) register
- FCA (Financial Conduct Authority) register
- Companies House (company health, officers, insolvency)

## Important
Settle provides factual data only. It does not make recommendations
or evaluate suitability. The user makes the final decision.
"""


@mcp.resource("settle://regulators")
def regulators() -> str:
    """UK regulatory bodies covered by Settle."""
    return """# UK Regulators

## SRA — Solicitors Regulation Authority
- Regulates solicitors and law firms in England and Wales
- Covers conveyancing, litigation, corporate law, etc.
- Register: solicitors.lawsociety.org.uk

## FCA — Financial Conduct Authority
- Regulates financial services firms and individuals
- Covers mortgage brokers, financial advisers, insurance brokers
- Register: register.fca.org.uk

## CLC — Council for Licensed Conveyancers
- Regulates licensed conveyancers (specialist property lawyers)
- ~250 practices in England and Wales
- Register: clc-uk.org (no API — data scraped)
"""
