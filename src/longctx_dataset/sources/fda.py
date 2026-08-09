"""openFDA Drugs@FDA adapter.

API: https://api.fda.gov/drug/drugsfda.json  (no key required; a key raises rate limits)

Drugs@FDA is the structured, authoritative record of FDA drug approvals. Each
application carries products (brand name, active ingredients + strengths, dosage form,
route, marketing status) and submissions (original vs supplement, with status dates).

This is a natural interference generator: the same active ingredient appears under
dozens of application numbers from different manufacturers, at different strengths, in
different dosage forms and routes. Nothing has to be synthesised.

One record is emitted per *attribute* of a product rather than per product, so that a
question can bind to an exact field (route vs dosage form vs strength) and so that a
distractor can differ from the target in exactly one dimension.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..normalize.common import canonical_date, canonical_number, make_record_id, parse_fda_strength
from ..schemas import Domain, NormalizedRecord
from .base import HTTPClient, RetrievalResult, SourceAdapter, register_adapter, utc_now

API_BASE = "https://api.fda.gov/drug"

DEFAULT_INGREDIENTS = [
    "METFORMIN HYDROCHLORIDE", "ATORVASTATIN CALCIUM", "LISINOPRIL", "AMLODIPINE BESYLATE",
    "LEVOTHYROXINE SODIUM", "OMEPRAZOLE", "SERTRALINE HYDROCHLORIDE", "GABAPENTIN",
    "IBUPROFEN", "AMOXICILLIN", "PREDNISONE", "WARFARIN SODIUM",
    "MONTELUKAST SODIUM", "LOSARTAN POTASSIUM", "CIPROFLOXACIN HYDROCHLORIDE",
]

# Product-level attributes promoted to their own records.
PRODUCT_FIELDS = {
    "product.brand_name": ("Brand name", "brand_name"),
    "product.dosage_form": ("Dosage form", "dosage_form"),
    "product.route": ("Route of administration", "route"),
    "product.marketing_status": ("Marketing status", "marketing_status"),
    "product.reference_drug": ("Reference listed drug", "reference_drug"),
    "product.reference_standard": ("Reference standard", "reference_standard"),
}


@register_adapter
class FDAAdapter(SourceAdapter):
    domain = Domain.FDA
    source_name = "OPENFDA_DRUGSFDA"
    api_base = API_BASE
    api_version = "openfda-drugsfda"
    license_note = "openFDA (public domain); results are unvalidated per openFDA terms."

    def _client(self) -> HTTPClient:
        return HTTPClient(
            self.cfg,
            self.raw_subdir,
            headers={"Accept": "application/json", "User-Agent": "longctx-dataset/0.1 (research)"},
            rate_limit_per_second=self.cfg.http.default_rate_limit_per_second,
        )

    def _ingredients(self) -> List[str]:
        return list(self.params.get("ingredients") or DEFAULT_INGREDIENTS)

    def fetch(self) -> RetrievalResult:
        client = self._client()
        res = RetrievalResult(
            domain=self.domain, source=self.source_name, api_base=API_BASE, api_version=self.api_version
        )
        limit = int(self.params.get("limit_per_ingredient", 100))
        api_key = self.cfg.http.openfda_api_key

        for ingredient in self._ingredients():
            search = f'products.active_ingredients.name:"{ingredient}"'
            params: Dict[str, Any] = {"search": search, "limit": limit}
            if api_key:
                params["api_key"] = api_key
            try:
                payload, path = client.get_json(f"{API_BASE}/drugsfda.json", params, allow_404=True)
            except Exception as exc:  # noqa: BLE001
                res.errors.append(f"{ingredient}: {exc}")
                continue
            if payload is None:
                # openFDA returns 404 for a zero-result search; that is information, not failure.
                res.errors.append(f"{ingredient}: no matching applications (HTTP 404)")
                continue
            results = payload.get("results") or []
            res.raw_paths.append(path)
            res.identifiers.append(ingredient)
            res.n_raw_records += len(results)

        res.n_requests = client.n_requests
        res.retrieved_at = utc_now()
        if not res.raw_paths:
            res.blocked = True
            res.blocker_reason = "no openFDA payloads retrieved: " + "; ".join(res.errors[:3])
        return res

    # ---- normalize ------------------------------------------------------------------

    def normalize(self) -> List[NormalizedRecord]:
        out: List[NormalizedRecord] = []
        seen: set[str] = set()
        for envelope, path in self.iter_raw_payloads():
            payload = envelope.get("payload") or {}
            results = payload.get("results")
            if not isinstance(results, list):
                continue
            retrieved_at = envelope.get("retrieved_at")
            for ai, app in enumerate(results):
                if not isinstance(app, dict):
                    continue
                for rec in self._normalize_application(app, path, ai, retrieved_at):
                    if rec.record_id not in seen:
                        seen.add(rec.record_id)
                        out.append(rec)
        return out

    def _normalize_application(self, app, path, ai, retrieved_at) -> List[NormalizedRecord]:
        appno = app.get("application_number")
        sponsor = app.get("sponsor_name") or "UNKNOWN SPONSOR"
        if not appno:
            return []
        recs: List[NormalizedRecord] = []

        for pi, product in enumerate(app.get("products") or []):
            if not isinstance(product, dict):
                continue
            prodno = product.get("product_number") or str(pi)
            entity_id = f"{appno}/{prodno}"
            brand = product.get("brand_name") or "(no brand name)"
            ingredients = product.get("active_ingredients") or []
            ing_names = [i.get("name") for i in ingredients if isinstance(i, dict) and i.get("name")]
            entity_name = f"{brand} ({appno}, product {prodno})"
            base_meta = {
                "application_number": appno,
                "product_number": prodno,
                "sponsor_name": sponsor,
                "brand_name": brand,
                "active_ingredients": ing_names,
                "dosage_form": product.get("dosage_form"),
                "route": product.get("route"),
                "marketing_status": product.get("marketing_status"),
                "application_type": appno[:4].rstrip("0123456789") or None,
            }
            ptr_base = f"$.results[{ai}].products[{pi}]"

            for concept, (label, key) in PRODUCT_FIELDS.items():
                value = product.get(key)
                if value in (None, ""):
                    continue
                recs.append(
                    NormalizedRecord(
                        record_id=make_record_id("FDA", appno, prodno, concept),
                        domain=self.domain, source=self.source_name,
                        entity_id=entity_id, entity_name=entity_name,
                        record_type="drug_product_attribute",
                        concept=concept, concept_label=label,
                        value=str(value), value_numeric=None, unit=None,
                        period=None, version=None,
                        metadata={**base_meta, "field": key},
                        raw_reference=self._raw_reference(path, f"{ptr_base}.{key}", retrieved_at),
                    )
                )

            for ii, ing in enumerate(ingredients):
                if not isinstance(ing, dict):
                    continue
                strength = ing.get("strength")
                parsed = parse_fda_strength(strength or "")
                recs.append(
                    NormalizedRecord(
                        record_id=make_record_id("FDA", appno, prodno, "strength", ing.get("name"), ii),
                        domain=self.domain, source=self.source_name,
                        entity_id=entity_id, entity_name=entity_name,
                        record_type="drug_product_strength",
                        concept="product.active_ingredient_strength",
                        concept_label=f"Strength of {ing.get('name')}",
                        value=strength,
                        value_numeric=canonical_number(parsed["magnitude"]),
                        unit=parsed["strength_unit"],
                        period=None, version=None,
                        metadata={
                            **base_meta,
                            "ingredient_name": ing.get("name"),
                            "ingredient_index": ii,
                            "strength_raw": strength,
                        },
                        raw_reference=self._raw_reference(
                            path, f"{ptr_base}.active_ingredients[{ii}].strength", retrieved_at
                        ),
                    )
                )

        # Submissions carry the original-vs-supplement axis: authentic WRONG_VERSION material.
        for si, sub in enumerate(app.get("submissions") or []):
            if not isinstance(sub, dict):
                continue
            date = canonical_date(sub.get("submission_status_date"))
            subtype = sub.get("submission_type")
            subno = sub.get("submission_number")
            if not (date and subtype):
                continue
            recs.append(
                NormalizedRecord(
                    record_id=make_record_id("FDA", appno, "submission", subtype, subno),
                    domain=self.domain, source=self.source_name,
                    entity_id=appno, entity_name=f"{sponsor} application {appno}",
                    record_type="drug_submission",
                    concept="submission.status_date",
                    concept_label=f"{subtype} submission {subno} status date",
                    value=date, value_numeric=None, unit=None,
                    period=date[:4], period_end=date,
                    version=f"{subtype}-{subno}",
                    metadata={
                        "application_number": appno,
                        "sponsor_name": sponsor,
                        "submission_type": subtype,
                        "submission_number": subno,
                        "submission_status": sub.get("submission_status"),
                        "submission_class_code": sub.get("submission_class_code"),
                        "review_priority": sub.get("review_priority"),
                        "is_original": subtype == "ORIG",
                    },
                    raw_reference=self._raw_reference(path, f"$.results[{ai}].submissions[{si}]", retrieved_at),
                )
            )
        return recs
