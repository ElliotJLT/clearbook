"""Tests for core domain models."""

from settle.models import (
    Address,
    CompanyHealth,
    DisciplinaryAction,
    Provider,
    ProviderType,
    RegulatoryProfile,
    RegulatorStatus,
    SearchFilters,
    SearchResult,
)


def test_provider_is_authorised():
    provider = Provider(
        id="test123",
        name="Test Solicitors LLP",
        provider_type=ProviderType.CONVEYANCER,
        address=Address(postcode="SE15 4QN"),
        regulatory_profiles=[
            RegulatoryProfile(
                regulator="SRA",
                reference_number="12345",
                status=RegulatorStatus.AUTHORISED,
                authorised_activities=["conveyancing"],
            )
        ],
    )
    assert provider.is_authorised is True


def test_provider_not_authorised():
    provider = Provider(
        id="test456",
        name="Suspended Firm",
        provider_type=ProviderType.CONVEYANCER,
        address=Address(),
        regulatory_profiles=[
            RegulatoryProfile(
                regulator="SRA",
                reference_number="67890",
                status=RegulatorStatus.SUSPENDED,
            )
        ],
    )
    assert provider.is_authorised is False


def test_provider_has_disciplinary_history():
    provider = Provider(
        id="test789",
        name="Dodgy Firm",
        provider_type=ProviderType.MORTGAGE_BROKER,
        address=Address(),
        regulatory_profiles=[
            RegulatoryProfile(
                regulator="FCA",
                reference_number="111222",
                status=RegulatorStatus.AUTHORISED,
                disciplinary_actions=[
                    DisciplinaryAction(
                        date="2025-01-01",
                        action_type="fine",
                        description="Failed to comply",
                        source="FCA",
                    )
                ],
            )
        ],
    )
    assert provider.has_disciplinary_history is True


def test_provider_trust_signals():
    provider = Provider(
        id="test101",
        name="Good Firm",
        provider_type=ProviderType.CONVEYANCER,
        address=Address(),
        regulatory_profiles=[
            RegulatoryProfile(
                regulator="SRA",
                reference_number="333",
                status=RegulatorStatus.AUTHORISED,
            )
        ],
        company_health=CompanyHealth(
            company_number="12345678",
            status="active",
            has_insolvency_history=False,
        ),
        google_rating=4.5,
        google_review_count=42,
    )
    signals = provider.trust_signals
    assert signals["is_authorised"] is True
    assert signals["has_disciplinary_history"] is False
    assert signals["company_active"] is True
    assert signals["has_insolvency_history"] is False
    assert signals["google_rating"] == 4.5
    assert signals["google_review_count"] == 42


def test_search_filters_defaults():
    filters = SearchFilters()
    assert filters.authorised_only is True
    assert filters.max_results == 20
    assert filters.radius_miles == 10


def test_search_result():
    result = SearchResult(
        providers=[],
        total_count=0,
        filters_applied=SearchFilters(),
        data_sources=["SRA"],
    )
    assert result.total_count == 0
    assert "SRA" in result.data_sources
