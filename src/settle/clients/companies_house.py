"""Companies House API client.

Async client for the Companies House REST API (https://developer.company-information.service.gov.uk).
Handles authentication, rate limiting (600 req / 5 min), response caching (24h TTL),
and returns typed Pydantic models.
"""

from __future__ import annotations

import asyncio
import base64
import time
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://api.company-information.service.gov.uk"

RATE_LIMIT_REQUESTS = 600
RATE_LIMIT_WINDOW_SECONDS = 300  # 5 minutes

CACHE_TTL_SECONDS = 86_400  # 24 hours


def _normalise_company_number(raw: str) -> str:
    """Zero-pad a company number to 8 characters.

    Companies House requires 8-digit company numbers but upstream sources
    (e.g. SRA) often store them without leading zeros.  Prefixed numbers
    like 'SC123456' or 'NI012345' are left as-is when already >= 8 chars.

    Examples:
        "3120664"  -> "03120664"
        "03120664" -> "03120664"
        "SC12345"  -> "SC012345"  (Scottish company, padded to 8)
        "NI012345" -> "NI012345"  (already 8 chars)
    """
    raw = raw.strip().upper()
    if not raw:
        return raw
    # Separate any alpha prefix (e.g. SC, NI, OC, etc.) from numeric part
    prefix = ""
    digits = raw
    for i, ch in enumerate(raw):
        if ch.isdigit():
            prefix = raw[:i]
            digits = raw[i:]
            break
    else:
        # No digits found — return as-is
        return raw

    target_len = 8 - len(prefix)
    if len(digits) < target_len:
        digits = digits.zfill(target_len)

    return prefix + digits


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CompanyStatus(str, Enum):
    active = "active"
    dissolved = "dissolved"
    liquidation = "liquidation"
    receivership = "receivership"
    converted_closed = "converted-closed"
    voluntary_arrangement = "voluntary-arrangement"
    insolvency_proceedings = "insolvency-proceedings"
    administration = "administration"
    open = "open"
    closed = "closed"
    registered = "registered"
    removed = "removed"


class Address(BaseModel):
    premises: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    locality: Optional[str] = None
    region: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    care_of: Optional[str] = None
    po_box: Optional[str] = None

    model_config = {"extra": "allow"}


class CompanySearchItem(BaseModel):
    company_number: str
    title: str = ""
    company_status: Optional[str] = None
    company_type: Optional[str] = None
    date_of_creation: Optional[date] = None
    date_of_cessation: Optional[date] = None
    address: Optional[Address] = None
    sic_codes: Optional[List[str]] = Field(default=None, alias="sic_codes")
    description: Optional[str] = None
    address_snippet: Optional[str] = None
    snippet: Optional[Dict[str, Any]] = None

    model_config = {"extra": "allow", "populate_by_name": True}


class CompanySearchResult(BaseModel):
    """Paginated search results from /search/companies."""

    items: List[CompanySearchItem] = Field(default_factory=list)
    total_results: int = 0
    start_index: int = 0
    items_per_page: int = 0
    kind: Optional[str] = None
    page_number: Optional[int] = None

    model_config = {"extra": "allow"}


class PreviousCompanyName(BaseModel):
    name: Optional[str] = None
    effective_from: Optional[date] = None
    ceased_on: Optional[date] = None

    model_config = {"extra": "allow"}


class AccountsInfo(BaseModel):
    next_due: Optional[date] = None
    last_accounts: Optional[Dict[str, Any]] = None
    next_made_up_to: Optional[date] = None
    overdue: Optional[bool] = None
    accounting_reference_date: Optional[Dict[str, Any]] = None

    model_config = {"extra": "allow"}


class ConfirmationStatement(BaseModel):
    next_due: Optional[date] = None
    last_made_up_to: Optional[date] = None
    next_made_up_to: Optional[date] = None
    overdue: Optional[bool] = None

    model_config = {"extra": "allow"}


