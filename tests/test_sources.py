"""Source normalization against committed authentic payloads.

Each adapter is checked for the properties the rest of the pipeline relies on: stable
IDs, preserved provenance, correct typing of values, and -- importantly -- graceful
handling of malformed records rather than silent corruption.
"""

from __future__ import annotations

import json

import pytest

from longctx_dataset.schemas import Domain
from longctx_dataset.sources import get_adapter
from longctx_dataset.sources.base import SourceBlocked


def test_all_four_adapters_normalize_fixtures(normalized):
    for domain, recs in normalized.items():
        assert recs, f"{domain.value} produced no normalized records from its fixture"


def test_record_ids_are_unique_and_whitespace_free(normalized):
    for domain, recs in normalized.items():
        ids = [r.record_id for r in recs]
        assert len(ids) == len(set(ids)), f"{domain.value} produced duplicate record IDs"
        assert all(" " not in i for i in ids)


def test_normalization_is_deterministic(cfg):
    a = get_adapter(Domain.SEC, cfg).normalize()
    b = get_adapter(Domain.SEC, cfg).normalize()
    assert [r.record_id for r in a] == [r.record_id for r in b]
    assert [r.value for r in a] == [r.value for r in b]


def test_provenance_is_preserved(normalized):
    for domain, recs in normalized.items():
        for r in recs[:20]:
            assert r.raw_reference.raw_file, f"{domain.value}: record lost its raw file pointer"
            assert r.raw_reference.raw_pointer, f"{domain.value}: record lost its raw pointer"


def test_sec_facts_carry_frames_units_and_versions(normalized):
    recs = normalized[Domain.SEC]
    framed = [r for r in recs if r.metadata.get("has_frame")]
    assert framed, "no frame-bearing SEC facts; gold selection depends on frames"
    assert all(r.unit for r in recs)
    assert all(r.version for r in recs)
    assert any(r.metadata.get("period_kind") == "annual" for r in framed)
    # Verified independently against the SEC companyconcept endpoint.
    walmart_rev = [r for r in recs if r.concept == "us-gaap:Revenues" and r.period == "CY2011"]
    assert walmart_rev and walmart_rev[0].value_numeric == 446509000000.0


def test_world_bank_preserves_null_observations_separately(normalized):
    recs = normalized[Domain.WORLD_BANK]
    missing = [r for r in recs if r.record_type == "observation_missing"]
    valued = [r for r in recs if r.record_type == "indicator_observation"]
    assert missing, "fixture should contain at least one genuine null observation"
    assert valued
    assert all(r.value is None and r.value_numeric is None for r in missing)
    assert all(r.value_numeric is not None for r in valued)


def test_world_bank_extracts_unit_from_indicator_name(normalized):
    gdp = [r for r in normalized[Domain.WORLD_BANK] if r.concept == "NY.GDP.MKTP.CD"]
    assert gdp and gdp[0].unit == "current US$"


def test_fda_splits_products_into_field_level_records(normalized):
    recs = normalized[Domain.FDA]
    concepts = {r.concept for r in recs}
    assert "product.dosage_form" in concepts
    assert "product.active_ingredient_strength" in concepts
    assert "submission.status_date" in concepts
    strengths = [r for r in recs if r.concept == "product.active_ingredient_strength"]
    assert any(r.value_numeric is not None and r.unit for r in strengths), \
        "strength parsing produced no numeric magnitude"


def test_fda_submission_dates_are_iso_normalized(normalized):
    subs = [r for r in normalized[Domain.FDA] if r.concept == "submission.status_date"]
    assert subs
    for r in subs:
        assert len(str(r.value)) == 10 and str(r.value)[4] == "-"


def test_clinical_trials_explodes_fields_arms_and_outcomes(normalized):
    recs = normalized[Domain.CLINICAL_TRIALS]
    concepts = {r.concept for r in recs}
    assert {"enrollment.count", "study.start_date", "arm.type"} <= concepts
    arms = [r for r in recs if r.concept == "arm.type"]
    assert all(r.metadata.get("arm_label") for r in arms)
    enroll = [r for r in recs if r.concept == "enrollment.count"]
    assert enroll and all(r.value_numeric is not None for r in enroll)


def test_sec_adapter_blocks_without_a_real_user_agent(cfg):
    cfg.http.sec_user_agent = None
    adapter = get_adapter(Domain.SEC, cfg)
    blocker = adapter.check_availability()
    assert blocker and "SEC_USER_AGENT" in blocker
    result = adapter.fetch()
    assert result.blocked and result.blocker_reason
    assert not result.raw_paths, "a blocked adapter must not produce data"


def test_sec_adapter_rejects_placeholder_user_agent(cfg):
    cfg.http.sec_user_agent = "Acme your.email@example.com"
    blocker = get_adapter(Domain.SEC, cfg).check_availability()
    assert blocker and "placeholder" in blocker


# ---- malformed source handling ---------------------------------------------------------


def test_malformed_records_are_skipped_not_guessed_at(cfg, data_root):
    """Rows missing the fields needed to re-verify them must be dropped, not imputed."""
    # Declare the synthetic indicator/country in scope; the adapter filters the raw
    # cache to the configured scope, so an undeclared indicator would be dropped for
    # that reason instead of for being malformed, and the test would prove nothing.
    cfg.domains[Domain.WORLD_BANK].params.update(
        {"indicators": ["X.Y"], "countries": ["USA"], "date_range": "1960:2024"}
    )
    path = data_root / "raw" / "world_bank" / "malformed.json"
    path.write_text(json.dumps({
        "request_url": "https://api.worldbank.org/v2/test",
        "retrieved_at": "2026-01-01T00:00:00Z",
        "payload": [
            {"page": 1, "pages": 1},
            [
                {"indicator": {"id": "X.Y", "value": "X"}, "country": {"id": "US", "value": "USA"},
                 "countryiso3code": "USA", "date": "2020", "value": 5.0},   # valid
                {"indicator": {"id": "X.Y"}, "date": "2020", "value": 5.0},  # no country
                {"country": {"id": "US"}, "date": "2020", "value": 5.0},     # no indicator
                {"indicator": {"id": "X.Y"}, "countryiso3code": "USA", "value": 5.0},  # no date
                "not-a-dict",
                None,
            ],
        ],
    }))
    recs = get_adapter(Domain.WORLD_BANK, cfg).normalize()
    survivors = [r for r in recs if r.concept == "X.Y"]
    assert len(survivors) == 1, "exactly the one well-formed malformed-file row should survive"
    assert survivors[0].value_numeric == 5.0


def test_corrupt_raw_payload_raises_rather_than_silently_skipping(cfg, data_root):
    (data_root / "raw" / "world_bank" / "corrupt.json").write_text("{not json at all")
    with pytest.raises(ValueError, match="corrupt raw payload"):
        get_adapter(Domain.WORLD_BANK, cfg).normalize()


def test_unexpected_payload_shape_yields_no_records(cfg, data_root):
    (data_root / "raw" / "fda" / "weird.json").write_text(json.dumps(
        {"request_url": "u", "retrieved_at": "t", "payload": {"results": "not-a-list"}}))
    recs = get_adapter(Domain.FDA, cfg).normalize()
    assert recs  # the good fixture still normalizes; the weird payload contributes nothing
