"""Core domain models for Settle."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    CONVEYANCER = "conveyancer"
    MORTGAGE_BROKER = "mortgage_broker"
    SURVEYOR = "surveyor"
    FINANCIAL_ADVISER = "financial_adviser"


class RegulatorStatus(str, Enum):
    AUTHORISED = "authorised"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    NO_LONGER_AUTHORISED = "no_longer_authorised"
    UNKNOWN = "unknown"


class Address(BaseModel):
    line_1: str = ""
    line_2: str = ""
    city: str = ""
    county: str = ""
    postcode: str = ""
    country: str = "England"


class DisciplinaryAction(BaseModel):
    date: str
    action_type: str
    description: str
    source: str  # "SRA" or "FCA"


class CompanyHealth(BaseModel):
    """Companies House cross-reference data."""
    company_number: Optional[str] = None
    status: Optional[str] = None  # active, dissolved, liquidation, etc.
    date_of_creation: Optional[str] = None
    sic_codes: list[str] = Field(default_factory=list)
    has_insolvency_history: bool = False
    has_charges: bool = False
    last_accounts_date: Optional[str] = None
    officer_count: int = 0


class RegulatoryProfile(BaseModel):
    """Regulatory status from SRA or FCA."""
    regulator: str  # "SRA", "FCA", "CLC"
    reference_number: str
    status: RegulatorStatus
    authorised_activities: list[str] = Field(default_factory=list)
    disciplinary_actions: list[DisciplinaryAction] = Field(default_factory=list)


class Provider(BaseModel):
    """A professional service provider — the core entity."""
    id: str  # settle internal ID
    name: str
    provider_type: ProviderType
    address: Address
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None

    # Regulatory
    regulatory_profiles: list[RegulatoryProfile] = Field(default_factory=list)

    # Company health
    company_health: Optional[CompanyHealth] = None

    # Quality signals
    google_rating: Optional[float] = None
    google_review_count: Optional[int] = None

    # Cross-reference keys
    company_reg_no: Optional[str] = None  # For Companies House lookup

    # Metadata
    data_sources: list[str] = Field(default_factory=list)  # which APIs contributed
    last_updated: Optional[str] = None

    @property
    def is_authorised(self) -> bool:
        return any(
            rp.status == RegulatorStatus.AUTHORISED for rp in self.regulatory_profiles
        )

    @property
    def has_disciplinary_history(self) -> bool:
        return any(
            len(rp.disciplinary_actions) > 0 for rp in self.regulatory_profiles
        )

    @property
    def trust_signals(self) -> dict:
        """Factual trust signals — no evaluative judgment."""
        return {
            "is_authorised": self.is_authorised,
            "has_disciplinary_history": self.has_disciplinary_history,
            "company_active": (
                self.company_health.status == "active"
                if self.company_health
                else None
            ),
            "has_insolvency_history": (
                self.company_health.has_insolvency_history
                if self.company_health
                else None
            ),
            "google_rating": self.google_rating,
            "google_review_count": self.google_review_count,
        }


class SearchFilters(BaseModel):
    """Factual filters for provider search — no evaluative criteria."""
    provider_type: Optional[ProviderType] = None
    postcode: Optional[str] = None
    radius_miles: int = 10
    name: Optional[str] = None
    authorised_only: bool = True
    max_results: int = 20


class SearchResult(BaseModel):
    """Search response."""
    providers: list[Provider]
    total_count: int
    filters_applied: SearchFilters
    data_sources: list[str]
