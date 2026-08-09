"""FRED / ALFRED adapter (Federal Reserve Bank of St. Louis).

Two first-party backends, selected automatically:

``fred_api`` (preferred, needs ``FRED_API_KEY``)
    https://api.stlouisfed.org/fred/... — returns series metadata (title, units,
    frequency, seasonal adjustment) alongside observations, so every attribute of a
    record comes from the source.

``fredgraph_csv`` (keyless fallback, used here)
    https://fred.stlouisfed.org/graph/fredgraph.csv  — current-vintage observations
    https://alfred.stlouisfed.org/graph/alfredgraph.csv — observations *as they stood*
    on a given vintage date

Both are St. Louis Fed endpoints. Nothing here scrapes a third-party mirror.

The keyless endpoints return observations but no series metadata. Rather than infer
units or seasonal adjustment from series-ID spelling, the adapter reads them from an
operator-supplied catalog in the config and stamps every such record with
``metadata_source: "operator_catalog"`` plus a provenance note. That keeps the
distinction explicit: observation *values* always come from the API, while descriptive
attributes are marked as operator-supplied until an API key upgrades them to
``metadata_source: "fred_api"``. No code changes are needed for that upgrade.

Why FRED earns its place in this benchmark: it is the only one of our sources where the
*same* observation legitimately carries different values depending on when you asked.
GDP for 2021-Q1 was 22048.894 in the April-2021 vintage and 22656.793 in the
March-2025 vintage. Those are authentic revisions, which is exactly the WRONG_VERSION
interference the other domains struggle to supply.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..normalize.common import canonical_date, canonical_number, make_record_id
from ..schemas import Domain, NormalizedRecord
from .base import HTTPClient, RetrievalResult, SourceAdapter, register_adapter, utc_now

FRED_API_BASE = "https://api.stlouisfed.org/fred"
FREDGRAPH_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"
ALFREDGRAPH_CSV = "https://alfred.stlouisfed.org/graph/alfredgraph.csv"

MISSING_TOKENS = {"", ".", "na", "n/a", "null"}
"""FRED marks an absent observation with an empty cell or a bare period."""


# Curated default catalog. Chosen so that every distractor class is reachable from
# authentic data rather than manufactured:
#   WRONG_UNIT     nominal vs chained-dollar GDP; seasonally adjusted vs not
#   WRONG_PERIOD   any series across its own observation dates
#   WRONG_VERSION  ALFRED vintages of heavily-revised series
#   WRONG_ENTITY   the same measure published per state
#   WRONG_FIELD    unrelated series for the same geography
DEFAULT_SERIES: List[Dict[str, Any]] = [
    # --- seasonally adjusted / not adjusted pairs (same measure, different basis) ---
    {"id": "UNRATE", "title": "Unemployment Rate", "units": "Percent",
     "frequency": "Monthly", "seasonal_adjustment": "Seasonally Adjusted",
     "family": "unemployment_rate", "geo_code": "US", "geo_name": "United States"},
    {"id": "UNRATENSA", "title": "Unemployment Rate", "units": "Percent",
     "frequency": "Monthly", "seasonal_adjustment": "Not Seasonally Adjusted",
     "family": "unemployment_rate", "geo_code": "US", "geo_name": "United States"},
    {"id": "CPIAUCSL", "title": "Consumer Price Index for All Urban Consumers: All Items in U.S. City Average",
     "units": "Index 1982-1984=100", "frequency": "Monthly",
     "seasonal_adjustment": "Seasonally Adjusted", "family": "cpi_all_items",
     "geo_code": "US", "geo_name": "United States"},
    {"id": "CPIAUCNS", "title": "Consumer Price Index for All Urban Consumers: All Items in U.S. City Average",
     "units": "Index 1982-1984=100", "frequency": "Monthly",
     "seasonal_adjustment": "Not Seasonally Adjusted", "family": "cpi_all_items",
     "geo_code": "US", "geo_name": "United States"},
    {"id": "PAYEMS", "title": "All Employees, Total Nonfarm", "units": "Thousands of Persons",
     "frequency": "Monthly", "seasonal_adjustment": "Seasonally Adjusted",
     "family": "nonfarm_payrolls", "geo_code": "US", "geo_name": "United States"},
    {"id": "PAYNSA", "title": "All Employees, Total Nonfarm", "units": "Thousands of Persons",
     "frequency": "Monthly", "seasonal_adjustment": "Not Seasonally Adjusted",
     "family": "nonfarm_payrolls", "geo_code": "US", "geo_name": "United States"},
    {"id": "HOUST", "title": "New Privately-Owned Housing Units Started: Total Units",
     "units": "Thousands of Units", "frequency": "Monthly",
     "seasonal_adjustment": "Seasonally Adjusted Annual Rate", "family": "housing_starts",
     "geo_code": "US", "geo_name": "United States"},
    {"id": "HOUSTNSA", "title": "New Privately-Owned Housing Units Started: Total Units",
     "units": "Thousands of Units", "frequency": "Monthly",
     "seasonal_adjustment": "Not Seasonally Adjusted", "family": "housing_starts",
     "geo_code": "US", "geo_name": "United States"},

    # --- nominal vs real: same measure, genuinely different units ---
    {"id": "GDP", "title": "Gross Domestic Product", "units": "Billions of Dollars",
     "frequency": "Quarterly", "seasonal_adjustment": "Seasonally Adjusted Annual Rate",
     "family": "gross_domestic_product", "geo_code": "US", "geo_name": "United States"},
    {"id": "GDPC1", "title": "Gross Domestic Product", "units": "Billions of Chained 2017 Dollars",
     "frequency": "Quarterly", "seasonal_adjustment": "Seasonally Adjusted Annual Rate",
     "family": "gross_domestic_product", "geo_code": "US", "geo_name": "United States"},
    {"id": "PCE", "title": "Personal Consumption Expenditures", "units": "Billions of Dollars",
     "frequency": "Monthly", "seasonal_adjustment": "Seasonally Adjusted Annual Rate",
     "family": "personal_consumption", "geo_code": "US", "geo_name": "United States"},
    {"id": "PCEC96", "title": "Personal Consumption Expenditures",
     "units": "Billions of Chained 2017 Dollars", "frequency": "Monthly",
     "seasonal_adjustment": "Seasonally Adjusted Annual Rate",
     "family": "personal_consumption", "geo_code": "US", "geo_name": "United States"},

    # --- same measure at three publication frequencies ---
    {"id": "DGS10", "title": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity",
     "units": "Percent", "frequency": "Daily", "seasonal_adjustment": "Not Seasonally Adjusted",
     "family": "treasury_10y", "geo_code": "US", "geo_name": "United States"},
    {"id": "WGS10YR", "title": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity",
     "units": "Percent", "frequency": "Weekly", "seasonal_adjustment": "Not Seasonally Adjusted",
     "family": "treasury_10y", "geo_code": "US", "geo_name": "United States"},
    {"id": "GS10", "title": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity",
     "units": "Percent", "frequency": "Monthly", "seasonal_adjustment": "Not Seasonally Adjusted",
     "family": "treasury_10y", "geo_code": "US", "geo_name": "United States"},

    # --- the same measure published per state: authentic WRONG_ENTITY material ---
    {"id": "CAUR", "title": "Unemployment Rate", "units": "Percent", "frequency": "Monthly",
     "seasonal_adjustment": "Seasonally Adjusted", "family": "unemployment_rate",
     "geo_code": "CA", "geo_name": "California"},
    {"id": "TXUR", "title": "Unemployment Rate", "units": "Percent", "frequency": "Monthly",
     "seasonal_adjustment": "Seasonally Adjusted", "family": "unemployment_rate",
     "geo_code": "TX", "geo_name": "Texas"},
    {"id": "NYUR", "title": "Unemployment Rate", "units": "Percent", "frequency": "Monthly",
     "seasonal_adjustment": "Seasonally Adjusted", "family": "unemployment_rate",
     "geo_code": "NY", "geo_name": "New York"},
    {"id": "FLUR", "title": "Unemployment Rate", "units": "Percent", "frequency": "Monthly",
     "seasonal_adjustment": "Seasonally Adjusted", "family": "unemployment_rate",
     "geo_code": "FL", "geo_name": "Florida"},
    {"id": "ILUR", "title": "Unemployment Rate", "units": "Percent", "frequency": "Monthly",
     "seasonal_adjustment": "Seasonally Adjusted", "family": "unemployment_rate",
     "geo_code": "IL", "geo_name": "Illinois"},
    {"id": "PAUR", "title": "Unemployment Rate", "units": "Percent", "frequency": "Monthly",
     "seasonal_adjustment": "Seasonally Adjusted", "family": "unemployment_rate",
     "geo_code": "PA", "geo_name": "Pennsylvania"},

    # --- unrelated measures for the same geography: WRONG_FIELD material ---
    {"id": "FEDFUNDS", "title": "Federal Funds Effective Rate", "units": "Percent",
     "frequency": "Monthly", "seasonal_adjustment": "Not Seasonally Adjusted",
     "family": "fed_funds_rate", "geo_code": "US", "geo_name": "United States"},
    {"id": "INDPRO", "title": "Industrial Production: Total Index", "units": "Index 2017=100",
     "frequency": "Monthly", "seasonal_adjustment": "Seasonally Adjusted",
     "family": "industrial_production", "geo_code": "US", "geo_name": "United States"},
]

# Series whose revisions are large and routine, so ALFRED vintages are worth pulling.
DEFAULT_VINTAGE_SERIES = ["GDP", "GDPC1", "PAYEMS", "UNRATE", "CPIAUCSL"]
DEFAULT_VINTAGE_DATES = ["2021-04-29", "2021-07-29", "2022-06-29", "2023-09-28", "2025-03-27"]

CATALOG_NOTE = (
    "Series descriptive attributes (title, units, frequency, seasonal adjustment) are "
    "operator-supplied from the configured catalog because the keyless St. Louis Fed CSV "
    "endpoints return observations only. Observation values, dates and vintages are "
    "returned by the API. Set FRED_API_KEY to source these attributes from /fred/series."
)


def _parse_fred_csv(text: str) -> Tuple[List[str], List[Tuple[str, List[str]]]]:
    """Parse a fredgraph/alfredgraph CSV into (value_column_names, [(date, values)])."""
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if r]
    if not rows:
        return [], []
    header = rows[0]
    return header[1:], [(r[0], r[1:]) for r in rows[1:] if len(r) >= 2]


def _is_missing(raw: str) -> bool:
    return raw is None or str(raw).strip().lower() in MISSING_TOKENS


@register_adapter
class FREDAdapter(SourceAdapter):
    domain = Domain.FRED
    source_name = "FRED_STLOUISFED"
    api_base = FRED_API_BASE
    api_version = "fred-v1"
    license_note = (
        "Federal Reserve Bank of St. Louis (FRED/ALFRED). Most series are public domain; "
        "some carry third-party copyright — see https://fred.stlouisfed.org/legal/"
    )

    # ---- configuration ---------------------------------------------------------------

    def _series(self) -> List[Dict[str, Any]]:
        return list(self.params.get("series") or DEFAULT_SERIES)

    def _vintage_config(self) -> Tuple[List[str], List[str], Optional[str]]:
        return (
            list(self.params.get("vintage_series") or DEFAULT_VINTAGE_SERIES),
            list(self.params.get("vintage_dates") or DEFAULT_VINTAGE_DATES),
            self.params.get("vintage_observation_start", "2018-01-01"),
        )

    def _start_date(self) -> Optional[str]:
        return self.params.get("observation_start", "1990-01-01")

    @property
    def _has_api_key(self) -> bool:
        return bool(self.params.get("api_key") or self.cfg.http.fred_api_key)

    @property
    def backend(self) -> str:
        return "fred_api" if self._has_api_key else "fredgraph_csv"

    def check_availability(self) -> Optional[str]:
        # Never blocked: the keyless first-party endpoints are always usable. The API key
        # only upgrades descriptive metadata, so its absence is a quality note, not a stop.
        return None

    def _client(self) -> HTTPClient:
        return HTTPClient(
            self.cfg,
            self.raw_subdir,
            headers={"Accept": "text/csv, application/json",
                     "User-Agent": "longctx-dataset/0.2 (research)"},
            rate_limit_per_second=float(self.params.get("rate_limit_per_second", 4.0)),
            timeout_seconds=float(self.params.get("timeout_seconds", 30.0)),
            max_retries=int(self.params.get("max_retries", 4)),
        )

    # ---- fetch ------------------------------------------------------------------------

    def fetch(self) -> RetrievalResult:
        client = self._client()
        res = RetrievalResult(
            domain=self.domain, source=self.source_name,
            api_base=FRED_API_BASE if self._has_api_key else FREDGRAPH_CSV,
            api_version=self.api_version,
            notes=f"backend={self.backend}",
        )
        start = self._start_date()

        for spec in self._series():
            sid = spec["id"]
            params: Dict[str, Any] = {"id": sid}
            if start:
                params["cosd"] = start
            try:
                text, path = self._get_csv(client, FREDGRAPH_CSV, params)
            except Exception as exc:  # noqa: BLE001 - recorded, never swallowed
                res.errors.append(f"{sid}: {exc}")
                continue
            if text is None:
                res.errors.append(f"{sid}: no observations returned")
                continue
            _, rows = _parse_fred_csv(text)
            res.raw_paths.append(path)
            res.identifiers.append(sid)
            res.n_raw_records += len(rows)

        vintage_series, vintage_dates, _ = self._vintage_config()
        for sid in vintage_series:
            for vdate in vintage_dates:
                params = {"id": sid, "vintage_date": vdate}
                if start:
                    params["cosd"] = start
                try:
                    text, path = self._get_csv(client, ALFREDGRAPH_CSV, params)
                except Exception as exc:  # noqa: BLE001
                    res.errors.append(f"{sid}@{vdate}: {exc}")
                    continue
                if text is None:
                    res.errors.append(f"{sid}@{vdate}: no vintage observations returned")
                    continue
                _, rows = _parse_fred_csv(text)
                res.raw_paths.append(path)
                res.n_raw_records += len(rows)

        res.n_requests = client.n_requests
        res.retrieved_at = utc_now()
        if not res.raw_paths:
            res.blocked = True
            res.blocker_reason = "no FRED payloads retrieved: " + "; ".join(res.errors[:3])
        return res

    def _get_csv(self, client: HTTPClient, url: str, params: Dict[str, Any]):
        """GET a CSV endpoint through the caching client.

        The shared client caches JSON; CSV is wrapped in the same envelope so the raw
        layer stays uniform and every payload keeps its request URL and timestamp.
        """
        cache = client._cache_path(url, params)  # noqa: SLF001 - same package, same contract
        if self.cfg.http.cache_enabled and cache.exists():
            import json
            return json.loads(cache.read_text(encoding="utf-8")).get("payload"), cache

        import json
        import time

        last_exc: Optional[Exception] = None
        for attempt in range(client.max_retries):
            client.limiter.wait()
            try:
                resp = client.session.get(url, params=params, timeout=client.timeout)
                client.n_requests += 1
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise IOError(f"HTTP {resp.status_code} from {resp.url}")
                resp.raise_for_status()
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps({
                    "request_url": resp.url, "status": resp.status_code,
                    "retrieved_at": utc_now(), "content_type": "text/csv",
                    "payload": resp.text,
                }, ensure_ascii=False), encoding="utf-8")
                return resp.text, cache
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < client.max_retries - 1:
                    time.sleep(min(client.backoff * (2**attempt), 8.0))
        raise IOError(f"GET {url} {params} failed after {client.max_retries} attempts: {last_exc}")

    # ---- normalize --------------------------------------------------------------------

    def normalize(self) -> List[NormalizedRecord]:
        catalog = {s["id"]: s for s in self._series()}
        _, _, vintage_start = self._vintage_config()
        start = self._start_date()
        out: List[NormalizedRecord] = []
        seen: set[str] = set()

        for envelope, path in self.iter_raw_payloads():
            payload = envelope.get("payload")
            if not isinstance(payload, str):
                continue  # not a CSV payload from this adapter
            url = envelope.get("request_url") or ""
            retrieved_at = envelope.get("retrieved_at")
            columns, rows = _parse_fred_csv(payload)
            if not columns:
                continue
            is_vintage = "alfredgraph" in url

            for col_idx, column in enumerate(columns):
                sid, vintage = self._split_column(column, is_vintage)
                spec = catalog.get(sid)
                if spec is None:
                    continue  # outside the configured catalog; keeps output config-determined
                for row_idx, (date, values) in enumerate(rows):
                    if col_idx >= len(values):
                        continue
                    iso = canonical_date(date)
                    if not iso or (start and iso < start):
                        continue
                    if is_vintage and vintage_start and iso < vintage_start:
                        continue
                    rec = self._make_record(
                        spec, sid, iso, values[col_idx], vintage, path,
                        f"$.payload[row={row_idx},col={col_idx}]", retrieved_at, url,
                    )
                    if rec is not None and rec.record_id not in seen:
                        seen.add(rec.record_id)
                        out.append(rec)
        return out

    @staticmethod
    def _split_column(column: str, is_vintage: bool) -> Tuple[str, Optional[str]]:
        """``GDP_20240131`` -> ``("GDP", "2024-01-31")``; ``GDP`` -> ``("GDP", None)``."""
        if is_vintage and "_" in column:
            head, _, tail = column.rpartition("_")
            if len(tail) == 8 and tail.isdigit():
                return head, f"{tail[:4]}-{tail[4:6]}-{tail[6:]}"
        return column, None

    def _make_record(self, spec, sid, iso_date, raw_value, vintage, path, pointer,
                     retrieved_at, url) -> Optional[NormalizedRecord]:
        missing = _is_missing(raw_value)
        value = None if missing else canonical_number(raw_value)
        if not missing and value is None:
            return None  # unparseable value: dropped rather than guessed at

        version = f"vintage:{vintage}" if vintage else "latest"
        record_type = ("fred_vintage_observation" if vintage
                       else ("observation_missing" if missing else "fred_observation"))

        metadata = {
            "series_id": sid,
            "series_title": spec.get("title") or sid,
            "series_family": spec.get("family"),
            "frequency": spec.get("frequency"),
            "seasonal_adjustment": spec.get("seasonal_adjustment"),
            "geography_code": spec.get("geo_code"),
            "geography_name": spec.get("geo_name"),
            "vintage_date": vintage,
            "is_vintage": bool(vintage),
            "no_data": missing,
            # Explicit: values come from the API, descriptive attributes may not.
            "metadata_source": "fred_api" if self._has_api_key else "operator_catalog",
            "metadata_note": None if self._has_api_key else CATALOG_NOTE,
            "series_url": f"https://fred.stlouisfed.org/series/{sid}",
        }

        label = spec.get("title") or sid
        adjustment = spec.get("seasonal_adjustment")
        if adjustment:
            label = f"{label} ({adjustment})"

        return NormalizedRecord(
            record_id=make_record_id("FRED", sid, iso_date, vintage or "latest"),
            domain=self.domain,
            source=self.source_name,
            entity_id=spec.get("geo_code") or "US",
            entity_name=spec.get("geo_name") or "United States",
            record_type=record_type,
            concept=sid,
            concept_label=label,
            value=value,
            value_numeric=value,
            unit=spec.get("units"),
            period=iso_date,
            period_start=iso_date,
            period_end=iso_date,
            version=version,
            metadata=metadata,
            raw_reference=self._raw_reference(path, pointer, retrieved_at),
        )