class CompanyProfile(BaseModel):
    company_number: str
    company_name: str = ""
    company_status: Optional[str] = None
    company_status_detail: Optional[str] = None
    type: Optional[str] = None
    date_of_creation: Optional[date] = None
    date_of_cessation: Optional[date] = None
    registered_office_address: Optional[Address] = None
    sic_codes: Optional[List[str]] = None
    has_insolvency_history: Optional[bool] = None
    has_charges: Optional[bool] = None
    has_been_liquidated: Optional[bool] = None
    jurisdiction: Optional[str] = None
    accounts: Optional[AccountsInfo] = None
    confirmation_statement: Optional[ConfirmationStatement] = None
    previous_company_names: Optional[List[PreviousCompanyName]] = None
    registered_office_is_in_dispute: Optional[bool] = None
    undeliverable_registered_office_address: Optional[bool] = None
    etag: Optional[str] = None
    last_full_members_list_date: Optional[date] = None
    can_file: Optional[bool] = None

    model_config = {"extra": "allow"}


class DateOfBirth(BaseModel):
    month: Optional[int] = None
    year: Optional[int] = None

    model_config = {"extra": "allow"}


class Officer(BaseModel):
    name: str = ""
    officer_role: Optional[str] = None
    appointed_on: Optional[date] = None
    resigned_on: Optional[date] = None
    nationality: Optional[str] = None
    country_of_residence: Optional[str] = None
    occupation: Optional[str] = None
    date_of_birth: Optional[DateOfBirth] = None
    address: Optional[Address] = None
    identification: Optional[Dict[str, Any]] = None
    links: Optional[Dict[str, Any]] = None

    model_config = {"extra": "allow"}


class OfficerList(BaseModel):
    items: List[Officer] = Field(default_factory=list)
    total_results: int = 0
    start_index: int = 0
    items_per_page: int = 0
    active_count: Optional[int] = None
    resigned_count: Optional[int] = None
    kind: Optional[str] = None
    etag: Optional[str] = None

    model_config = {"extra": "allow"}


class FilingHistoryItem(BaseModel):
    transaction_id: Optional[str] = None
    date: Optional[date] = None
    type: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None
    description_values: Optional[Dict[str, Any]] = None
    action_date: Optional[date] = None
    pages: Optional[int] = None
    barcode: Optional[str] = None
    paper_filed: Optional[bool] = None
    links: Optional[Dict[str, Any]] = None

    model_config = {"extra": "allow"}


class FilingHistory(BaseModel):
    items: List[FilingHistoryItem] = Field(default_factory=list)
    total_count: int = 0
    start_index: int = 0
    items_per_page: int = 0
    filing_history_status: Optional[str] = None

    model_config = {"extra": "allow"}


class InsolvencyPractitioner(BaseModel):
    name: Optional[str] = None
    address: Optional[Address] = None
    appointed_on: Optional[date] = None
    ceased_to_act_on: Optional[date] = None
    role: Optional[str] = None

    model_config = {"extra": "allow"}


class InsolvencyDate(BaseModel):
    type: Optional[str] = None
    date: Optional[date] = None

    model_config = {"extra": "allow"}


class InsolvencyCase(BaseModel):
    number: Optional[int] = None
    type: Optional[str] = None
    practitioners: List[InsolvencyPractitioner] = Field(default_factory=list)
    dates: List[InsolvencyDate] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class InsolvencyData(BaseModel):
    cases: List[InsolvencyCase] = Field(default_factory=list)
    status: List[str] = Field(default_factory=list)
    etag: Optional[str] = None

    model_config = {"extra": "allow"}


class RegulatoryReference(BaseModel):
    """Cross-reference record linking a Companies House registration number
    to an SRA or FCA entity."""

    company_number: str
    company_name: str
    source: str  # "sra" or "fca"
    reference_number: Optional[str] = None
    status: Optional[str] = None
    match_method: str = "company_number"


# ---------------------------------------------------------------------------
# Rate limiter — sliding-window token bucket
# ---------------------------------------------------------------------------


