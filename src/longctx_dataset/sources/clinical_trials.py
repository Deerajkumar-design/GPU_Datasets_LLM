"""ClinicalTrials.gov API v2 adapter.

API: https://clinicaltrials.gov/api/v2/studies  (current official API; no credentials)

Each study is exploded into field-level records: enrollment, status, the several
distinct date fields, phase, design attributes, eligibility bounds, arm groups,
interventions, and primary/secondary outcome measures with their timeframes.

Field-level granularity is what makes the interference realistic. A context can then
contain the *same* trial's several dates, the *same* intervention across other trials,
and other arms of the same trial -- so answering requires binding to an exact
(trial, field, arm, timepoint) tuple rather than pattern-matching a number.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..normalize.common import canonical_date, canonical_number, make_record_id
from ..schemas import Domain, NormalizedRecord
from .base import HTTPClient, RetrievalResult, SourceAdapter, register_adapter, utc_now

API_BASE = "https://clinicaltrials.gov/api/v2"

DEFAULT_QUERIES = [
    "metformin", "atorvastatin", "pembrolizumab", "insulin glargine",
    "semaglutide", "rivaroxaban", "aspirin", "tranexamic acid",
]

# Simple scalar paths -> (concept, label, kind)
_SCALAR_FIELDS = [
    ("statusModule.overallStatus", "study.overall_status", "Overall recruitment status", "string"),
    ("statusModule.startDateStruct.date", "study.start_date", "Study start date", "date"),
    ("statusModule.primaryCompletionDateStruct.date", "study.primary_completion_date", "Primary completion date", "date"),
    ("statusModule.completionDateStruct.date", "study.completion_date", "Study completion date", "date"),
    ("statusModule.studyFirstPostDateStruct.date", "study.first_posted_date", "Study first posted date", "date"),
    ("statusModule.lastUpdatePostDateStruct.date", "study.last_update_posted_date", "Last update posted date", "date"),
    ("statusModule.resultsFirstPostDateStruct.date", "study.results_first_posted_date", "Results first posted date", "date"),
    ("designModule.studyType", "study.study_type", "Study type", "string"),
    ("designModule.designInfo.allocation", "design.allocation", "Allocation", "string"),
    ("designModule.designInfo.interventionModel", "design.intervention_model", "Intervention model", "string"),
    ("designModule.designInfo.primaryPurpose", "design.primary_purpose", "Primary purpose", "string"),
    ("designModule.designInfo.maskingInfo.masking", "design.masking", "Masking", "string"),
    ("eligibilityModule.sex", "eligibility.sex", "Eligible sex", "string"),
    ("eligibilityModule.minimumAge", "eligibility.minimum_age", "Minimum eligible age", "string"),
    ("eligibilityModule.maximumAge", "eligibility.maximum_age", "Maximum eligible age", "string"),
    ("eligibilityModule.healthyVolunteers", "eligibility.healthy_volunteers", "Accepts healthy volunteers", "bool"),
    ("sponsorCollaboratorsModule.leadSponsor.name", "sponsor.lead_sponsor", "Lead sponsor", "string"),
]


def _dig(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


@register_adapter
class ClinicalTrialsAdapter(SourceAdapter):
    domain = Domain.CLINICAL_TRIALS
    source_name = "CLINICALTRIALS_GOV_V2"
    api_base = API_BASE
    api_version = "v2"
    license_note = "ClinicalTrials.gov (NLM), public domain"

    def _client(self) -> HTTPClient:
        return HTTPClient(
            self.cfg,
            self.raw_subdir,
            headers={"Accept": "application/json", "User-Agent": "longctx-dataset/0.1 (research)"},
            rate_limit_per_second=self.cfg.http.default_rate_limit_per_second,
        )

    def _queries(self) -> List[str]:
        return list(self.params.get("queries") or DEFAULT_QUERIES)

    def fetch(self) -> RetrievalResult:
        client = self._client()
        res = RetrievalResult(
            domain=self.domain, source=self.source_name, api_base=API_BASE, api_version="v2"
        )
        page_size = int(self.params.get("page_size", 100))
        max_pages = int(self.params.get("max_pages_per_query", 2))
        status_filter = self.params.get("overall_status", "COMPLETED")

        for query in self._queries():
            token: Optional[str] = None
            for page in range(max_pages):
                params: Dict[str, Any] = {
                    "query.term": query,
                    "pageSize": page_size,
                    "countTotal": "true",
                }
                if status_filter:
                    params["filter.overallStatus"] = status_filter
                if token:
                    params["pageToken"] = token
                try:
                    payload, path = client.get_json(f"{API_BASE}/studies", params)
                except Exception as exc:  # noqa: BLE001
                    res.errors.append(f"{query} page {page}: {exc}")
                    break
                studies = (payload or {}).get("studies") or []
                if not studies:
                    break
                res.raw_paths.append(path)
                res.n_raw_records += len(studies)
                if query not in res.identifiers:
                    res.identifiers.append(query)
                token = (payload or {}).get("nextPageToken")
                if not token:
                    break

        res.n_requests = client.n_requests
        res.retrieved_at = utc_now()
        if not res.raw_paths:
            res.blocked = True
            res.blocker_reason = "no ClinicalTrials.gov payloads retrieved: " + "; ".join(res.errors[:3])
        return res

    # ---- normalize ------------------------------------------------------------------

    def normalize(self) -> List[NormalizedRecord]:
        out: List[NormalizedRecord] = []
        seen: set[str] = set()
        for envelope, path in self.iter_raw_payloads():
            payload = envelope.get("payload") or {}
            studies = payload.get("studies")
            if not isinstance(studies, list):
                continue
            retrieved_at = envelope.get("retrieved_at")
            for si, study in enumerate(studies):
                proto = (study or {}).get("protocolSection")
                if not isinstance(proto, dict):
                    continue
                for rec in self._normalize_study(proto, path, si, retrieved_at):
                    if rec.record_id not in seen:
                        seen.add(rec.record_id)
                        out.append(rec)
        return out

    def _normalize_study(self, proto, path, si, retrieved_at) -> List[NormalizedRecord]:
        ident = proto.get("identificationModule") or {}
        nct = ident.get("nctId")
        if not nct:
            return []
        title = ident.get("briefTitle") or nct
        status = _dig(proto, "statusModule.overallStatus")
        last_update = _dig(proto, "statusModule.lastUpdatePostDateStruct.date")
        conditions = (proto.get("conditionsModule") or {}).get("conditions") or []
        base_meta = {
            "nct_id": nct,
            "brief_title": title,
            "overall_status": status,
            "conditions": conditions,
            "phases": _dig(proto, "designModule.phases") or [],
            "lead_sponsor": _dig(proto, "sponsorCollaboratorsModule.leadSponsor.name"),
        }
        url = f"https://clinicaltrials.gov/study/{nct}"
        recs: List[NormalizedRecord] = []

        def mk(concept, label, value, *, rtype, numeric=None, unit=None, period=None,
               version=None, extra=None, pointer="", key_parts=()) -> NormalizedRecord:
            ref = self._raw_reference(path, f"$.studies[{si}].protocolSection.{pointer}", retrieved_at)
            ref.source_url = url
            return NormalizedRecord(
                record_id=make_record_id("CT", nct, concept, *key_parts),
                domain=self.domain, source=self.source_name,
                entity_id=nct, entity_name=title,
                record_type=rtype, concept=concept, concept_label=label,
                value=value, value_numeric=numeric, unit=unit,
                period=period, version=version or (f"lastupdate:{last_update}" if last_update else None),
                metadata={**base_meta, **(extra or {})},
                raw_reference=ref,
            )

        # Enrollment: the workhorse numeric field for retrieval + calculation questions.
        enroll = _dig(proto, "designModule.enrollmentInfo") or {}
        if enroll.get("count") is not None:
            recs.append(mk(
                "enrollment.count", "Enrollment (participants)", canonical_number(enroll.get("count")),
                rtype="trial_field", numeric=canonical_number(enroll.get("count")),
                unit="participants", extra={"enrollment_type": enroll.get("type")},
                pointer="designModule.enrollmentInfo.count",
            ))

        for path_, concept, label, kind in _SCALAR_FIELDS:
            value = _dig(proto, path_)
            if value in (None, ""):
                continue
            if kind == "date":
                value = canonical_date(value)
            elif kind == "bool":
                value = "Yes" if value else "No"
            recs.append(mk(
                concept, label, str(value), rtype="trial_field",
                period=str(value)[:4] if kind == "date" else None,
                extra={"field_kind": kind}, pointer=path_,
            ))

        phases = _dig(proto, "designModule.phases") or []
        if phases:
            recs.append(mk("study.phase", "Study phase", "/".join(phases), rtype="trial_field",
                           pointer="designModule.phases"))

        arms = _dig(proto, "armsInterventionsModule.armGroups") or []
        if arms:
            recs.append(mk("arms.count", "Number of arm groups", float(len(arms)),
                           rtype="trial_field", numeric=float(len(arms)), unit="arms",
                           pointer="armsInterventionsModule.armGroups"))
        for i, arm in enumerate(arms):
            if not isinstance(arm, dict) or not arm.get("label"):
                continue
            recs.append(mk(
                "arm.type", f"Arm group type: {arm.get('label')}", str(arm.get("type") or "UNSPECIFIED"),
                rtype="trial_arm", extra={"arm_label": arm.get("label"), "arm_index": i,
                                          "arm_interventions": arm.get("interventionNames") or []},
                pointer=f"armsInterventionsModule.armGroups[{i}]", key_parts=(arm.get("label"), i),
            ))

        for i, iv in enumerate(_dig(proto, "armsInterventionsModule.interventions") or []):
            if not isinstance(iv, dict) or not iv.get("name"):
                continue
            recs.append(mk(
                "intervention.type", f"Intervention: {iv.get('name')}", str(iv.get("type") or "OTHER"),
                rtype="trial_intervention",
                extra={"intervention_name": iv.get("name"), "intervention_index": i,
                       "arm_group_labels": iv.get("armGroupLabels") or []},
                pointer=f"armsInterventionsModule.interventions[{i}]", key_parts=(iv.get("name"), i),
            ))

        for kind, key in (("primary", "primaryOutcomes"), ("secondary", "secondaryOutcomes")):
            for i, oc in enumerate(_dig(proto, f"outcomesModule.{key}") or []):
                if not isinstance(oc, dict) or not oc.get("measure"):
                    continue
                recs.append(mk(
                    f"outcome.{kind}.timeframe", f"{kind.capitalize()} outcome timeframe: {oc.get('measure')}",
                    str(oc.get("timeFrame") or "(not specified)"),
                    rtype="trial_outcome",
                    extra={"outcome_measure": oc.get("measure"), "outcome_kind": kind, "outcome_index": i},
                    pointer=f"outcomesModule.{key}[{i}]", key_parts=(kind, i),
                ))

        for i, cond in enumerate(conditions):
            recs.append(mk("study.condition", "Studied condition", str(cond), rtype="trial_field",
                           extra={"condition_index": i},
                           pointer=f"conditionsModule.conditions[{i}]", key_parts=(i,)))
        return recs
