"""Core service layer — orchestrates data from multiple API clients."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Optional

from clearbook.models import (
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

logger = logging.getLogger(__name__)


class ClearbookService:
    """Orchestrates searches across SRA, FCA, and Companies House."""

    def __init__(
        self,
        sra_api_key: str = "",
        fca_email: str = "",
        fca_key: str = "",
        companies_house_key: str = "",
    ):
        self._sra_key = sra_api_key
        self._fca_email = fca_email
        self._fca_key = fca_key
        self._ch_key = companies_house_key
        self._sra = None
        self._fca = None
        self._ch = None

    @property
    def sra(self):
        if self._sra is None:
            from clearbook.clients.sra import SRAClient
            self._sra = SRAClient(api_key=self._sra_key)
        return self._sra

    @property
    def fca(self):
        if self._fca is None:
            from clearbook.clients.fca import FCAClient
            self._fca = FCAClient(email=self._fca_email, key=self._fca_key)
        return self._fca

    @property
    def ch(self):
        if self._ch is None:
            from clearbook.clients.companies_house import CompaniesHouseClient
            self._ch = CompaniesHouseClient(api_key=self._ch_key)
        return self._ch

    def _make_id(self, regulator: str, ref: str) -> str:
        raw = f"{regulator}:{ref}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    async def search(self, filters: SearchFilters) -> SearchResult:
        """Search for providers across regulatory registers."""
        providers: list[Provider] = []
        data_sources: list[str] = []

        if filters.provider_type in (ProviderType.CONVEYANCER, None):
            sra_results = await self._search_sra(filters)
            providers.extend(sra_results)
            if sra_results:
                data_sources.append("SRA")

        if filters.provider_type in (
            ProviderType.MORTGAGE_BROKER,
            ProviderType.FINANCIAL_ADVISER,
            None,
        ):
            fca_results = await self._search_fca(filters)
            providers.extend(fca_results)
            if fca_results:
                data_sources.append("FCA")

        # Enrich with Companies House data
        for provider in providers:
            await self._enrich_with_companies_house(provider)

        providers = providers[: filters.max_results]

        return SearchResult(
            providers=providers,
            total_count=len(providers),
            filters_applied=filters,
            data_sources=data_sources,
        )

    async def get_provider(
        self, regulator: str, reference_number: str
    ) -> Optional[Provider]:
        """Get a single enriched provider profile."""
        provider = None

        if regulator.upper() == "SRA":
            provider = await self._get_sra_provider(reference_number)
        elif regulator.upper() == "FCA":
            provider = await self._get_fca_provider(reference_number)

        if provider:
            await self._enrich_with_companies_house(provider)

        return provider

    async def get_disciplinary_history(
        self, regulator: str, reference_number: str
    ) -> list[DisciplinaryAction]:
        """Get disciplinary actions for a provider."""
        if regulator.upper() == "FCA":
            try:
                resp = await self.fca.get_firm_disciplinary_history(reference_number)
                return [
                    DisciplinaryAction(
                        date=getattr(action, "date", "unknown"),
                        action_type=getattr(action, "action_type", "unknown"),
                        description=getattr(action, "description", ""),
                        source="FCA",
                    )
                    for action in (resp.actions if hasattr(resp, "actions") else [])
                ]
            except Exception as e:
                logger.warning(f"Failed to get FCA disciplinary history for {reference_number}: {e}")
                return []
        return []

    # ---- SRA ----

    async def _search_sra(self, filters: SearchFilters) -> list[Provider]:
        """Search SRA register for conveyancers."""
        try:
            orgs = await self.sra.search_conveyancers(
                postcode=filters.postcode or "",
                max_results=filters.max_results,
            )
            providers = []
            for org in orgs:
                provider = self._sra_org_to_provider(org)
                if filters.authorised_only and not provider.is_authorised:
                    continue
                providers.append(provider)
            return providers
        except Exception as e:
            logger.warning(f"SRA search failed: {e}")
            return []

    async def _get_sra_provider(self, sra_number: str) -> Optional[Provider]:
        try:
            org = await self.sra.get_organisation(sra_number)
            return self._sra_org_to_provider(org)
        except Exception as e:
            logger.warning(f"SRA get_organisation failed for {sra_number}: {e}")
            return None

    def _sra_org_to_provider(self, org) -> Provider:
        """Convert SRAOrganisation to Provider model."""
        # Extract address from head office or first office
        address = Address()
        head = org.head_office if hasattr(org, "head_office") else None
        if head is None and hasattr(org, "offices") and org.offices:
            head = org.offices[0]
        if head:
            address = Address(
                line_1=getattr(head, "address1", ""),
                line_2=getattr(head, "address2", ""),
                city=getattr(head, "town", ""),
                county=getattr(head, "county", ""),
                postcode=getattr(head, "postcode", ""),
            )

        # Map authorisation status
        auth_status = getattr(org, "authorisation_status", "").upper()
        status_map = {
            "AUTHORISED": RegulatorStatus.AUTHORISED,
            "YES": RegulatorStatus.AUTHORISED,
            "CEASE": RegulatorStatus.CANCELLED,
            "CONDITION": RegulatorStatus.AUTHORISED,
            "INTERVENE": RegulatorStatus.SUSPENDED,
        }

        sra_number = str(getattr(org, "sra_number", ""))

        return Provider(
            id=self._make_id("SRA", sra_number),
            name=getattr(org, "practice_name", ""),
            provider_type=ProviderType.CONVEYANCER,
            address=address,
            phone=getattr(head, "phone_number", "") if head else "",
            email=getattr(head, "email", "") if head else "",
            website=getattr(head, "website", "") if head else "",
            regulatory_profiles=[
                RegulatoryProfile(
                    regulator="SRA",
                    reference_number=sra_number,
                    status=status_map.get(auth_status, RegulatorStatus.UNKNOWN),
                    authorised_activities=getattr(org, "work_area", []),
                )
            ],
            data_sources=["SRA"],
            last_updated=datetime.now().isoformat(),
        )

    # ---- FCA ----

    async def _search_fca(self, filters: SearchFilters) -> list[Provider]:
        """Search FCA register for mortgage brokers."""
        try:
            query = filters.postcode or filters.name or "mortgage broker"
            resp = await self.fca.search_firms(query)
            providers = []
            for result in resp.data:
                provider = self._fca_result_to_provider(result)
                if filters.authorised_only and not provider.is_authorised:
                    continue
                providers.append(provider)
            return providers
        except Exception as e:
            logger.warning(f"FCA search failed: {e}")
            return []

    async def _get_fca_provider(self, frn: str) -> Optional[Provider]:
        try:
            firm = await self.fca.get_firm(frn)
            return self._fca_firm_to_provider(firm)
        except Exception as e:
            logger.warning(f"FCA get_firm failed for {frn}: {e}")
            return None

    def _fca_result_to_provider(self, result) -> Provider:
        """Convert FCA SearchResult to Provider model."""
        status_str = getattr(result, "status", "").lower()
        status_map = {
            "authorised": RegulatorStatus.AUTHORISED,
            "registered": RegulatorStatus.AUTHORISED,
            "suspended": RegulatorStatus.SUSPENDED,
            "cancelled": RegulatorStatus.CANCELLED,
            "no longer authorised": RegulatorStatus.NO_LONGER_AUTHORISED,
        }

        frn = getattr(result, "reference_number", "") or getattr(result, "frn", "")

        return Provider(
            id=self._make_id("FCA", frn),
            name=result.display_name if hasattr(result, "display_name") else getattr(result, "name", ""),
            provider_type=ProviderType.MORTGAGE_BROKER,
            address=Address(),  # FCA search results have limited address data
            regulatory_profiles=[
                RegulatoryProfile(
                    regulator="FCA",
                    reference_number=frn,
                    status=status_map.get(status_str, RegulatorStatus.UNKNOWN),
                )
            ],
            data_sources=["FCA"],
            last_updated=datetime.now().isoformat(),
        )

    def _fca_firm_to_provider(self, firm) -> Provider:
        """Convert FCA FirmResponse to Provider model."""
        detail = firm.detail if hasattr(firm, "detail") else firm
        status_str = getattr(detail, "status", "").lower()
        status_map = {
            "authorised": RegulatorStatus.AUTHORISED,
            "registered": RegulatorStatus.AUTHORISED,
            "suspended": RegulatorStatus.SUSPENDED,
            "cancelled": RegulatorStatus.CANCELLED,
            "no longer authorised": RegulatorStatus.NO_LONGER_AUTHORISED,
        }

        frn = getattr(detail, "frn", "")

        return Provider(
            id=self._make_id("FCA", frn),
            name=getattr(detail, "name", ""),
            provider_type=ProviderType.MORTGAGE_BROKER,
            address=Address(),
            phone=getattr(detail, "phone", ""),
            email=getattr(detail, "email", ""),
            website=getattr(detail, "website", ""),
            regulatory_profiles=[
                RegulatoryProfile(
                    regulator="FCA",
                    reference_number=frn,
                    status=status_map.get(status_str, RegulatorStatus.UNKNOWN),
                )
            ],
            data_sources=["FCA"],
            last_updated=datetime.now().isoformat(),
        )

    # ---- Companies House enrichment ----

    async def _enrich_with_companies_house(self, provider: Provider) -> None:
        """Cross-reference with Companies House for company health."""
        # Try company reg number from regulatory profile first, then name search
        company_number = None

        # SRA orgs sometimes have company registration numbers
        for rp in provider.regulatory_profiles:
            if rp.regulator == "SRA":
                # We'd need to store this — for now, search by name
                break

        try:
            search_result = await self.ch.search_companies(provider.name, items_per_page=1)
            if hasattr(search_result, "items") and search_result.items:
                company = search_result.items[0]
                company_number = getattr(company, "company_number", None)

                if company_number:
                    # Get full profile
                    profile = await self.ch.get_company_profile(company_number)
                    provider.company_health = CompanyHealth(
                        company_number=company_number,
                        status=getattr(profile, "company_status", None),
                        date_of_creation=getattr(profile, "date_of_creation", None),
                        sic_codes=getattr(profile, "sic_codes", []) or [],
                        has_insolvency_history=getattr(profile, "has_insolvency_history", False),
                        has_charges=getattr(profile, "has_charges", False),
                    )

                    # Get officer count
                    try:
                        officers = await self.ch.get_officers(company_number)
                        if hasattr(officers, "active_count"):
                            provider.company_health.officer_count = officers.active_count
                        elif hasattr(officers, "total_results"):
                            provider.company_health.officer_count = officers.total_results
                    except Exception:
                        pass

                    if "companies_house" not in provider.data_sources:
                        provider.data_sources.append("companies_house")
        except Exception as e:
            logger.debug(f"Companies House enrichment failed for {provider.name}: {e}")
