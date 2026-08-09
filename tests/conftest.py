"""Shared fixtures.

Every test runs fully offline against small committed payloads carved from authentic API
responses (provenance preserved in each envelope). Nothing in the default test run
touches the network -- tests that would are marked ``network`` and deselected by default.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from longctx_dataset.config import PipelineConfig, TokenizerConfig, ContextConfig, DomainConfig
from longctx_dataset.normalize.common import RecordPool
from longctx_dataset.schemas import Domain, QuestionType

FIXTURE_RAW = Path(__file__).parent / "fixtures" / "raw"

# Small enough to build quickly, still exercising every nesting step.
TEST_LENGTHS = [512, 1024, 2048]


def _domain_cfg(n: int = 5, **params) -> DomainConfig:
    return DomainConfig(
        enabled=True,
        n_families=n,
        params=params,
        question_type_mix={
            QuestionType.DIRECT_RETRIEVAL: 0.20,
            QuestionType.RETRIEVAL_CALCULATION: 0.30,
            QuestionType.TEMPORAL_VERSION: 0.15,
            QuestionType.ENTITY_UNIT_BINDING: 0.15,
            QuestionType.UNANSWERABLE: 0.20,
        },
    )


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    """A temp data tree pre-populated with the committed raw fixtures."""
    root = tmp_path / "data"
    for sub in ("raw", "normalized", "pilot", "manifests", "reports"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    for domain_dir in FIXTURE_RAW.iterdir():
        if domain_dir.is_dir():
            shutil.copytree(domain_dir, root / "raw" / domain_dir.name, dirs_exist_ok=True)
    return root


@pytest.fixture
def cfg(data_root: Path) -> PipelineConfig:
    c = PipelineConfig(
        name="test",
        seed=1234,
        data_root=data_root,
        output_subdir="pilot",
        write_parquet=False,
        tokenizer=TokenizerConfig(id="whitespace:v1", allow_fallback=False),
        context=ContextConfig(
            lengths=list(TEST_LENGTHS),
            target_position=0.50,
            position_tolerance=0.05,
            min_fill_ratio=0.90,
        ),
        domains={
            Domain.SEC: _domain_cfg(),
            Domain.FDA: _domain_cfg(),
            Domain.CLINICAL_TRIALS: _domain_cfg(),
            # The committed World Bank fixture's genuine null observations sit in the
            # 1960s, so the test window starts there rather than at the pilot's 1990.
            Domain.WORLD_BANK: _domain_cfg(date_range="1960:2024"),
        },
    )
    # SEC's availability gate must not block offline normalization tests.
    c.http.sec_user_agent = "longctx-dataset test suite tests@example.invalid"
    c.config_hash = c.compute_hash()
    return c


@pytest.fixture
def normalized(cfg: PipelineConfig):
    """All four adapters normalized from the fixtures, as a dict of domain -> records."""
    from longctx_dataset.sources import get_adapter

    out = {}
    for domain in cfg.enabled_domains():
        out[domain] = get_adapter(domain, cfg).normalize()
    return out


@pytest.fixture
def pool(normalized) -> RecordPool:
    p = RecordPool()
    for recs in normalized.values():
        for r in recs:
            p.add(r)
    return p
