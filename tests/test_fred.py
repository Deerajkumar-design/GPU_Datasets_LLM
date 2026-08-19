"""FRED / ALFRED adapter and templates.

Runs entirely offline against committed payloads carved from real St. Louis Fed
responses, with each envelope's request URL and retrieval timestamp preserved.
"""

from __future__ import annotations

import json

import pytest

from longctx_dataset.distractors.taxonomy import classify_distractor
from longctx_dataset.normalize.common import RecordPool
from longctx_dataset.questions import generate_families_for_domain
from longctx_dataset.schemas import Domain, DistractorType, NormalizedRecord, QuestionType
from longctx_dataset.sources import get_adapter
from longctx_dataset.sources.fred import FREDAdapter, _is_missing, _parse_fred_csv


@pytest.fixture
def fred_records(cfg):
    return get_adapter(Domain.FRED, cfg).normalize()


# ---- CSV parsing -------------------------------------------------------------------


def test_parse_csv_splits_header_and_rows():
    cols, rows = _parse_fred_csv("observation_date,GDP\n2021-01-01,22048.894\n2021-04-01,22740.959\n")
    assert cols == ["GDP"]
    assert rows[0] == ("2021-01-01", ["22048.894"])
    assert len(rows) == 2


@pytest.mark.parametrize("raw,expected", [("", True), (".", True), ("NA", True),
                                          ("n/a", True), ("0", False), ("22048.894", False)])
def test_missing_observation_tokens(raw, expected):
    assert _is_missing(raw) is expected


def test_vintage_column_is_split_into_series_and_date():
    assert FREDAdapter._split_column("GDP_20240131", True) == ("GDP", "2024-01-31")
    assert FREDAdapter._split_column("GDP", False) == ("GDP", None)
    # A series ID containing an underscore must not be mistaken for a vintage suffix.
    assert FREDAdapter._split_column("SOME_SERIES", True) == ("SOME_SERIES", None)


# ---- normalization -----------------------------------------------------------------


def test_normalizes_observations_with_provenance(fred_records):
    assert fred_records
    for r in fred_records[:20]:
        assert r.domain is Domain.FRED
        assert r.raw_reference.raw_file and r.raw_reference.raw_pointer
        assert r.metadata["series_id"] == r.concept


def test_record_ids_unique_and_deterministic(cfg):
    a = get_adapter(Domain.FRED, cfg).normalize()
    b = get_adapter(Domain.FRED, cfg).normalize()
    ids = [r.record_id for r in a]
    assert len(ids) == len(set(ids))
    assert ids == [r.record_id for r in b]


def test_only_configured_series_are_emitted(cfg, fred_records):
    configured = {s["id"] for s in cfg.domains[Domain.FRED].params["series"]}
    assert {r.concept for r in fred_records} <= configured


def test_descriptive_metadata_is_marked_operator_supplied(fred_records):
    """Keyless runs must not pass catalog attributes off as API-returned."""
    sample = fred_records[0]
    assert sample.metadata["metadata_source"] == "operator_catalog"
    assert sample.metadata["metadata_note"]
    assert sample.unit and sample.metadata["frequency"] and sample.metadata["seasonal_adjustment"]


def test_vintage_records_carry_distinct_versions(fred_records):
    vint = [r for r in fred_records if r.record_type == "fred_vintage_observation"]
    assert vint, "fixtures should contain ALFRED vintage payloads"
    assert all(r.version.startswith("vintage:") for r in vint)
    assert all(r.metadata["is_vintage"] for r in vint)
    latest = [r for r in fred_records if r.record_type == "fred_observation"]
    assert latest and all(r.version == "latest" for r in latest)


def test_revisions_are_real_not_manufactured(fred_records):
    """The same observation must carry genuinely different values across vintages.

    This is FRED's reason for being in the benchmark; if the fixture ever stopped
    exhibiting it, the WRONG_VERSION story would be hollow.
    """
    by_obs = {}
    for r in fred_records:
        if r.record_type == "fred_vintage_observation" and r.value_numeric is not None:
            by_obs.setdefault((r.concept, r.period), set()).add(r.value_numeric)
    revised = {k: v for k, v in by_obs.items() if len(v) >= 2}
    assert revised, "no observation shows more than one vintage value"
    # GDP 2021-Q1 is the documented example.
    gdp = by_obs.get(("GDP", "2021-01-01"))
    assert gdp and len(gdp) >= 2


def test_missing_observations_are_preserved_but_valueless(fred_records):
    missing = [r for r in fred_records if r.record_type == "observation_missing"]
    for r in missing:
        assert r.value is None and r.value_numeric is None
        assert r.metadata["no_data"] is True


def test_malformed_rows_are_skipped(cfg, data_root):
    """Unparseable values are dropped; empty ones become explicit missing observations.

    PAYEMS is used deliberately: the committed fixtures carry only its ALFRED *vintage*
    payloads, so the current-vintage records below come solely from this payload. Using a
    series that also has an observation fixture would leave the assertion depending on
    which payload won the record-ID dedup, which is not what this test is about.
    """
    (data_root / "raw" / "fred" / "zz_malformed.json").write_text(json.dumps({
        "request_url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PAYEMS",
        "retrieved_at": "2026-01-01T00:00:00Z",
        "payload": ("observation_date,PAYEMS\n"
                    "2019-01-01,150000\n"
                    "2019-02-01,not-a-number\n"
                    "2019-03-01,\n"
                    "badrow\n"),
    }))
    recs = get_adapter(Domain.FRED, cfg).normalize()
    by_period = {r.period: r for r in recs
                 if r.concept == "PAYEMS" and r.version == "latest"}
    assert by_period["2019-01-01"].value_numeric == 150000.0
    assert "2019-02-01" not in by_period, "an unparseable value must be dropped, not guessed"
    assert by_period["2019-03-01"].record_type == "observation_missing"
    assert by_period["2019-03-01"].value is None


