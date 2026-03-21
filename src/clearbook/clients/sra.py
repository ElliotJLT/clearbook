"""SRA (Solicitors Regulation Authority) Data Sharing API client.

Async client for the SRA Data Share API V1, hosted on Azure API Management.
Provides access to the public register of regulated law firms in England & Wales.

API portal: https://sra-prod-apim.developer.azure-api.net
Data docs:  https://www.sra.org.uk/sra/how-we-work/privacy-data-information/data-sharing/

Authentication:
    Requires an Ocp-Apim-Subscription-Key header. Register for free at
    https://sra-prod-apim.developer.azure-api.net/signup, then subscribe to
    "SRA Data Share API Version V1" under Products. Copy the primary or
    secondary key from your Profile page.

Rate limits:
    Not formally documented. The API is built on Azure APIM which defaults to
    throttling at high volumes. This client implements exponential backoff with
    jitter for 429 responses.

Data freshness:
    The SRA updates the dataset every 24 hours. Cache TTL defaults to 24h.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from enum import Enum
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://sra-prod-apim.azure-api.net"
DEFAULT_CACHE_TTL = 86400  # 24 hours — matches SRA update cycle
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds


# ---------------------------------------------------------------------------
# Enums — mirror the SRA data dictionary
# ---------------------------------------------------------------------------


class OfficeType(str, Enum):
    HEAD_OFFICE = "HO"
    BRANCH = "Branch"


class AuthorisationStatus(str, Enum):
    YES = "YES"
    CEASE = "CEASE"
    CONDITION = "CONDITION"
    INTERVENE = "INTERVENE"


class OrganisationType(str, Enum):
    LICENSED_BODY_AUTHORISED = "LicensedBodyAuthorised"
    RECOGNISED_BODY_AUTHORISED = "RecognisedBodyAuthorised"
    RECOGNISED_SOLE_PRACTICE_AUTHORISED = "RecognisedSolePracticeAuthorised"
    LICENSED_BODY_CLOSED = "LicensedBodyClosed"
    RECOGNISED_BODY_CLOSED = "RecognisedBodyClosed"
    RECOGNISED_SOLE_PRACTICE_CLOSED = "RecognisedSolePracticesClosed"


class PracticeArea(str, Enum):
    """SRA-defined work areas. Enum values are the SRA's canonical strings."""
    ACCIDENT_CLAIMS = "Accident claims"
    BANKING_DEBT_FINANCE = "Banking and debt finance"
    CHILDREN = "Children"
    COMMERCIAL_CORPORATE_LISTED = "Commercial/corporate work for listed companies"
    COMMERCIAL_CORPORATE_NONLISTED = "Commercial/corporate work for non-listed companies"
    CONSUMER_PROBLEMS = "Consumer problems"
    CONVEYANCING_COMMERCIAL = "Property - Commercial"
    CONVEYANCING_RESIDENTIAL = "Property - Residential"
    CRIMINAL = "Criminal"
    DISCRIMINATION_CIVIL_LIBERTIES = "Discrimination/civil liberties"
    EDUCATION = "Education"
    EMPLOYMENT = "Employment"
    FAMILY_MATRIMONIAL = "Family/matrimonial"
    HOUSING = "Housing"
    IMMIGRATION = "Immigration"
    INTELLECTUAL_PROPERTY = "Intellectual property"
    MENTAL_HEALTH = "Mental health"
    PERSONAL_INJURY = "Personal injury"
    PLANNING = "Planning"
    PROBATE_TRUSTS_TAX = "Probate/trusts/tax planning"
    PROFESSIONAL_NEGLIGENCE = "Professional negligence"
    SOCIAL_WELFARE = "Social welfare"
    WILLS_INTESTACY_PROBATE = "Wills/intestacy/probate"


