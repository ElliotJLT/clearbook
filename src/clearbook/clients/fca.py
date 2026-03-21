"""
FCA Financial Services Register API client.

Async client for the FCA FS Register API (V0.1).
Docs: https://register.fca.org.uk/Developer/s/

Authentication requires X-Auth-Email and X-Auth-Key headers,
obtained by registering at the FCA developer portal.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://register.fca.org.uk/services/V0.1"
DEFAULT_PER_PAGE = 20
MAX_REQUESTS = 50
RATE_WINDOW_SECONDS = 10.0
CACHE_TTL_SECONDS = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SearchType(str, Enum):
    FIRM = "firm"
    INDIVIDUAL = "individual"
    FUND = "fund"


class FirmStatus(str, Enum):
    AUTHORISED = "Authorised"
    REGISTERED = "Registered"
    NO_LONGER_AUTHORISED = "No longer authorised"
    EEA_AUTHORISED = "EEA Authorised"


# ---------------------------------------------------------------------------
# Pydantic models — Search
# ---------------------------------------------------------------------------

class ResultInfo(BaseModel):
    page: int = 1
    per_page: int = Field(DEFAULT_PER_PAGE, alias="per_page")
    total_count: int = 0

    model_config = {"populate_by_name": True, "extra": "allow"}


class SearchResult(BaseModel):
    """A single search result from the FCA Register.

    The real API returns keys like "Organisation Name" for firm searches.
    Some fields (URL, Reference Number, etc.) may not be present in all
    response variants, so everything defaults to empty string.
    """
    url: str = Field("", alias="URL")
    reference_number: str = Field("", alias="Reference Number")
    type_of_business: str = Field("", alias="Type of business or Individual")
    name: str = Field("", alias="Name")
    organisation_name: str = Field("", alias="Organisation Name")
    status: str = Field("", alias="Status")

    model_config = {"populate_by_name": True, "extra": "allow"}

    @property
    def display_name(self) -> str:
        """Return the best available name for this result."""
        return self.organisation_name or self.name


class SearchResponse(BaseModel):
    status: str = Field("", alias="Status")
    message: str = Field("", alias="Message")
    result_info: ResultInfo = Field(default_factory=ResultInfo, alias="ResultInfo")
    data: list[SearchResult] = Field(default_factory=list, alias="Data")

    model_config = {"populate_by_name": True, "extra": "allow"}


# ---------------------------------------------------------------------------
# Pydantic models — Firm
# ---------------------------------------------------------------------------

class FirmDetail(BaseModel):
    frn: str = Field("", alias="FRN")
    organisation_name: str = Field("", alias="Organisation Name")
    business_type: str = Field("", alias="Business Type")
    status: str = Field("", alias="Status")
    status_effective_date: str = Field("", alias="Status Effective Date")
    sub_status: str = Field("", alias="Sub-Status")
    sub_status_effective_from: str = Field("", alias="Sub Status Effective from")
    companies_house_number: str = Field("", alias="Companies House Number")
    mutual_society_number: str = Field("", alias="Mutual Society Number")
    client_money_permission: str = Field("", alias="Client Money Permission")
    psd_agent_status: str = Field("", alias="PSD Agent Status")
    psd_agent_effective_date: str = Field("", alias="PSD Agent Effective date")
    psd_emd_status: str = Field("", alias="PSD / EMD Status")
    psd_emd_effective_date: str = Field("", alias="PSD / EMD Effective Date")
    e_money_agent_status: str = Field("", alias="E-Money Agent Status")
    e_money_agent_effective_date: str = Field("", alias="E-Money Agent Effective Date")
    mlrs_status: str = Field("", alias="MLRs Status")
    mlrs_status_effective_date: str = Field("", alias="MLRs Status Effective Date")
    system_timestamp: str = Field("", alias="System Timestamp")

    # Sub-resource URLs returned by the API
    names_url: str = Field("", alias="Name")
    individuals_url: str = Field("", alias="Individuals")
    requirements_url: str = Field("", alias="Requirements")
    permission_url: str = Field("", alias="Permission")
    passport_url: str = Field("", alias="Passport")
    regulators_url: str = Field("", alias="Regulators")
    appointed_representative_url: str = Field("", alias="Appointed Representative")
    address_url: str = Field("", alias="Address")
    waivers_url: str = Field("", alias="Waivers")
    exclusions_url: str = Field("", alias="Exclusions")
    disciplinary_history_url: str = Field("", alias="DisciplinaryHistory")

    exceptional_info_details: list[dict[str, str]] = Field(
        default_factory=list, alias="Exceptional Info Details"
    )

    model_config = {"populate_by_name": True, "extra": "allow"}


class FirmResponse(BaseModel):
    status: str = Field("", alias="Status")
    message: str = Field("", alias="Message")
    result_info: ResultInfo = Field(default_factory=ResultInfo, alias="ResultInfo")
    data: list[FirmDetail] = Field(default_factory=list, alias="Data")

    model_config = {"populate_by_name": True, "extra": "allow"}


# ---------------------------------------------------------------------------
# Pydantic models — Address
# ---------------------------------------------------------------------------

class FirmAddress(BaseModel):
    address_type: str = Field("", alias="Address Type")
    address_line_1: str = Field("", alias="Address Line 1")
    address_line_2: str = Field("", alias="Address Line 2")
    address_line_3: str = Field("", alias="Address Line 3")
    address_line_4: str = Field("", alias="Address Line 4")
    town: str = Field("", alias="Town")
    county: str = Field("", alias="County")
    postcode: str = Field("", alias="Postcode")
    country: str = Field("", alias="Country")
    phone_number: str = Field("", alias="Phone Number")
    website_address: str = Field("", alias="Website Address")
    url: str = Field("", alias="URL")

    model_config = {"populate_by_name": True, "extra": "allow"}


class FirmAddressResponse(BaseModel):
    status: str = Field("", alias="Status")
    message: str = Field("", alias="Message")
    result_info: ResultInfo = Field(default_factory=ResultInfo, alias="ResultInfo")
    data: list[FirmAddress] = Field(default_factory=list, alias="Data")

    model_config = {"populate_by_name": True, "extra": "allow"}


# ---------------------------------------------------------------------------
# Pydantic models — Permissions
# ---------------------------------------------------------------------------

class PermissionDetail(BaseModel):
    """A single permission entry within a permission category.

    The permissions endpoint returns a dict where keys are permission names
    (e.g. "Advising on regulated mortgage contracts") and values are lists
    of objects with Customer Type, Investment Type, and Limitation fields.
    We flatten this into a structured model.
    """
    permission_name: str = ""
    customer_type: str = Field("", alias="Customer Type")
    investment_type: str = Field("", alias="Investment Type")
    limitation: str = Field("", alias="Limitation")

    model_config = {"populate_by_name": True, "extra": "allow"}


class FirmPermissionsResponse(BaseModel):
    """Wrapper for the permissions endpoint.

    The raw API returns Data as a list with a single dict where keys are
    permission category names. We parse this in the client method.
    """
    status: str = Field("", alias="Status")
    message: str = Field("", alias="Message")
    result_info: ResultInfo = Field(default_factory=ResultInfo, alias="ResultInfo")
    permissions: list[PermissionDetail] = Field(default_factory=list)

    model_config = {"populate_by_name": True, "extra": "allow"}


# ---------------------------------------------------------------------------
# Pydantic models — Individuals
# ---------------------------------------------------------------------------

class FirmIndividual(BaseModel):
    name: str = Field("", alias="Name")
    irn: str = Field("", alias="IRN")
    status: str = Field("", alias="Status")
    url: str = Field("", alias="URL")

    model_config = {"populate_by_name": True, "extra": "allow"}


class FirmIndividualsResponse(BaseModel):
    status: str = Field("", alias="Status")
    message: str = Field("", alias="Message")
    result_info: ResultInfo = Field(default_factory=ResultInfo, alias="ResultInfo")
    data: list[FirmIndividual] = Field(default_factory=list, alias="Data")

    model_config = {"populate_by_name": True, "extra": "allow"}


# ---------------------------------------------------------------------------
# Pydantic models — Disciplinary History
# ---------------------------------------------------------------------------

class DisciplinaryAction(BaseModel):
    type_of_action: str = Field("", alias="TypeofAction")
    enforcement_type: str = Field("", alias="EnforcementType")
    action_effective_from: str = Field("", alias="ActionEffectiveFrom")
    type_of_description: str = Field("", alias="TypeofDescription")

    model_config = {"populate_by_name": True, "extra": "allow"}


class FirmDisciplinaryResponse(BaseModel):
    status: str = Field("", alias="Status")
    message: str = Field("", alias="Message")
    result_info: ResultInfo = Field(default_factory=ResultInfo, alias="ResultInfo")
    data: list[DisciplinaryAction] = Field(default_factory=list, alias="Data")

    model_config = {"populate_by_name": True, "extra": "allow"}


# ---------------------------------------------------------------------------
# Pydantic models — Regulators
# ---------------------------------------------------------------------------

class FirmRegulator(BaseModel):
    regulator_name: str = Field("", alias="Regulator Name")
    effective_date: str = Field("", alias="Effective Date")
    termination_date: str = Field("", alias="Termination Date")

    model_config = {"populate_by_name": True, "extra": "allow"}


class FirmRegulatorsResponse(BaseModel):
    status: str = Field("", alias="Status")
    message: str = Field("", alias="Message")
    result_info: ResultInfo = Field(default_factory=ResultInfo, alias="ResultInfo")
    data: list[FirmRegulator] = Field(default_factory=list, alias="Data")

    model_config = {"populate_by_name": True, "extra": "allow"}


# ---------------------------------------------------------------------------
# Pydantic models — Names
# ---------------------------------------------------------------------------

class FirmName(BaseModel):
    name: str = Field("", alias="Name")
    status: str = Field("", alias="Status")
    effective_from: str = Field("", alias="Effective From")
    effective_to: str = Field("", alias="Effective To")

    model_config = {"populate_by_name": True, "extra": "allow"}


class FirmNamesResponse(BaseModel):
    status: str = Field("", alias="Status")
    message: str = Field("", alias="Message")
    result_info: ResultInfo = Field(default_factory=ResultInfo, alias="ResultInfo")
    data: list[dict[str, Any]] = Field(default_factory=list, alias="Data")

    model_config = {"populate_by_name": True, "extra": "allow"}

    @property
    def current_names(self) -> list[FirmName]:
        names: list[FirmName] = []
        for item in self.data:
            for entry in item.get("Current Names", []):
                names.append(FirmName.model_validate(entry))
        return names

    @property
    def previous_names(self) -> list[FirmName]:
        names: list[FirmName] = []
        for item in self.data:
            for entry in item.get("Previous Names", []):
                names.append(FirmName.model_validate(entry))
        return names


# ---------------------------------------------------------------------------
# Pydantic models — Requirements
# ---------------------------------------------------------------------------

class FirmRequirement(BaseModel):
    requirement_reference: str = Field("", alias="Requirement Reference")
    effective_date: str = Field("", alias="Effective Date")
    financial_promotions_requirement: str = Field("", alias="Financial Promotions Requirement")
    financial_promotions_investment_types: str = Field(
        "", alias="Financial Promotions Investment Types"
    )

    model_config = {"populate_by_name": True, "extra": "allow"}


class FirmRequirementsResponse(BaseModel):
    status: str = Field("", alias="Status")
    message: str = Field("", alias="Message")
    result_info: ResultInfo = Field(default_factory=ResultInfo, alias="ResultInfo")
    data: list[FirmRequirement] = Field(default_factory=list, alias="Data")

    model_config = {"populate_by_name": True, "extra": "allow"}


# ---------------------------------------------------------------------------
# Pydantic models — Appointed Representatives
# ---------------------------------------------------------------------------

class AppointedRepresentative(BaseModel):
    """Appointed representative record. Field names may vary; we capture raw."""
    raw: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class FirmAppointedRepsResponse(BaseModel):
    status: str = Field("", alias="Status")
    message: str = Field("", alias="Message")
    result_info: ResultInfo = Field(default_factory=ResultInfo, alias="ResultInfo")
    data: list[dict[str, Any]] = Field(default_factory=list, alias="Data")

    model_config = {"populate_by_name": True, "extra": "allow"}


# ---------------------------------------------------------------------------
# Pydantic models — Waivers
# ---------------------------------------------------------------------------

class FirmWaiver(BaseModel):
    waivers_discretions: str = Field("", alias="Waivers_Discretions")
    waivers_discretions_url: str = Field("", alias="Waivers_Discretions_URL")
    rule_article_no: list[str] = Field(default_factory=list, alias="Rule_ArticleNo")

    model_config = {"populate_by_name": True, "extra": "allow"}


class FirmWaiversResponse(BaseModel):
    status: str = Field("", alias="Status")
    message: str = Field("", alias="Message")
    result_info: ResultInfo = Field(default_factory=ResultInfo, alias="ResultInfo")
    data: list[FirmWaiver] = Field(default_factory=list, alias="Data")

    model_config = {"populate_by_name": True, "extra": "allow"}


# ---------------------------------------------------------------------------
# Pydantic models — Exclusions
# ---------------------------------------------------------------------------

class FirmExclusion(BaseModel):
    psd2_exclusion_type: str = Field("", alias="PSD2_Exclusion_Type")
    particular_exclusion_relied_upon: str = Field("", alias="Particular_Exclusion_relied_upon")
    description_of_services: str = Field("", alias="Description_of_services")

    model_config = {"populate_by_name": True, "extra": "allow"}


class FirmExclusionsResponse(BaseModel):
    status: str = Field("", alias="Status")
    message: str = Field("", alias="Message")
    result_info: ResultInfo = Field(default_factory=ResultInfo, alias="ResultInfo")
    data: list[FirmExclusion] = Field(default_factory=list, alias="Data")

    model_config = {"populate_by_name": True, "extra": "allow"}


# ---------------------------------------------------------------------------
# Pydantic models — Individual detail
# ---------------------------------------------------------------------------

class IndividualDetail(BaseModel):
    irn: str = ""
    full_name: str = ""
    commonly_used_name: str = ""
    status: str = ""
    disciplinary_history_url: str = ""
    roles_activities_url: str = ""
    firm_name: str = ""
    location: str = ""


class IndividualResponse(BaseModel):
    status: str = Field("", alias="Status")
    message: str = Field("", alias="Message")
    result_info: ResultInfo = Field(default_factory=ResultInfo, alias="ResultInfo")
    data: list[IndividualDetail] = Field(default_factory=list)

    model_config = {"populate_by_name": True, "extra": "allow"}


# ---------------------------------------------------------------------------
# Mortgage-related permission names
# ---------------------------------------------------------------------------

MORTGAGE_PERMISSION_NAMES = frozenset({
    "Advising on regulated mortgage contracts",
    "Arranging (bringing about) regulated mortgage contracts",
    "Making arrangements with a view to regulated mortgage contracts",
    "Entering into regulated mortgage contracts as lender",
    "Administering regulated mortgage contracts",
    "Advising on home finance transactions",
    "Arranging (bringing about) home finance transactions",
    "Making arrangements with a view to home finance transactions",
    "Agreeing to carry on a regulated activity",
})


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

@dataclass
class _RateLimiter:
    """Sliding-window rate limiter: max_requests per window_seconds."""
    max_requests: int = MAX_REQUESTS
    window_seconds: float = RATE_WINDOW_SECONDS
    _timestamps: list[float] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds
            self._timestamps = [t for t in self._timestamps if t > cutoff]
            if len(self._timestamps) >= self.max_requests:
                sleep_until = self._timestamps[0] + self.window_seconds
                delay = sleep_until - now
                if delay > 0:
                    await asyncio.sleep(delay)
                    # After sleeping, prune again
                    now = time.monotonic()
                    cutoff = now - self.window_seconds
                    self._timestamps = [t for t in self._timestamps if t > cutoff]
            self._timestamps.append(time.monotonic())


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

@dataclass
class _CacheEntry:
    data: Any
    expires_at: float


class _Cache:
    """Simple in-memory TTL cache keyed by URL string."""

    def __init__(self, ttl_seconds: float = CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, _CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.monotonic() > entry.expires_at:
                del self._store[key]
                return None
            return entry.data

    async def set(self, key: str, data: Any) -> None:
        async with self._lock:
            self._store[key] = _CacheEntry(
                data=data,
                expires_at=time.monotonic() + self._ttl,
            )

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()

    async def evict_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        async with self._lock:
            now = time.monotonic()
            expired = [k for k, v in self._store.items() if now > v.expires_at]
            for k in expired:
                del self._store[k]
            return len(expired)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class FCAClientError(Exception):
    """Base exception for FCA API client errors."""


class FCAAuthError(FCAClientError):
    """Raised when authentication fails (403)."""


class FCANotFoundError(FCAClientError):
    """Raised when a resource is not found (404 or API status indicates not found)."""


class FCARateLimitError(FCAClientError):
    """Raised when rate limited by the API (429)."""


class FCAServerError(FCAClientError):
    """Raised on 5xx responses."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class FCAClient:
    """Async client for the FCA Financial Services Register API.

    Usage::

        async with FCAClient(email="you@example.com", key="key123") as fca:
            results = await fca.search_firms("Cyborg Finance")
            firm = await fca.get_firm("919921")
            permissions = await fca.get_firm_permissions("919921")
    """

    def __init__(
        self,
        email: str,
        key: str = "",
        *,
        api_key: str = "",
        base_url: str = BASE_URL,
        cache_ttl_seconds: float = CACHE_TTL_SECONDS,
        max_requests_per_window: int = MAX_REQUESTS,
        rate_window_seconds: float = RATE_WINDOW_SECONDS,
        timeout: float = 30.0,
    ) -> None:
        self._email = email
        self._api_key = key or api_key
        if not self._api_key:
            raise FCAClientError("Either 'key' or 'api_key' must be provided.")
        self._base_url = base_url.rstrip("/")
        self._cache = _Cache(ttl_seconds=cache_ttl_seconds)
        self._rate_limiter = _RateLimiter(
            max_requests=max_requests_per_window,
            window_seconds=rate_window_seconds,
        )
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._owns_client: bool = False

    async def __aenter__(self) -> "FCAClient":
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "X-Auth-Email": self._email,
                "X-Auth-Key": self._api_key,
                "Accept": "application/json",
            },
            timeout=httpx.Timeout(self._timeout),
        )
        self._owns_client = True
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._client and self._owns_client:
            await self._client.aclose()
            self._client = None
            self._owns_client = False

    async def close(self) -> None:
        """Explicitly close the underlying HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._owns_client = False

    @property
    def cache(self) -> _Cache:
        return self._cache

    def _ensure_client(self) -> httpx.AsyncClient:
        """Return the httpx client, lazily creating one if not using context manager."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "X-Auth-Email": self._email,
                    "X-Auth-Key": self._api_key,
                    "Accept": "application/json",
                },
                timeout=httpx.Timeout(self._timeout),
            )
            self._owns_client = True
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Make a rate-limited, cached request to the FCA API."""
        client = self._ensure_client()

        cache_key = f"{method}:{path}:{params}"
        if use_cache:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached

        await self._rate_limiter.acquire()

        response = await client.request(method, path, params=params)

        if response.status_code == 403:
            raise FCAAuthError(
                f"Authentication failed (403). Check X-Auth-Email and X-Auth-Key. "
                f"Body: {response.text[:200]}"
            )
        if response.status_code == 404:
            raise FCANotFoundError(f"Resource not found: {path}")
        if response.status_code == 429:
            raise FCARateLimitError(
                "Rate limited by FCA API. Back off and retry."
            )
        if response.status_code >= 500:
            raise FCAServerError(
                f"FCA API server error ({response.status_code}): {response.text[:200]}"
            )
        if response.status_code >= 400:
            raise FCAClientError(
                f"FCA API error ({response.status_code}): {response.text[:200]}"
            )

        data = response.json()

        if use_cache:
            await self._cache.set(cache_key, data)

        return data

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        return await self._request("GET", path, params=params, use_cache=use_cache)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        search_type: SearchType = SearchType.FIRM,
        *,
        page: int = 1,
    ) -> SearchResponse:
        """Search the FS Register for firms, individuals, or funds.

        Args:
            query: Name or partial name to search for.
            search_type: One of 'firm', 'individual', 'fund'.
            page: Page number (1-based).

        Returns:
            SearchResponse with matched results and pagination info.
        """
        params: dict[str, Any] = {
            "q": query,
            "type": search_type.value,
        }
        if page > 1:
            params["page"] = page

        raw = await self._get("/Search", params=params)
        return SearchResponse.model_validate(raw)

    async def search_firms(
        self,
        query: str,
        *,
        page: int = 1,
    ) -> SearchResponse:
        """Convenience: search for firms only."""
        return await self.search(query, SearchType.FIRM, page=page)

    async def search_all_firms(
        self,
        query: str,
        *,
        max_pages: int = 50,
    ) -> list[SearchResult]:
        """Paginate through all firm search results.

        Args:
            query: Search term.
            max_pages: Safety cap to prevent runaway pagination.

        Returns:
            Flat list of all SearchResult objects across pages.
        """
        all_results: list[SearchResult] = []
        page = 1

        while page <= max_pages:
            resp = await self.search_firms(query, page=page)
            all_results.extend(resp.data)

            total = resp.result_info.total_count
            per_page = resp.result_info.per_page or DEFAULT_PER_PAGE
            if page * per_page >= total:
                break
            page += 1

        return all_results

    # ------------------------------------------------------------------
    # Firm detail
    # ------------------------------------------------------------------

    async def get_firm(self, frn: str) -> FirmResponse:
        """Get core firm details by FRN (Firm Reference Number)."""
        raw = await self._get(f"/Firm/{frn}")
        return FirmResponse.model_validate(raw)

    async def get_firm_addresses(self, frn: str) -> FirmAddressResponse:
        """Get all addresses for a firm."""
        raw = await self._get(f"/Firm/{frn}/Address")
        return FirmAddressResponse.model_validate(raw)

    async def get_firm_permissions(self, frn: str) -> FirmPermissionsResponse:
        """Get firm permissions (activities the firm is authorised to perform).

        The API returns permissions as a dict where keys are activity names
        and values are lists of limitation/investment-type objects. We flatten
        this into a list of PermissionDetail objects.
        """
        raw = await self._get(f"/Firm/{frn}/Permissions")

        permissions: list[PermissionDetail] = []
        data_list = raw.get("Data", [])
        for data_item in data_list:
            if not isinstance(data_item, dict):
                continue
            # Skip metadata keys
            skip_keys = {"CBTL Status", "CBTL Effective Date"}
            for perm_name, entries in data_item.items():
                if perm_name in skip_keys:
                    continue
                if isinstance(entries, list):
                    for entry in entries:
                        if isinstance(entry, dict):
                            detail = PermissionDetail.model_validate(entry)
                            detail.permission_name = perm_name
                            permissions.append(detail)
                        elif isinstance(entry, str):
                            # Some entries are just strings (e.g. "Limitation Not Found")
                            detail = PermissionDetail(
                                permission_name=perm_name, limitation=entry
                            )
                            permissions.append(detail)

        return FirmPermissionsResponse(
            status=raw.get("Status", ""),
            message=raw.get("Message", ""),
            result_info=ResultInfo.model_validate(raw.get("ResultInfo", {})),
            permissions=permissions,
        )

    async def get_firm_individuals(
        self,
        frn: str,
        *,
        page: int = 1,
    ) -> FirmIndividualsResponse:
        """Get individuals associated with a firm."""
        params: dict[str, Any] = {}
        if page > 1:
            params["page"] = page
        raw = await self._get(f"/Firm/{frn}/Individuals", params=params or None)
        return FirmIndividualsResponse.model_validate(raw)

    async def get_all_firm_individuals(
        self,
        frn: str,
        *,
        max_pages: int = 50,
    ) -> list[FirmIndividual]:
        """Paginate through all individuals for a firm."""
        all_individuals: list[FirmIndividual] = []
        page = 1

        while page <= max_pages:
            resp = await self.get_firm_individuals(frn, page=page)
            all_individuals.extend(resp.data)

            total = resp.result_info.total_count
            per_page = resp.result_info.per_page or DEFAULT_PER_PAGE
            if page * per_page >= total:
                break
            page += 1

        return all_individuals

    async def get_firm_disciplinary_history(self, frn: str) -> FirmDisciplinaryResponse:
        """Get disciplinary history for a firm."""
        raw = await self._get(f"/Firm/{frn}/DisciplinaryHistory")
        return FirmDisciplinaryResponse.model_validate(raw)

    async def get_firm_regulators(self, frn: str) -> FirmRegulatorsResponse:
        """Get regulators for a firm."""
        raw = await self._get(f"/Firm/{frn}/Regulators")
        return FirmRegulatorsResponse.model_validate(raw)

    async def get_firm_names(self, frn: str) -> FirmNamesResponse:
        """Get current and previous names for a firm."""
        raw = await self._get(f"/Firm/{frn}/Names")
        return FirmNamesResponse.model_validate(raw)

    async def get_firm_requirements(self, frn: str) -> FirmRequirementsResponse:
        """Get regulatory requirements for a firm."""
        raw = await self._get(f"/Firm/{frn}/Requirements")
        return FirmRequirementsResponse.model_validate(raw)

    async def get_firm_appointed_representatives(
        self, frn: str
    ) -> FirmAppointedRepsResponse:
        """Get appointed representatives for a firm."""
        raw = await self._get(f"/Firm/{frn}/AR")
        return FirmAppointedRepsResponse.model_validate(raw)

    async def get_firm_waivers(self, frn: str) -> FirmWaiversResponse:
        """Get waivers for a firm."""
        raw = await self._get(f"/Firm/{frn}/Waivers")
        return FirmWaiversResponse.model_validate(raw)

    async def get_firm_exclusions(self, frn: str) -> FirmExclusionsResponse:
        """Get exclusions for a firm."""
        raw = await self._get(f"/Firm/{frn}/Exclusions")
        return FirmExclusionsResponse.model_validate(raw)

    # ------------------------------------------------------------------
    # Individual detail
    # ------------------------------------------------------------------

    async def get_individual(self, irn: str) -> IndividualResponse:
        """Get individual details by IRN (Individual Reference Number).

        The API nests fields under Details and Workplace Location keys,
        so we flatten them into our model.
        """
        raw = await self._get(f"/Individual/{irn}")
        individuals: list[IndividualDetail] = []

        for item in raw.get("Data", []):
            details = item.get("Details", {})
            workplace = item.get("Workplace Location 1", {})
            individuals.append(
                IndividualDetail(
                    irn=details.get("IRN", ""),
                    full_name=details.get("Full Name", ""),
                    commonly_used_name=details.get("Commonly Used Name", ""),
                    status=details.get("Status", ""),
                    disciplinary_history_url=details.get("Disciplinary History", ""),
                    roles_activities_url=details.get("Roles & Activities", ""),
                    firm_name=workplace.get("Firm Name", ""),
                    location=workplace.get("Location 1", ""),
                )
            )

        return IndividualResponse(
            status=raw.get("Status", ""),
            message=raw.get("Message", ""),
            result_info=ResultInfo.model_validate(raw.get("ResultInfo", {})),
            data=individuals,
        )

    async def get_individual_disciplinary_history(
        self, irn: str
    ) -> FirmDisciplinaryResponse:
        """Get disciplinary history for an individual. Same response shape as firm."""
        raw = await self._get(f"/Individual/{irn}/DisciplinaryHistory")
        return FirmDisciplinaryResponse.model_validate(raw)

    # ------------------------------------------------------------------
    # Mortgage-specific helpers
    # ------------------------------------------------------------------

    async def is_mortgage_broker(self, frn: str) -> bool:
        """Check if a firm holds any mortgage-related permissions."""
        perms = await self.get_firm_permissions(frn)
        return any(
            p.permission_name in MORTGAGE_PERMISSION_NAMES
            for p in perms.permissions
        )

    async def get_mortgage_permissions(self, frn: str) -> list[PermissionDetail]:
        """Return only mortgage-related permissions for a firm."""
        perms = await self.get_firm_permissions(frn)
        return [
            p for p in perms.permissions
            if p.permission_name in MORTGAGE_PERMISSION_NAMES
        ]

    async def search_mortgage_brokers(
        self,
        query: str,
        *,
        max_pages: int = 10,
    ) -> list[tuple[SearchResult, list[PermissionDetail]]]:
        """Search for firms and filter to those with mortgage permissions.

        Returns a list of (SearchResult, mortgage_permissions) tuples.
        Only firms that hold at least one mortgage permission are included.

        Note: This makes one search call + one permissions call per result,
        so it can be slow for broad queries. Use specific search terms.
        """
        results = await self.search_all_firms(query, max_pages=max_pages)
        mortgage_firms: list[tuple[SearchResult, list[PermissionDetail]]] = []

        for result in results:
            frn = result.reference_number
            if not frn:
                continue
            try:
                mortgage_perms = await self.get_mortgage_permissions(frn)
                if mortgage_perms:
                    mortgage_firms.append((result, mortgage_perms))
            except FCANotFoundError:
                continue

        return mortgage_firms

    # ------------------------------------------------------------------
    # Full firm profile (convenience aggregator)
    # ------------------------------------------------------------------

    async def get_firm_full_profile(self, frn: str) -> dict[str, Any]:
        """Fetch firm detail + all sub-resources in parallel.

        Returns a dict with keys: firm, addresses, permissions,
        individuals, disciplinary_history, regulators, names,
        requirements, waivers, exclusions, appointed_representatives.
        """
        (
            firm,
            addresses,
            permissions,
            individuals,
            disciplinary,
            regulators,
            names,
            requirements,
            waivers,
            exclusions,
            appointed_reps,
        ) = await asyncio.gather(
            self.get_firm(frn),
            self.get_firm_addresses(frn),
            self.get_firm_permissions(frn),
            self.get_firm_individuals(frn),
            self.get_firm_disciplinary_history(frn),
            self.get_firm_regulators(frn),
            self.get_firm_names(frn),
            self.get_firm_requirements(frn),
            self.get_firm_waivers(frn),
            self.get_firm_exclusions(frn),
            self.get_firm_appointed_representatives(frn),
        )

        return {
            "firm": firm,
            "addresses": addresses,
            "permissions": permissions,
            "individuals": individuals,
            "disciplinary_history": disciplinary,
            "regulators": regulators,
            "names": names,
            "requirements": requirements,
            "waivers": waivers,
            "exclusions": exclusions,
            "appointed_representatives": appointed_reps,
        }