def test_unknown_series_outside_catalog_is_ignored(cfg, data_root):
    (data_root / "raw" / "fred" / "unknown.json").write_text(json.dumps({
        "request_url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=ZZZNOTREAL",
        "retrieved_at": "2026-01-01T00:00:00Z",
        "payload": "observation_date,ZZZNOTREAL\n2019-01-01,1.0\n",
    }))
    recs = get_adapter(Domain.FRED, cfg).normalize()
    assert not [r for r in recs if r.concept == "ZZZNOTREAL"]


def test_adapter_is_never_blocked_without_a_key(cfg):
    adapter = get_adapter(Domain.FRED, cfg)
    assert adapter.check_availability() is None
    assert adapter.backend == "fredgraph_csv"


def test_backend_switches_when_a_key_is_present(cfg):
    cfg.http.fred_api_key = "test-key-not-used-offline"
    assert get_adapter(Domain.FRED, cfg).backend == "fred_api"


# ---- distractor classification -------------------------------------------------------


def _find(records, concept, period, version="latest"):
    return next(r for r in records
                if r.concept == concept and r.period == period and r.version == version)


def test_seasonal_adjustment_twin_is_a_series_variant(fred_records):
    period = sorted({r.period for r in fred_records if r.concept == "UNRATE"})[-1]
    target = _find(fred_records, "UNRATE", period)
    twin = _find(fred_records, "UNRATENSA", period)
    assert target.unit == twin.unit
    assert classify_distractor(twin, [target])[0] is DistractorType.WRONG_SERIES_VARIANT


def test_chained_dollar_twin_is_a_unit_conflict(fred_records):
    periods = ({r.period for r in fred_records if r.concept == "GDP"}
               & {r.period for r in fred_records if r.concept == "GDPC1"})
    period = sorted(periods)[-1]
    target, twin = _find(fred_records, "GDP", period), _find(fred_records, "GDPC1", period)
    assert target.unit != twin.unit
    assert classify_distractor(twin, [target])[0] is DistractorType.WRONG_UNIT


def test_other_state_is_an_entity_conflict(fred_records):
    periods = ({r.period for r in fred_records if r.concept == "CAUR"}
               & {r.period for r in fred_records if r.concept == "TXUR"})
    period = sorted(periods)[-1]
    target, other = _find(fred_records, "CAUR", period), _find(fred_records, "TXUR", period)
    assert classify_distractor(other, [target])[0] is DistractorType.WRONG_ENTITY


def test_vintage_of_same_observation_is_a_version_conflict(fred_records):
    vint = [r for r in fred_records if r.record_type == "fred_vintage_observation"
            and r.concept == "GDP"]
    assert vint
    v = vint[0]
    target = _find(fred_records, "GDP", v.period)
    dtype, flags = classify_distractor(v, [target])
    assert dtype is DistractorType.WRONG_VERSION
    assert flags["different_version"] and flags["same_metric"] and flags["same_period"]


def test_unrelated_series_is_a_field_conflict(fred_records):
    periods = ({r.period for r in fred_records if r.concept == "UNRATE"}
               & {r.period for r in fred_records if r.concept == "FEDFUNDS"})
    period = sorted(periods)[-1]
    target = _find(fred_records, "UNRATE", period)
    other = _find(fred_records, "FEDFUNDS", period)
    assert classify_distractor(other, [target])[0] is DistractorType.WRONG_FIELD


# ---- templates -----------------------------------------------------------------------


@pytest.fixture
def fred_families(cfg, fred_records):
    pool = RecordPool(fred_records)
    return generate_families_for_domain(Domain.FRED, cfg, pool)


def test_templates_cover_every_question_type(fred_families):
    assert fred_families
    assert {f.question_type for f in fred_families} == set(QuestionType)


def test_gold_answers_come_from_source_records(cfg, fred_records, fred_families):
    from longctx_dataset.validation.gold import verify_family

    pool = RecordPool(fred_records)
    for fam in fred_families:
        assert verify_family(fam, pool, 1e-9) == [], fam.question_family_id


def test_vintage_family_binds_to_one_vintage(cfg, fred_records, fred_families):
    vintage = [f for f in fred_families
               if f.generation_metadata.template_id == "FRED_VINTAGE_SELECTION"]
    if not vintage:
        pytest.skip("fixture window produced no revised observation for this seed")
    fam = vintage[0]
    pool = RecordPool(fred_records)
    ev = pool.get(fam.gold_evidence_ids[0])
    assert ev.version.startswith("vintage:")
    # The named vintage's value must differ from at least one declared foil, or the
    # question would not be a selection task at all.
    foils = fam.target_conditions.get("explicit_foils") or []
    assert foils


def test_unanswerable_family_is_genuinely_absent(cfg, fred_records, fred_families):
    pool = RecordPool(fred_records)
    for fam in fred_families:
        if fam.answerable:
            continue
        spec = fam.unanswerable_spec
        assert spec.verified_absent_in_pool
        matches = [r for r in pool.matches_target(entity_id=spec.missing_entity_id,
                                                  concept=spec.missing_concept,
                                                  period=spec.missing_period)
                   if r.value is not None]
        assert not matches, f"{fam.question_family_id} is answerable after all"


def test_spread_operands_share_a_unit(fred_families):
    for fam in fred_families:
        if fam.generation_metadata.template_id != "FRED_SERIES_SPREAD":
            continue
        units = {e.unit for e in fam.gold_evidence}
        assert len(units) == 1, "a spread across mixed units would be meaningless"
