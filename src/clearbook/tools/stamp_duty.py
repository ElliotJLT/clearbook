"""SDLT (Stamp Duty Land Tax) calculator for England & Northern Ireland."""

from typing import Annotated, Literal

from pydantic import Field

from clearbook.app import mcp

try:
    from mcp.types import ToolAnnotations
except ImportError:
    ToolAnnotations = None  # type: ignore[assignment,misc]

# England & NI SDLT thresholds — current rates from 1 April 2025
# Temporary higher thresholds (Sep 2022 – Mar 2025) have expired and reverted.
# Source: https://www.gov.uk/stamp-duty-land-tax/residential-property-rates
STANDARD_BANDS = [
    (125_000, 0.00),   # 0% up to £125,000
    (250_000, 0.02),   # 2% on £125,001–£250,000
    (925_000, 0.05),   # 5% on £250,001–£925,000
    (1_500_000, 0.10), # 10% on £925,001–£1,500,000
    (float("inf"), 0.12),  # 12% above £1,500,000
]

# FTB relief: only available if purchase price ≤ £500,000
FIRST_TIME_BUYER_BANDS = [
    (300_000, 0.00),   # 0% up to £300,000
    (500_000, 0.05),   # 5% on £300,001–£500,000
]

# Additional property surcharge: 5% (increased from 3% on 31 October 2024)
# Source: Autumn Budget 2024
ADDITIONAL_PROPERTY_SURCHARGE = 0.05

FTB_MAX_PRICE = 500_000


def _calculate_banded(price: int, bands: list[tuple[float, float]]) -> int:
    """Calculate tax across progressive bands."""
    tax = 0
    prev_threshold = 0
    for threshold, rate in bands:
        if price <= prev_threshold:
            break
        taxable = min(price, threshold) - prev_threshold
        tax += taxable * rate
        prev_threshold = threshold
    return round(tax)


_tool_kwargs: dict = {}
if ToolAnnotations is not None:
    _tool_kwargs["annotations"] = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )


@mcp.tool(
    title="Stamp Duty Calculator",
    **_tool_kwargs,
)
def estimate_stamp_duty(
    purchase_price: Annotated[
        int,
        Field(description="Property purchase price in GBP (whole pounds). Example: 300000"),
    ],
    first_time_buyer: Annotated[
        bool,
        Field(
            description=(
                "True if the buyer has never owned property before. "
                "Unlocks reduced rates on purchases up to £500,000."
            ),
        ),
    ] = False,
    additional_property: Annotated[
        bool,
        Field(
            description=(
                "True if the buyer already owns another property (buy-to-let, second home). "
                "Adds a 5% surcharge on the entire purchase price."
            ),
        ),
    ] = False,
    country: Annotated[
        Literal["england"],
        Field(
            description=(
                "Only 'england' (covering England & Northern Ireland) is supported. "
                "Scotland uses LBTT and Wales uses LTT — different tax systems."
            ),
        ),
    ] = "england",
) -> dict:
    """Calculate UK Stamp Duty Land Tax (SDLT) for a residential property purchase.

    Use this when a user is buying a home in England or Northern Ireland and wants to
    know how much stamp duty they'll pay. Returns a full breakdown: base tax per band,
    any additional property surcharge, total tax, and effective rate as a percentage.

    Example: A £300,000 standard purchase returns £5,000 total stamp duty (1.67% effective rate).

    Not suitable for: commercial property, mixed-use, corporate purchases, or transfers
    of equity. Scotland (LBTT) and Wales (LTT) are not yet supported.
    """
    if country != "england":
        return {
            "error": f"Only England & Northern Ireland SDLT is currently supported. Got: {country}",
            "suggestion": "Scotland uses LBTT, Wales uses LTT — different rate structures.",
        }

    if purchase_price < 0:
        return {"error": "Purchase price must be non-negative."}

    # First-time buyer relief only applies up to £500,000
    if first_time_buyer and purchase_price <= FTB_MAX_PRICE and not additional_property:
        bands = FIRST_TIME_BUYER_BANDS
        buyer_type = "first-time buyer"
    else:
        bands = STANDARD_BANDS
        if first_time_buyer and purchase_price > FTB_MAX_PRICE:
            buyer_type = (
                f"standard (first-time buyer relief not available above £{FTB_MAX_PRICE:,})"
            )
        else:
            buyer_type = "standard"

    base_tax = _calculate_banded(purchase_price, bands)
    surcharge = round(purchase_price * ADDITIONAL_PROPERTY_SURCHARGE) if additional_property else 0
    total_tax = base_tax + surcharge
    effective_rate = round((total_tax / purchase_price) * 100, 2) if purchase_price > 0 else 0

    return {
        "purchase_price": purchase_price,
        "buyer_type": buyer_type,
        "additional_property": additional_property,
        "base_tax": base_tax,
        "additional_property_surcharge": surcharge,
        "total_stamp_duty": total_tax,
        "effective_rate_percent": effective_rate,
        "country": "England & Northern Ireland",
        "note": (
            "SDLT rates from 1 April 2025. "
            "Temporary higher nil-rate bands (Sep 2022\u2013Mar 2025) have reverted."
        ),
    }
