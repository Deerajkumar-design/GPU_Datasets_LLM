"""World Bank Indicators API adapter.

API: https://api.worldbank.org/v2/country/{iso3}/indicator/{indicator}?format=json
No credentials required. Data are CC-BY-4.0.

Same-domain interference here is natural: the same indicator across countries and
years, plus neighbouring indicators with confusingly similar names and different units
(current US$ vs constant 2015 US$ vs per-capita vs % of GDP).

Observations the API returns with a ``null`` value are preserved as
``record_type='observation_missing'``. They are never rendered into a context, but they
are the *authentic* basis for unanswerable questions: the primary source genuinely has
no value for that country-year.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ..normalize.common import canonical_number, make_record_id
from ..schemas import Domain, NormalizedRecord
from .base import HTTPClient, RetrievalResult, SourceAdapter, register_adapter, utc_now

API_BASE = "https://api.worldbank.org/v2"

DEFAULT_INDICATORS = [
    "NY.GDP.MKTP.CD",       # GDP (current US$)
    "NY.GDP.MKTP.KD",       # GDP (constant 2015 US$)
    "NY.GDP.PCAP.CD",       # GDP per capita (current US$)
    "NY.GDP.MKTP.KD.ZG",    # GDP growth (annual %)
    "SP.POP.TOTL",          # Population, total
    "SP.POP.GROW",          # Population growth (annual %)
    "FP.CPI.TOTL.ZG",       # Inflation, consumer prices (annual %)
    "NE.EXP.GNFS.ZS",       # Exports of goods and services (% of GDP)
    "NE.IMP.GNFS.ZS",       # Imports of goods and services (% of GDP)
    "SL.UEM.TOTL.ZS",       # Unemployment, total (% of labor force, modeled ILO)
    "SP.DYN.LE00.IN",       # Life expectancy at birth, total (years)
    "SE.XPD.TOTL.GD.ZS",    # Government expenditure on education (% of GDP)
    "EN.GHG.CO2.MT.CE.AR5",  # Carbon dioxide (CO2) emissions (Mt CO2e)
    "SH.XPD.CHEX.GD.ZS",    # Current health expenditure (% of GDP)
    "AG.LND.FRST.ZS",       # Forest area (% of land area)
]

DEFAULT_COUNTRIES = [
    "USA", "CHN", "JPN", "DEU", "IND", "GBR", "FRA", "BRA", "ITA", "CAN",
    "KOR", "MEX", "ESP", "IDN", "TUR", "NLD", "SAU", "CHE", "POL", "SWE",
]

_UNIT_IN_NAME = re.compile(r"\(([^)]+)\)\s*$")


def _unit_from_indicator_name(name: str) -> Optional[str]:
    """World Bank encodes the unit in the trailing parenthetical of the indicator name."""
    m = _UNIT_IN_NAME.search(name or "")
    return m.group(1).strip() if m else None


@register_adapter
class WorldBankAdapter(SourceAdapter):
    domain = Domain.WORLD_BANK
    source_name = "WORLD_BANK_INDICATORS_V2"
    api_base = API_BASE
    api_version = "v2"
    license_note = "World Bank Open Data, CC BY-4.0"

    def _client(self) -> HTTPClient:
        # The World Bank endpoint throttles aggressively and responds by hanging rather
        # than returning 429, so this adapter paces itself well below the shared default.
        rate = float(self.params.get("rate_limit_per_second", 2.0))
        return HTTPClient(
            self.cfg,
            self.raw_subdir,
            headers={"Accept": "application/json", "User-Agent": "longctx-dataset/0.1 (research)"},
            rate_limit_per_second=rate,
            # Healthy responses arrive in ~0.1s; anything slower is the endpoint's known
            # slow path, so failing fast and retrying beats waiting out a long timeout.
            timeout_seconds=float(self.params.get("timeout_seconds", 12.0)),
            # The endpoint intermittently returns a fast HTTP 502 that succeeds on an
            # immediate retry, so this adapter retries often and quickly rather than
            # backing off into minutes.
            max_retries=int(self.params.get("max_retries", 10)),
            backoff_seconds=float(self.params.get("backoff_seconds", 0.4)),
        )

    def _config(self) -> Dict[str, Any]:
        return {
            "indicators": self.params.get("indicators", DEFAULT_INDICATORS),
            "countries": self.params.get("countries", DEFAULT_COUNTRIES),
            "date_range": self.params.get("date_range", "1990:2024"),
            # The upstream `date=YYYY:YYYY` filter has been observed returning HTTP 502
            # while the unfiltered endpoint serves fine, so the year window is applied
            # client-side in normalize() by default. Set use_date_param: true to push it
            # back to the server if the endpoint recovers.
            "use_date_param": bool(self.params.get("use_date_param", False)),
            "per_page": int(self.params.get("per_page", 500)),
            # Long multi-country URLs are the trigger for the endpoint's slow path, so
            # countries are requested in batches rather than all at once.
            # api.worldbank.org reliably serves small result sets and hangs on large
            # ones (observed: 1 country x 66 years = fine; 5 countries = timeout), so
            # the default is one country per request.
            "country_batch_size": int(self.params.get("country_batch_size", 1)),
        }

    def fetch(self) -> RetrievalResult:
        conf = self._config()
        client = self._client()
        res = RetrievalResult(
            domain=self.domain, source=self.source_name, api_base=API_BASE, api_version="v2"
        )
        batch = max(1, conf["country_batch_size"])
        all_countries = conf["countries"]
        batches = [all_countries[i: i + batch] for i in range(0, len(all_countries), batch)]

        for ind in conf["indicators"]:
            got_any = False
            for group in batches:
                url = f"{API_BASE}/country/{';'.join(group)}/indicator/{ind}"
                params = {"format": "json", "per_page": conf["per_page"]}
                if conf["use_date_param"]:
                    params["date"] = conf["date_range"]
                try:
                    payload, path = client.get_json(url, params)
                except Exception as exc:  # noqa: BLE001 - recorded, never swallowed
                    res.errors.append(f"{ind} [{group[0]}..{group[-1]}]: {exc}")
                    continue
                if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
                    res.errors.append(f"{ind} [{group[0]}..{group[-1]}]: unexpected payload shape")
                    continue
                got_any = True
                res.raw_paths.append(path)
                res.n_raw_records += len(payload[1])

                # World Bank paginates; follow remaining pages so year coverage is complete.
                pages = int((payload[0] or {}).get("pages", 1) or 1)
                for page in range(2, pages + 1):
                    try:
                        p2, path2 = client.get_json(url, {**params, "page": page})
                    except Exception as exc:  # noqa: BLE001
                        res.errors.append(f"{ind} [{group[0]}..{group[-1]}] page {page}: {exc}")
                        break
                    if isinstance(p2, list) and len(p2) > 1 and p2[1]:
                        res.raw_paths.append(path2)
                        res.n_raw_records += len(p2[1])
            if got_any:
                res.identifiers.append(ind)

        res.n_requests = client.n_requests
        res.retrieved_at = utc_now()
        if not res.raw_paths:
            res.blocked = True
            res.blocker_reason = "no World Bank payloads retrieved: " + "; ".join(res.errors[:3])
        return res

    @staticmethod
    def _parse_range(date_range: Optional[str]) -> Optional[tuple[int, int]]:
        if not date_range or ":" not in str(date_range):
            return None
        lo, hi = str(date_range).split(":", 1)
        try:
            return int(lo), int(hi)
        except ValueError:
            return None

    def normalize(self) -> List[NormalizedRecord]:
        out: List[NormalizedRecord] = []
        seen: set[str] = set()
        conf = self._config()
        window = self._parse_range(conf["date_range"])
        # The raw cache may hold payloads from an earlier run with a wider scope. Filter
        # to the configured indicators and countries so the normalized layer is a pure
        # function of (raw cache + config) and the dataset stays reproducible.
        want_ind = set(conf["indicators"])
        want_ctry = set(conf["countries"])
        for envelope, path in self.iter_raw_payloads():
            payload = envelope.get("payload")
            if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
                continue
            retrieved_at = envelope.get("retrieved_at")
            for idx, obs in enumerate(payload[1]):
                rec = self._normalize_obs(obs, path, idx, retrieved_at)
                if rec is not None and (rec.concept not in want_ind or rec.entity_id not in want_ctry):
                    continue
                if rec is not None and window is not None and rec.period:
                    try:
                        if not (window[0] <= int(rec.period) <= window[1]):
                            continue
                    except ValueError:
                        pass
                if rec is not None and rec.record_id not in seen:
                    seen.add(rec.record_id)
                    out.append(rec)
        return out

    def _normalize_obs(self, obs: Dict[str, Any], path, idx: int, retrieved_at) -> Optional[NormalizedRecord]:
        if not isinstance(obs, dict):
            return None
        ind = obs.get("indicator") or {}
        ctry = obs.get("country") or {}
        ind_id, ind_name = ind.get("id"), ind.get("value")
        iso3 = obs.get("countryiso3code") or ctry.get("id")
        year = obs.get("date")
        if not (ind_id and iso3 and year):
            return None  # malformed row -- skipped, never guessed at

        value = canonical_number(obs.get("value"))
        missing = obs.get("value") is None
        unit = obs.get("unit") or _unit_from_indicator_name(ind_name or "") or None

        return NormalizedRecord(
            record_id=make_record_id("WB", iso3, ind_id, year),
            domain=self.domain,
            source=self.source_name,
            entity_id=iso3,
            entity_name=ctry.get("value") or iso3,
            record_type="observation_missing" if missing else "indicator_observation",
            concept=ind_id,
            concept_label=ind_name or ind_id,
            value=None if missing else value,
            value_numeric=None if missing else value,
            unit=unit,
            period=str(year),
            period_start=f"{year}-01-01",
            period_end=f"{year}-12-31",
            version=None,
            metadata={
                "country_iso2": ctry.get("id"),
                "indicator_id": ind_id,
                "indicator_name": ind_name,
                "obs_status": obs.get("obs_status") or None,
                "decimal": obs.get("decimal"),
                "no_data": missing,
                "aggregation_level": "country",
            },
            raw_reference=self._raw_reference(path, f"$[1][{idx}]", retrieved_at),
        )
