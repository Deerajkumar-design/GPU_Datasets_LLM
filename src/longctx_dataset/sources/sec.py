"""SEC EDGAR XBRL "company facts" adapter.

API: https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json

Compliance notes (these are not optional):

* SEC requires a descriptive ``User-Agent`` carrying a **real, reachable** contact
  address. This adapter never invents one. If ``SEC_USER_AGENT`` is neither in the
  environment nor in the config, :meth:`check_availability` blocks the adapter and the
  pipeline records an explicit blocker instead of producing data.
* Requests are rate limited (default 8/s, under SEC's published 10/s ceiling).

Same-domain interference is exceptionally rich here: one company reports the same
concept across fiscal years, quarters, units, and *restated* values that arrive in
later filings, so the identical tag+period can legitimately appear with two different
accession numbers. Those are real WRONG_VERSION distractors, not synthetic ones.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ..normalize.common import canonical_number, make_record_id
from ..schemas import Domain, NormalizedRecord
from .base import HTTPClient, RetrievalResult, SourceAdapter, SourceBlocked, register_adapter, utc_now

API_BASE = "https://data.sec.gov/api/xbrl"

# CIK -> display name. Kept explicit so a run is reproducible without a ticker lookup.
DEFAULT_COMPANIES = {
    "0000320193": "Apple Inc.",
    "0000789019": "Microsoft Corporation",
    "0001018724": "Amazon.com, Inc.",
    "0000021344": "The Coca-Cola Company",
    "0000104169": "Walmart Inc.",
    "0000200406": "Johnson & Johnson",
    "0000078003": "Pfizer Inc.",
    "0000019617": "JPMorgan Chase & Co.",
}

# Restricting to a curated concept set keeps the pool dense in *competing* facts
# rather than sparse across thousands of rarely-used tags.
DEFAULT_CONCEPTS = [
    "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
    "CostOfRevenue", "CostOfGoodsAndServicesSold", "GrossProfit",
    "OperatingIncomeLoss", "OperatingExpenses", "ResearchAndDevelopmentExpense",
    "SellingGeneralAndAdministrativeExpense", "NetIncomeLoss",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    "IncomeTaxExpenseBenefit", "EarningsPerShareBasic", "EarningsPerShareDiluted",
    "Assets", "AssetsCurrent", "Liabilities", "LiabilitiesCurrent",
    "StockholdersEquity", "CashAndCashEquivalentsAtCarryingValue",
    "InventoryNet", "AccountsReceivableNetCurrent", "AccountsPayableCurrent",
    "LongTermDebtNoncurrent", "PropertyPlantAndEquipmentNet",
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInInvestingActivities",
    "NetCashProvidedByUsedInFinancingActivities",
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "CommonStockSharesOutstanding", "WeightedAverageNumberOfSharesOutstandingBasic",
    "WeightedAverageNumberOfDilutedSharesOutstanding",
]

_FRAME_RE = re.compile(r"^CY(\d{4})(Q\d)?(I)?$")


@register_adapter
class SECAdapter(SourceAdapter):
    domain = Domain.SEC
    source_name = "SEC_EDGAR_XBRL_COMPANYFACTS"
    api_base = API_BASE
    api_version = "xbrl-companyfacts-v1"
    license_note = "US SEC EDGAR, public domain"

    # ---- availability ---------------------------------------------------------------

    def check_availability(self) -> Optional[str]:
        ua = self.cfg.http.sec_user_agent
        if not ua or "@" not in ua:
            return (
                "SEC_USER_AGENT is not configured with a real contact email. SEC requires a "
                "descriptive User-Agent containing a reachable address; this adapter will not "
                "fabricate one. Set SEC_USER_AGENT='Your Org your.email@domain' and re-run "
                "`fetch --domain SEC`."
            )
        if "example.com" in ua.lower() or "your.email" in ua.lower():
            return (
                f"SEC_USER_AGENT looks like a placeholder ({ua!r}). SEC requires a real contact "
                "address; refusing to send a fake one."
            )
        return None

    def _client(self) -> HTTPClient:
        blocker = self.check_availability()
        if blocker:
            raise SourceBlocked(self.domain.value, blocker)
        return HTTPClient(
            self.cfg,
            self.raw_subdir,
            headers={
                "User-Agent": self.cfg.http.sec_user_agent or "",
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
                "Host": "data.sec.gov",
            },
            rate_limit_per_second=self.cfg.http.sec_rate_limit_per_second,
        )

    def _companies(self) -> Dict[str, str]:
        return dict(self.params.get("companies") or DEFAULT_COMPANIES)

    def _concepts(self) -> List[str]:
        return list(self.params.get("concepts") or DEFAULT_CONCEPTS)

    # ---- fetch ----------------------------------------------------------------------

    def fetch(self) -> RetrievalResult:
        res = RetrievalResult(
            domain=self.domain, source=self.source_name, api_base=API_BASE, api_version=self.api_version
        )
        blocker = self.check_availability()
        if blocker:
            res.blocked = True
            res.blocker_reason = blocker
            res.errors.append(blocker)
            return res

        client = self._client()
        for cik in self._companies():
            cik10 = str(cik).zfill(10)
            url = f"{API_BASE}/companyfacts/CIK{cik10}.json"
            try:
                payload, path = client.get_json(url, None, allow_404=True)
            except Exception as exc:  # noqa: BLE001
                res.errors.append(f"CIK{cik10}: {exc}")
                continue
            if payload is None:
                res.errors.append(f"CIK{cik10}: 404 from companyfacts")
                continue
            res.raw_paths.append(path)
            res.identifiers.append(cik10)
            res.n_raw_records += sum(
                len(u)
                for tax in (payload.get("facts") or {}).values()
                for tag in tax.values()
                for u in (tag.get("units") or {}).values()
            )

        res.n_requests = client.n_requests
        res.retrieved_at = utc_now()
        if not res.raw_paths:
            res.blocked = True
            res.blocker_reason = "no SEC companyfacts payloads retrieved: " + "; ".join(res.errors[:3])
        return res

    # ---- normalize ------------------------------------------------------------------

    @staticmethod
    def _period_label(fact: Dict[str, Any]) -> str:
        """Canonical, human-meaningful period for a fact.

        SEC's own ``frame`` (``CY2023``, ``CY2023Q2``, ``CY2023Q4I``) is preferred because
        it is calendar-aligned and unique per company/concept/unit -- exactly the property
        a gold answer needs. Facts without a frame fall back to their raw date span; they
        remain useful as authentic WRONG_PERIOD / WRONG_VERSION distractors.
        """
        frame = fact.get("frame")
        if frame:
            return str(frame)
        start, end = fact.get("start"), fact.get("end")
        return f"{start}..{end}" if start else f"AS_OF_{end}"

    @staticmethod
    def _period_kind(fact: Dict[str, Any]) -> str:
        frame = fact.get("frame") or ""
        m = _FRAME_RE.match(frame)
        if m:
            if m.group(3):
                return "instant"
            return "quarterly" if m.group(2) else "annual"
        if not fact.get("start"):
            return "instant"
        return "duration"

    def normalize(self) -> List[NormalizedRecord]:
        wanted = set(self._concepts())
        companies = self._companies()
        out: List[NormalizedRecord] = []
        seen: set[str] = set()

        for envelope, path in self.iter_raw_payloads():
            payload = envelope.get("payload") or {}
            if "facts" not in payload:
                continue
            retrieved_at = envelope.get("retrieved_at")
            cik = str(payload.get("cik", "")).zfill(10)
            entity_name = payload.get("entityName") or companies.get(cik, cik)

            for taxonomy, tags in (payload.get("facts") or {}).items():
                for tag, tagdata in tags.items():
                    if wanted and tag not in wanted:
                        continue
                    label = (tagdata or {}).get("label") or tag
                    for unit, facts in ((tagdata or {}).get("units") or {}).items():
                        for i, fact in enumerate(facts or []):
                            rec = self._normalize_fact(
                                fact, cik, entity_name, taxonomy, tag, label, unit,
                                path, f"$.facts.{taxonomy}.{tag}.units.{unit}[{i}]", retrieved_at,
                            )
                            if rec is not None and rec.record_id not in seen:
                                seen.add(rec.record_id)
                                out.append(rec)
        return out

    def _normalize_fact(
        self, fact, cik, entity_name, taxonomy, tag, label, unit, path, pointer, retrieved_at
    ) -> Optional[NormalizedRecord]:
        val = canonical_number(fact.get("val"))
        if val is None or not fact.get("end"):
            return None  # a fact without a usable value or period cannot be re-verified
        concept = f"{taxonomy}:{tag}"
        period = self._period_label(fact)
        accn = fact.get("accn")
        form = fact.get("form")

        return NormalizedRecord(
            record_id=make_record_id("SEC", cik, tag, unit, period, accn),
            domain=self.domain,
            source=self.source_name,
            entity_id=cik,
            entity_name=entity_name,
            record_type="xbrl_fact",
            concept=concept,
            concept_label=label,
            value=val,
            value_numeric=val,
            unit=unit,
            period=period,
            period_start=fact.get("start"),
            period_end=fact.get("end"),
            version=f"{form}|{accn}" if accn else form,
            metadata={
                "cik": cik,
                "taxonomy": taxonomy,
                "tag": tag,
                "form": form,
                "accn": accn,
                "fy": fact.get("fy"),
                "fp": fact.get("fp"),
                "filed": fact.get("filed"),
                "frame": fact.get("frame"),
                "has_frame": bool(fact.get("frame")),
                "period_kind": self._period_kind(fact),
                "is_amendment": bool(form and form.endswith("/A")),
                "filing_url": (
                    f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"
                    if accn else None
                ),
            },
            raw_reference=self._raw_reference(path, pointer, retrieved_at),
        )