class ConstitutionType(str, Enum):
    """Selected constitution types from the SRA data dictionary."""
    ILLP = "ILLP"  # Limited Liability Partnership
    PART = "PART"  # Partnership
    SOLP = "SOLP"  # Sole Practice
    COMP = "COMP"  # Company
    CORP = "CORP"  # Corporation
    UCOP = "UCOP"  # Unincorporated body/co-operative


# ---------------------------------------------------------------------------
# Response models — typed representations of SRA API responses
# ---------------------------------------------------------------------------


class SRAOffice(BaseModel):
    """An office/branch of a regulated firm — matches real API PascalCase."""
    office_id: int = Field(default=0, alias="OfficeId")
    name: str = Field(default="", alias="Name")
    address1: str = Field(default="", alias="Address1")
    address2: str = Field(default="", alias="Address2")
    address3: str = Field(default="", alias="Address3")
    address4: str = Field(default="", alias="Address4")
    postcode: str = Field(default="", alias="Postcode")
    town: str = Field(default="", alias="Town")
    county: str = Field(default="", alias="County")
    country: str = Field(default="", alias="Country")
    phone_number: str = Field(default="", alias="PhoneNumber")
    website: str = Field(default="", alias="Website")
    email: str = Field(default="", alias="Email")
    office_type: str = Field(default="", alias="OfficeType")

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def _coerce_nulls(cls, values: Any) -> Any:
        """The SRA API returns null for missing string fields. Coerce to defaults."""
        if isinstance(values, dict):
            for k, v in values.items():
                if v is None:
                    values[k] = "" if k != "OfficeId" else 0
        return values


class SRAOrganisation(BaseModel):
    """A regulated law firm / organisation — matches real API PascalCase."""
    id: int = Field(default=0, alias="Id")
    sra_number: int = Field(default=0, alias="SraNumber")
    practice_name: str = Field(default="", alias="PracticeName")
    authorisation_type: str = Field(default="", alias="AuthorisationType")
    authorisation_status: str = Field(default="", alias="AuthorisationStatus")
    organisation_type: str = Field(default="", alias="OrganisationType")
    authorisation_date: str = Field(default="", alias="AuthorisationDate")
    authorisation_status_date: str = Field(default="", alias="AuthorisationStatusDate")
    freelance_basis: str = Field(default="", alias="FreelanceBasis")
    regulator: str = Field(default="", alias="Regulator")
    offices: list[SRAOffice] = Field(default_factory=list, alias="Offices")
    trading_names: list[str] = Field(default_factory=list, alias="TradingNames")
    previous_names: list[str] = Field(default_factory=list, alias="PreviousNames")
    work_area: list[str] = Field(default_factory=list, alias="WorkArea")
    websites: list[str] = Field(default_factory=list, alias="Websites")
    reserved_activities: list[str] = Field(default_factory=list, alias="ReservedActivites")
    company_reg_no: str = Field(default="", alias="CompanyRegNo")
    constitution: str = Field(default="", alias="Constitution")
    no_of_offices: int = Field(default=0, alias="NoOfOffices")
    type: str = Field(default="", alias="Type")

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def _coerce_nulls(cls, values: Any) -> Any:
        """The SRA API returns null for missing fields. Coerce to type defaults."""
        if not isinstance(values, dict):
            return values
        _LIST_FIELDS = {"Offices", "TradingNames", "PreviousNames", "WorkArea",
                        "Websites", "ReservedActivites"}
        _INT_FIELDS = {"Id", "SraNumber", "NoOfOffices"}
        for k, v in values.items():
            if v is None:
                if k in _LIST_FIELDS:
                    values[k] = []
                elif k in _INT_FIELDS:
                    values[k] = 0
                else:
                    values[k] = ""
        return values

    @property
    def organisation_sra_number(self) -> str:
        """Backward compat for service layer."""
        return str(self.sra_number)

    @property
    def organisation_name(self) -> str:
        """Backward compat for service layer."""
        return self.practice_name

    @property
    def practice_areas(self) -> list[str]:
        """Backward compat — maps WorkArea to practice_areas."""
        return self.work_area

    @property
    def is_authorised(self) -> bool:
        return self.authorisation_status.upper() in ("AUTHORISED", "YES")

    @property
    def does_conveyancing(self) -> bool:
        conveyancing_areas = {"Property - Residential", "Property - Commercial"}
        return bool(set(self.work_area) & conveyancing_areas)

    @property
    def head_office(self) -> Optional[SRAOffice]:
        for office in self.offices:
            if office.office_type.upper() in ("HO", "HEAD OFFICE"):
                return office
        return self.offices[0] if self.offices else None