class _RateLimiter:
    """Sliding-window rate limiter.

    Tracks timestamps of requests within the current window and blocks
    (asyncio.sleep) when the budget is exhausted.
    """

    def __init__(
        self,
        max_requests: int = RATE_LIMIT_REQUESTS,
        window_seconds: float = RATE_LIMIT_WINDOW_SECONDS,
    ) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._timestamps: List[float] = []
        self._lock = asyncio.Lock()

    def _prune(self, now: float) -> None:
        cutoff = now - self._window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.pop(0)

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._prune(now)

            if len(self._timestamps) >= self._max_requests:
                sleep_for = self._timestamps[0] + self._window_seconds - now
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
                    now = time.monotonic()
                    self._prune(now)

            self._timestamps.append(now)


# ---------------------------------------------------------------------------
# Response cache
# ---------------------------------------------------------------------------


class _CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: float) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl


class _ResponseCache:
    """In-memory cache with TTL expiry."""

    def __init__(self, ttl: float = CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl
        self._store: Dict[str, _CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[key]
            return None
        return entry.value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = _CacheEntry(value, self._ttl)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CompaniesHouseError(Exception):
    """Base exception for Companies House API errors."""

    def __init__(self, status_code: int, message: str, body: Any = None) -> None:
        self.status_code = status_code
        self.message = message
        self.body = body
        super().__init__(f"HTTP {status_code}: {message}")


class CompanyNotFoundError(CompaniesHouseError):
    """Raised when a company number returns 404."""

    def __init__(self, company_number: str) -> None:
        self.company_number = company_number
        super().__init__(404, f"Company {company_number} not found")


class RateLimitExceededError(CompaniesHouseError):
    """Raised when the API returns 429 despite local rate limiting."""

    def __init__(self, retry_after: Optional[float] = None) -> None:
        self.retry_after = retry_after
        super().__init__(429, "Rate limit exceeded")


class AuthenticationError(CompaniesHouseError):
    """Raised on 401 — invalid or missing API key."""

    def __init__(self) -> None:
        super().__init__(401, "Invalid or missing API key")


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class CompaniesHouseClient:
    """Async client for the Companies House REST API.

    Usage::

        async with CompaniesHouseClient(api_key="YOUR_KEY") as ch:
            results = await ch.search_companies("Monzo")
            profile = await ch.get_company_profile("09446231")
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = BASE_URL,
        cache_ttl: float = CACHE_TTL_SECONDS,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries

        # Basic auth: key as username, empty password
        token = base64.b64encode(f"{api_key}:".encode()).decode()
        self._auth_header = f"Basic {token}"

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": self._auth_header,
                "Accept": "application/json",
            },
            timeout=httpx.Timeout(timeout),
        )
        self._rate_limiter = _RateLimiter()
        self._cache = _ResponseCache(ttl=cache_ttl)

    # -- Context manager --------------------------------------------------

    async def __aenter__(self) -> CompaniesHouseClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    # -- Low-level request ------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """Execute an API request with rate limiting, caching, and retries."""

        # Build cache key from method + path + sorted params
        cache_key = f"{method}:{path}"
        if params:
            sorted_params = "&".join(
                f"{k}={v}" for k, v in sorted(params.items()) if v is not None
            )
            cache_key += f"?{sorted_params}"

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        last_exc: Optional[Exception] = None

        for attempt in range(self._max_retries):
            await self._rate_limiter.acquire()

            try:
                # Strip None values from params
                clean_params = (
                    {k: v for k, v in (params or {}).items() if v is not None} or None
                )
                response = await self._client.request(method, path, params=clean_params)
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2**attempt)
                continue

            if response.status_code == 200:
                data = response.json()
                if use_cache:
                    self._cache.set(cache_key, data)
                return data

            if response.status_code == 404:
                # Extract company number from path if possible
                parts = path.strip("/").split("/")
                company_number = (
                    parts[1] if len(parts) >= 2 and parts[0] == "company" else path
                )
                raise CompanyNotFoundError(company_number)

            if response.status_code == 401:
                raise AuthenticationError()

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else (2**attempt * 5)
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(wait)
                    continue
                raise RateLimitExceededError(
                    retry_after=float(retry_after) if retry_after else None
                )

            # Other errors — retry on 5xx, raise immediately on 4xx
            if response.status_code >= 500 and attempt < self._max_retries - 1:
                last_exc = CompaniesHouseError(
                    response.status_code,
                    response.text,
                    body=response.text,
                )
                await asyncio.sleep(2**attempt)
                continue

            raise CompaniesHouseError(
                response.status_code,
                response.text,
                body=response.text,
            )

        raise last_exc or CompaniesHouseError(0, "Request failed after retries")

    # -- Company search ---------------------------------------------------

    async def search_companies(
        self,
        query: str,
        *,
        items_per_page: int = 20,
        start_index: int = 0,
    ) -> CompanySearchResult:
        """Search for companies by name.

        Args:
            query: Company name or keyword to search.
            items_per_page: Results per page (max 100).
            start_index: Pagination offset.

        Returns:
            CompanySearchResult with matching companies.
        """
        data = await self._request(
            "GET",
            "/search/companies",
            params={
                "q": query,
                "items_per_page": items_per_page,
                "start_index": start_index,
            },
        )
        return CompanySearchResult.model_validate(data)

    async def search_companies_by_sic_code(
        self,
        sic_code: str,
        *,
        query: Optional[str] = None,
        items_per_page: int = 20,
        start_index: int = 0,
    ) -> CompanySearchResult:
        """Search for companies filtered by SIC code.

        Uses the /advanced-search/companies endpoint which supports direct
        SIC code filtering. Falls back gracefully if the endpoint is unavailable.

        Args:
            sic_code: The SIC code to filter by (e.g. "69102" for solicitors).
            query: Optional search query to narrow results. If None, uses the SIC code.
            items_per_page: Results to fetch per page before filtering.
            start_index: Pagination offset.

        Returns:
            CompanySearchResult with only companies matching the SIC code.
        """
        search_query = query or sic_code
        data = await self._request(
            "GET",
            "/advanced-search/companies",
            params={
                "sic_codes": sic_code,
                "q": search_query if query else None,
                "size": items_per_page,
                "start_index": start_index,
            },
        )

        # The advanced search endpoint may not be available on all keys.
        # If we get data, parse it. The response shape differs from basic search.
        if "items" in data:
            # Normalise advanced-search items to CompanySearchItem shape
            items: List[Dict[str, Any]] = []
            for item in data.get("items", []):
                items.append(
                    {
                        "company_number": item.get("company_number", ""),
                        "title": item.get("company_name", item.get("title", "")),
                        "company_status": item.get("company_status"),
                        "company_type": item.get("company_type"),
                        "date_of_creation": item.get("date_of_creation"),
                        "date_of_cessation": item.get("date_of_cessation"),
                        "sic_codes": item.get("sic_codes"),
                        "address": item.get(
                            "registered_office_address", item.get("address")
                        ),
                    }
                )
            return CompanySearchResult(
                items=[CompanySearchItem.model_validate(i) for i in items],
                total_results=data.get("total_results", data.get("hits", len(items))),
                start_index=start_index,
                items_per_page=items_per_page,
            )

        return CompanySearchResult.model_validate(data)

    async def search_companies_by_sic_code_fallback(
        self,
        sic_code: str,
        *,
        query: str = "",
        items_per_page: int = 100,
        start_index: int = 0,
    ) -> CompanySearchResult:
        """Fallback SIC code search: fetches search results then filters
        by retrieving each company's profile to check SIC codes.

        This is expensive (1 + N API calls) but guaranteed accurate. Use
        sparingly and prefer `search_companies_by_sic_code` with the
        advanced-search endpoint when available.
        """
        if not query:
            query = "company"

        search_result = await self.search_companies(
            query, items_per_page=items_per_page, start_index=start_index
        )

        matched: List[CompanySearchItem] = []
        for item in search_result.items:
            try:
                profile = await self.get_company_profile(item.company_number)
            except CompanyNotFoundError:
                continue
            if profile.sic_codes and sic_code in profile.sic_codes:
                matched.append(item)

        return CompanySearchResult(
            items=matched,
            total_results=len(matched),
            start_index=start_index,
            items_per_page=items_per_page,
        )

    # -- Company profile --------------------------------------------------

    async def get_company_profile(self, company_number: str) -> CompanyProfile:
        """Get full company profile.

        Args:
            company_number: The Companies House company number (e.g. "09446231").

        Returns:
            CompanyProfile with status, SIC codes, address, dates, etc.
        """
        company_number = _normalise_company_number(company_number)
        data = await self._request("GET", f"/company/{company_number}")
        return CompanyProfile.model_validate(data)

    # -- Officers ---------------------------------------------------------

    async def get_officers(
        self,
        company_number: str,
        *,
        items_per_page: int = 35,
        start_index: int = 0,
        order_by: Optional[str] = None,
    ) -> OfficerList:
        """Get company officers (directors, secretaries, etc.).

        Args:
            company_number: The Companies House company number.
            items_per_page: Results per page.
            start_index: Pagination offset.
            order_by: Optional sort field (e.g. "appointed_on").

        Returns:
            OfficerList with current and resigned officers.
        """
        company_number = _normalise_company_number(company_number)
        data = await self._request(
            "GET",
            f"/company/{company_number}/officers",
            params={
                "items_per_page": items_per_page,
                "start_index": start_index,
                "order_by": order_by,
            },
        )
        return OfficerList.model_validate(data)

    async def get_all_officers(self, company_number: str) -> List[Officer]:
        """Fetch all officers, paginating automatically."""
        all_officers: List[Officer] = []
        start_index = 0
        page_size = 100

        while True:
            result = await self.get_officers(
                company_number, items_per_page=page_size, start_index=start_index
            )
            all_officers.extend(result.items)
            if start_index + len(result.items) >= result.total_results:
                break
            start_index += len(result.items)

        return all_officers

    # -- Filing history ---------------------------------------------------

    async def get_filing_history(
        self,
        company_number: str,
        *,
        items_per_page: int = 25,
        start_index: int = 0,
        category: Optional[str] = None,
    ) -> FilingHistory:
        """Get company filing history.

        Args:
            company_number: The Companies House company number.
            items_per_page: Results per page.
            start_index: Pagination offset.
            category: Optional filter (e.g. "accounts", "confirmation-statement").

        Returns:
            FilingHistory with filed documents.
        """
        company_number = _normalise_company_number(company_number)
        data = await self._request(
            "GET",
            f"/company/{company_number}/filing-history",
            params={
                "items_per_page": items_per_page,
                "start_index": start_index,
                "category": category,
            },
        )
        return FilingHistory.model_validate(data)

    # -- Insolvency -------------------------------------------------------

    async def get_insolvency(self, company_number: str) -> InsolvencyData:
        """Get insolvency data for a company.

        Args:
            company_number: The Companies House company number.

        Returns:
            InsolvencyData with cases, practitioners, and dates.
            Returns empty InsolvencyData if the company has no insolvency history.
        """
        company_number = _normalise_company_number(company_number)

        # Check profile first — avoid 404 on companies without insolvency
        profile = await self.get_company_profile(company_number)
        if not profile.has_insolvency_history:
            return InsolvencyData()

        data = await self._request("GET", f"/company/{company_number}/insolvency")
        return InsolvencyData.model_validate(data)

    # -- Cross-referencing with SRA / FCA ---------------------------------

    async def cross_reference_sra(
        self,
        company_number: str,
        sra_records: List[Dict[str, Any]],
    ) -> Optional[RegulatoryReference]:
        """Match a Companies House company to an SRA record by company number.

        Args:
            company_number: The Companies House company number.
            sra_records: List of SRA records, each expected to have at minimum
                a "company_number" field. May also have "sra_id", "name", "status".

        Returns:
            RegulatoryReference if a match is found, else None.
        """
        company_number = _normalise_company_number(company_number)

        for record in sra_records:
            sra_company_num = _normalise_company_number(
                str(record.get("company_number", ""))
            )
            if sra_company_num == company_number:
                profile = await self.get_company_profile(company_number)
                return RegulatoryReference(
                    company_number=company_number,
                    company_name=profile.company_name,
                    source="sra",
                    reference_number=record.get("sra_id"),
                    status=record.get("status"),
                    match_method="company_number",
                )

        return None

    async def cross_reference_fca(
        self,
        company_number: str,
        fca_records: List[Dict[str, Any]],
    ) -> Optional[RegulatoryReference]:
        """Match a Companies House company to an FCA record by company number.

        Args:
            company_number: The Companies House company number.
            fca_records: List of FCA records, each expected to have at minimum
                a "company_number" field. May also have "frn", "name", "status".

        Returns:
            RegulatoryReference if a match is found, else None.
        """
        company_number = _normalise_company_number(company_number)

        for record in fca_records:
            fca_company_num = _normalise_company_number(
                str(record.get("company_number", ""))
            )
            if fca_company_num == company_number:
                profile = await self.get_company_profile(company_number)
                return RegulatoryReference(
                    company_number=company_number,
                    company_name=profile.company_name,
                    source="fca",
                    reference_number=record.get("frn"),
                    status=record.get("status"),
                    match_method="company_number",
                )

        return None

    async def cross_reference_regulatory(
        self,
        company_number: str,
        *,
        sra_records: Optional[List[Dict[str, Any]]] = None,
        fca_records: Optional[List[Dict[str, Any]]] = None,
    ) -> List[RegulatoryReference]:
        """Check a company against both SRA and FCA records.

        Args:
            company_number: The Companies House company number.
            sra_records: Optional list of SRA records to match against.
            fca_records: Optional list of FCA records to match against.

        Returns:
            List of RegulatoryReference matches (may be empty).
        """
        results: List[RegulatoryReference] = []

        tasks = []
        if sra_records:
            tasks.append(self.cross_reference_sra(company_number, sra_records))
        if fca_records:
            tasks.append(self.cross_reference_fca(company_number, fca_records))

        if tasks:
            matches = await asyncio.gather(*tasks)
            results = [m for m in matches if m is not None]

        return results

    # -- Convenience methods ----------------------------------------------

    async def get_company_summary(self, company_number: str) -> Dict[str, Any]:
        """Fetch profile + officers + recent filings in parallel.

        Returns a dict with keys: "profile", "officers", "recent_filings".
        """
        profile_task = self.get_company_profile(company_number)
        officers_task = self.get_officers(company_number)
        filings_task = self.get_filing_history(company_number, items_per_page=10)

        profile, officers, filings = await asyncio.gather(
            profile_task, officers_task, filings_task
        )

        return {
            "profile": profile,
            "officers": officers,
            "recent_filings": filings,
        }

    async def is_active(self, company_number: str) -> bool:
        """Quick check: is this company active?"""
        profile = await self.get_company_profile(company_number)
        return profile.company_status == "active"

    async def get_active_officers(self, company_number: str) -> List[Officer]:
        """Get only currently-serving officers (no resigned_on date)."""
        officers = await self.get_all_officers(company_number)
        return [o for o in officers if o.resigned_on is None]

    # -- Cache management -------------------------------------------------

    def clear_cache(self) -> None:
        """Clear the entire response cache."""
        self._cache.clear()

    def invalidate_company_cache(self, company_number: str) -> None:
        """Invalidate all cached responses for a specific company."""
        company_number = _normalise_company_number(company_number)
        prefix = f"GET:/company/{company_number}"
        keys_to_remove = [k for k in self._cache._store if k.startswith(prefix)]
        for key in keys_to_remove:
            self._cache.invalidate(key)