class SRASearchResponse(BaseModel):
    """Wrapper for local search results over the cached dataset."""
    count: int = 0
    organisations: list[SRAOrganisation] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class _CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: float) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl

    @property
    def is_expired(self) -> bool:
        return time.monotonic() >= self.expires_at


class TTLCache:
    """Simple in-memory TTL cache. Thread-safe enough for async single-thread."""

    def __init__(self, default_ttl: float = DEFAULT_CACHE_TTL) -> None:
        self._store: dict[str, _CacheEntry] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.is_expired:
            del self._store[key]
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        self._store[key] = _CacheEntry(value, ttl if ttl is not None else self._default_ttl)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def prune(self) -> int:
        """Remove expired entries. Returns count removed."""
        expired = [k for k, v in self._store.items() if v.is_expired]
        for k in expired:
            del self._store[k]
        return len(expired)

    @property
    def size(self) -> int:
        return len(self._store)

    @staticmethod
    def make_key(*parts: str) -> str:
        raw = "|".join(str(p) for p in parts)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SRAClientError(Exception):
    """Base error for SRA client operations."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class SRAAuthenticationError(SRAClientError):
    """Raised when the API key is missing or invalid."""
    pass


class SRARateLimitError(SRAClientError):
    """Raised when rate limited and all retries exhausted."""
    pass


class SRANotFoundError(SRAClientError):
    """Raised when a specific resource is not found."""
    pass


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class SRAClient:
    """Async client for the SRA Data Share API V1.

    The real API has ONE endpoint: /organisation/GetAll which returns all
    ~25,000 organisations in a single call. This client fetches that once,
    caches the full dataset (24hr TTL), and filters locally.

    Usage::

        async with SRAClient(api_key="your-key") as client:
            results = await client.search_conveyancers(postcode="SE15")
            for firm in results:
                print(firm.practice_name, firm.sra_number)
    """

    _GETALL_PATH = "/datashare/api/V1/organisation/GetAll"
    _CACHE_KEY = "sra_all_organisations"

    def __init__(
        self,
        api_key: str = "",
        base_url: str = BASE_URL,
        cache_ttl: float = DEFAULT_CACHE_TTL,
        timeout: float = 120.0,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._cache = TTLCache(default_ttl=cache_ttl)
        self._max_retries = max_retries
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout
        self._owns_client = False
        # Lock to prevent multiple concurrent fetches of the full dataset
        self._fetch_lock: asyncio.Lock | None = None

    async def __aenter__(self) -> SRAClient:
        await self._ensure_client()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {
                "Accept": "application/json",
                "User-Agent": "Settle/1.0 (https://github.com/elliotlittle/settle)",
            }
            if self._api_key:
                headers["Ocp-Apim-Subscription-Key"] = self._api_key
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=httpx.Timeout(self._timeout),
            )
            self._owns_client = True
        return self._client

    async def close(self) -> None:
        if self._client and self._owns_client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # HTTP layer with retry + backoff
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Make an HTTP request with retry, backoff, and error handling."""
        if not self._api_key:
            raise SRAAuthenticationError(
                "SRA API key not configured. Register at "
                "https://sra-prod-apim.developer.azure-api.net/signup and set "
                "SRA_API_KEY environment variable.",
                status_code=401,
            )

        client = await self._ensure_client()
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = await client.request(method, path, params=params)

                if response.status_code == 200:
                    return response.json()

                if response.status_code in (401, 403):
                    raise SRAAuthenticationError(
                        f"SRA API authentication failed (HTTP {response.status_code}). "
                        "Check your Ocp-Apim-Subscription-Key.",
                        status_code=response.status_code,
                    )

                if response.status_code == 404:
                    raise SRANotFoundError(
                        f"Resource not found: {path}",
                        status_code=404,
                    )

                if response.status_code == 429:
                    retry_after = _parse_retry_after(response)
                    if attempt < self._max_retries:
                        delay = retry_after or _backoff_delay(attempt)
                        logger.warning(
                            "SRA rate limited (429). Retrying in %.1fs (attempt %d/%d)",
                            delay, attempt + 1, self._max_retries,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise SRARateLimitError(
                        "SRA rate limit exceeded after all retries.",
                        status_code=429,
                    )

                if response.status_code >= 500:
                    if attempt < self._max_retries:
                        delay = _backoff_delay(attempt)
                        logger.warning(
                            "SRA server error (%d). Retrying in %.1fs (attempt %d/%d)",
                            response.status_code, delay, attempt + 1, self._max_retries,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise SRAClientError(
                        f"SRA server error (HTTP {response.status_code})",
                        status_code=response.status_code,
                    )

                raise SRAClientError(
                    f"Unexpected response from SRA API: HTTP {response.status_code}",
                    status_code=response.status_code,
                )

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                last_error = exc
                if attempt < self._max_retries:
                    delay = _backoff_delay(attempt)
                    logger.warning(
                        "SRA connection error: %s. Retrying in %.1fs (attempt %d/%d)",
                        exc, delay, attempt + 1, self._max_retries,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise SRAClientError(
                    f"Failed to connect to SRA API after {self._max_retries + 1} attempts: {exc}",
                ) from last_error

        raise SRAClientError("Request failed after all retries")

    # ------------------------------------------------------------------
    # Dataset fetching — single call, cached 24h
    # ------------------------------------------------------------------

    async def _get_all_organisations(self) -> list[SRAOrganisation]:
        """Fetch the full SRA dataset via GetAll, with 24hr cache.

        Returns the cached list if available. Otherwise hits the API once
        and parses all ~25,000 organisations into typed models.
        """
        cached = self._cache.get(self._CACHE_KEY)
        if cached is not None:
            return cached

        # Prevent concurrent fetches (e.g. parallel search calls)
        if self._fetch_lock is None:
            self._fetch_lock = asyncio.Lock()

        async with self._fetch_lock:
            # Double-check after acquiring lock
            cached = self._cache.get(self._CACHE_KEY)
            if cached is not None:
                return cached

            logger.info("Fetching full SRA organisation dataset from GetAll...")
            data = await self._request("GET", self._GETALL_PATH)

            # The API returns a JSON array of organisation objects
            if isinstance(data, list):
                raw_list = data
            elif isinstance(data, dict):
                # Some envelope formats: try common keys
                raw_list = (
                    data.get("Organisations")
                    or data.get("organisations")
                    or data.get("Records")
                    or data.get("records")
                    or []
                )
            else:
                raw_list = []

            orgs: list[SRAOrganisation] = []
            for item in raw_list:
                try:
                    orgs.append(SRAOrganisation.model_validate(item))
                except Exception:
                    # Skip malformed records rather than failing the whole load
                    logger.debug("Skipping malformed SRA record: %s", item.get("SraNumber", "?"))
                    continue

            logger.info("Loaded %d SRA organisations into cache", len(orgs))
            self._cache.set(self._CACHE_KEY, orgs)
            return orgs

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def search_firms(
        self,
        *,
        name: str = "",
        postcode: str = "",
        city: str = "",
        practice_area: str = "",
        authorised_only: bool = True,
        max_results: int = 100,
    ) -> list[SRAOrganisation]:
        """Search the cached SRA dataset with local filtering.

        Args:
            name: Search by firm name (case-insensitive substring match).
            postcode: Filter by postcode prefix (e.g. "SE15", "SW1A").
                     Matches any office postcode starting with this prefix.
            city: Filter by city/town (case-insensitive substring match on office town).
            practice_area: Filter by practice area. Accepts shorthand:
                          "conveyancing" -> Property - Residential + Property - Commercial
                          "residential" -> Property - Residential only
                          "commercial" -> Property - Commercial only
                          Or pass the exact SRA WorkArea string.
            authorised_only: Only return currently authorised firms.
            max_results: Maximum results to return (default 100).

        Returns:
            List of SRAOrganisation objects matching all criteria.
        """
        all_orgs = await self._get_all_organisations()
        practice_areas = _resolve_practice_areas(practice_area)

        name_lower = name.strip().lower() if name else ""
        postcode_upper = postcode.strip().upper() if postcode else ""
        city_lower = city.strip().lower() if city else ""

        results: list[SRAOrganisation] = []

        for org in all_orgs:
            # Authorisation filter
            if authorised_only and not org.is_authorised:
                continue

            # Name filter (substring match on practice_name or trading_names)
            if name_lower:
                name_match = name_lower in org.practice_name.lower()
                if not name_match:
                    name_match = any(
                        name_lower in tn.lower() for tn in org.trading_names
                    )
                if not name_match:
                    continue

            # Practice area filter (any overlap between required areas and org's work_area)
            if practice_areas:
                # Case-insensitive comparison for work area matching
                org_areas_lower = {wa.lower() for wa in org.work_area}
                required_lower = {pa.lower() for pa in practice_areas}
                if not org_areas_lower & required_lower:
                    continue

            # Postcode filter (prefix match on any office postcode)
            if postcode_upper:
                postcode_match = False
                for office in org.offices:
                    if office.postcode and office.postcode.upper().startswith(postcode_upper):
                        postcode_match = True
                        break
                if not postcode_match:
                    continue

            # City filter (substring match on any office town)
            if city_lower:
                city_match = False
                for office in org.offices:
                    if office.town and city_lower in office.town.lower():
                        city_match = True
                        break
                if not city_match:
                    continue

            results.append(org)

            if len(results) >= max_results:
                break

        return results

    async def get_organisation(self, sra_number: str) -> SRAOrganisation:
        """Get a single organisation by its SRA number.

        Searches the cached dataset. Falls back to fetching GetAll if not cached.

        Args:
            sra_number: The firm's SRA registration number (e.g. "620472").

        Returns:
            SRAOrganisation with full details.

        Raises:
            SRANotFoundError: If no firm exists with this SRA number.
        """
        sra_number = sra_number.strip()
        if not sra_number:
            raise SRAClientError("SRA number cannot be empty")

        try:
            sra_num_int = int(sra_number)
        except ValueError:
            raise SRAClientError(f"Invalid SRA number: {sra_number}")

        all_orgs = await self._get_all_organisations()
        for org in all_orgs:
            if org.sra_number == sra_num_int:
                return org

        raise SRANotFoundError(
            f"Organisation with SRA number {sra_number} not found",
            status_code=404,
        )

    async def get_firm(self, sra_number: str) -> dict[str, Any]:
        """Get firm details as a dict for the service layer.

        This is the integration point called by SettleService._get_sra_provider().
        Returns a flat dict matching what service.py expects.
        """
        org = await self.get_organisation(sra_number)
        return _organisation_to_service_dict(org)

    async def search_conveyancers(
        self,
        *,
        postcode: str = "",
        city: str = "",
        name: str = "",
        max_results: int = 50,
    ) -> list[SRAOrganisation]:
        """Convenience: search specifically for conveyancing firms.

        Filters to firms with "Property - Residential" or "Property - Commercial"
        work areas.
        """
        return await self.search_firms(
            name=name,
            postcode=postcode,
            city=city,
            practice_area="conveyancing",
            authorised_only=True,
            max_results=max_results,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


# Conveyancing work areas as returned by the real SRA API
_CONVEYANCING_WORK_AREAS = {
    "Property - Residential",
    "Property - Commercial",
}


def _resolve_practice_areas(shorthand: str) -> list[str]:
    """Convert friendly practice area names to SRA canonical WorkArea strings."""
    if not shorthand:
        return []

    mapping: dict[str, list[str]] = {
        "conveyancing": [
            PracticeArea.CONVEYANCING_RESIDENTIAL.value,
            PracticeArea.CONVEYANCING_COMMERCIAL.value,
        ],
        "residential": [PracticeArea.CONVEYANCING_RESIDENTIAL.value],
        "commercial": [PracticeArea.CONVEYANCING_COMMERCIAL.value],
        "property": [
            PracticeArea.CONVEYANCING_RESIDENTIAL.value,
            PracticeArea.CONVEYANCING_COMMERCIAL.value,
        ],
        "family": [PracticeArea.FAMILY_MATRIMONIAL.value],
        "criminal": [PracticeArea.CRIMINAL.value],
        "immigration": [PracticeArea.IMMIGRATION.value],
        "employment": [PracticeArea.EMPLOYMENT.value],
        "personal injury": [PracticeArea.PERSONAL_INJURY.value],
        "probate": [
            PracticeArea.PROBATE_TRUSTS_TAX.value,
            PracticeArea.WILLS_INTESTACY_PROBATE.value,
        ],
        "wills": [PracticeArea.WILLS_INTESTACY_PROBATE.value],
    }

    key = shorthand.strip().lower()
    if key in mapping:
        return mapping[key]

    # If it's already a canonical SRA practice area string, use it directly
    valid_areas = {pa.value for pa in PracticeArea}
    if shorthand in valid_areas:
        return [shorthand]

    logger.warning("Unrecognised practice area shorthand: %r — no filter applied", shorthand)
    return []


def _organisation_to_service_dict(org: SRAOrganisation) -> dict[str, Any]:
    """Convert SRAOrganisation to the flat dict expected by the service layer."""
    ho = org.head_office

    status_map = {
        "AUTHORISED": "authorised",
        "YES": "authorised",
        "CEASE": "revoked",
        "CONDITION": "suspended",
        "INTERVENE": "suspended",
    }

    return {
        "sra_number": str(org.sra_number),
        "name": org.practice_name,
        "status": status_map.get(org.authorisation_status.upper(), org.authorisation_status),
        "organisation_type": org.organisation_type,
        "constitution": org.constitution,
        "company_reg_no": org.company_reg_no,
        "practice_areas": org.work_area,
        "reserved_activities": org.reserved_activities,
        "trading_names": org.trading_names,
        "address": {
            "line1": ho.address1 if ho else "",
            "line2": ho.address2 if ho else "",
            "town": ho.town if ho else "",
            "county": ho.county if ho else "",
            "postcode": ho.postcode if ho else "",
            "country": ho.country if ho else "",
        },
        "phone": ho.phone_number if ho else "",
        "email": ho.email if ho else "",
        "website": ho.website if ho else "",
        "number_of_offices": org.no_of_offices,
        "offices": [
            {
                "office_id": o.office_id,
                "name": o.name,
                "type": o.office_type,
                "postcode": o.postcode,
                "town": o.town,
                "phone": o.phone_number,
                "email": o.email,
            }
            for o in org.offices
        ],
    }


def _backoff_delay(attempt: int) -> float:
    """Exponential backoff with jitter: 1s, 2s, 4s + random jitter."""
    import random
    base = RETRY_BASE_DELAY * (2 ** attempt)
    jitter = random.uniform(0, base * 0.5)
    return base + jitter


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Extract Retry-After header value in seconds, if present."""
    retry_after = response.headers.get("Retry-After")
    if retry_after is None:
        return None
    try:
        return float(retry_after)
    except ValueError:
        return None
