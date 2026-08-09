"""Stage orchestration: fetch -> normalize -> generate-questions -> build-contexts -> validate -> report.

Every stage writes its output to disk and reads its input from disk, which is what makes
the end-to-end command restartable: re-running a stage recomputes only that stage, and
`fetch` is idempotent because raw payloads are content-addressed by request URL.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import PipelineConfig, git_commit
from .normalize.common import RecordPool
from .schemas import Domain, Instance, NormalizedRecord, QuestionFamily, UnavailableVariant
from .sources import SourceBlocked, get_adapter
from .storage.io import (iter_models, read_models, sha256_jsonl_content, write_jsonl,
                         write_json, write_parquet)
from .storage.manifests import DatasetManifest, SourceRetrieval, utc_now


# --------------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------------


def normalized_path(cfg: PipelineConfig, domain: Domain) -> Path:
    return cfg.normalized_dir / f"{domain.value.lower()}.jsonl"


def families_path(cfg: PipelineConfig) -> Path:
    return cfg.out_dir / "question_families.jsonl"


def instances_path(cfg: PipelineConfig) -> Path:
    return cfg.out_dir / "instances.jsonl"


def unavailable_path(cfg: PipelineConfig) -> Path:
    return cfg.out_dir / "unavailable_variants.jsonl"


def retrievals_path(cfg: PipelineConfig) -> Path:
    return cfg.manifest_dir / "source_retrievals.json"


def manifest_path(cfg: PipelineConfig) -> Path:
    return cfg.manifest_dir / f"{cfg.name}_manifest.json"


def validation_path(cfg: PipelineConfig) -> Path:
    return cfg.report_dir / f"{cfg.name}_validation.json"


# --------------------------------------------------------------------------------------
# Stage 1: fetch
# --------------------------------------------------------------------------------------


def stage_fetch(cfg: PipelineConfig, domains: Optional[List[Domain]] = None, log=print) -> List[SourceRetrieval]:
    """Retrieve raw payloads from every enabled primary source.

    A blocked source is recorded as blocked and the run continues with the others.
    It is never substituted with data from somewhere else.
    """
    cfg.ensure_dirs()
    targets = domains or cfg.enabled_domains()
    out: List[SourceRetrieval] = []

    for domain in targets:
        t0 = time.time()
        try:
            adapter = get_adapter(domain, cfg)
        except KeyError as exc:
            log(f"  [{domain.value}] SKIP: {exc}")
            continue

        blocker = adapter.check_availability()
        if blocker:
            log(f"  [{domain.value}] BLOCKED: {blocker}")
            out.append(SourceRetrieval(
                domain=domain.value, source=adapter.source_name, api_base=adapter.api_base,
                api_version=adapter.api_version, retrieved_at=utc_now(),
                blocked=True, blocker_reason=blocker, errors=[blocker],
            ))
            continue

        log(f"  [{domain.value}] fetching from {adapter.api_base} ...")
        try:
            res = adapter.fetch()
        except SourceBlocked as exc:
            log(f"  [{domain.value}] BLOCKED: {exc}")
            out.append(SourceRetrieval(
                domain=domain.value, source=adapter.source_name, api_base=adapter.api_base,
                api_version=adapter.api_version, retrieved_at=utc_now(),
                blocked=True, blocker_reason=str(exc), errors=[str(exc)],
            ))
            continue

        sr = SourceRetrieval(
            domain=domain.value, source=res.source, api_base=res.api_base,
            api_version=res.api_version, retrieved_at=res.retrieved_at,
            n_requests=res.n_requests, n_raw_payloads=len(res.raw_paths),
            n_raw_records=res.n_raw_records, identifiers=res.identifiers,
            errors=res.errors, notes=res.notes, blocked=res.blocked,
            blocker_reason=res.blocker_reason,
        )
        out.append(sr)
        log(
            f"  [{domain.value}] {res.n_requests} requests, {len(res.raw_paths)} payloads, "
            f"{res.n_raw_records} raw records in {time.time() - t0:.1f}s"
            + (f" ({len(res.errors)} errors)" if res.errors else "")
        )
    _merge_retrievals(cfg, out)
    return out


def _merge_retrievals(cfg: PipelineConfig, new: List[SourceRetrieval]) -> List[SourceRetrieval]:
    """Persist retrieval records, replacing prior entries for the same domain."""
    existing: Dict[str, Dict[str, Any]] = {}
    path = retrievals_path(cfg)
    if path.exists():
        import json
        for row in json.loads(path.read_text()):
            existing[row["domain"]] = row
    for sr in new:
        existing[sr.domain] = sr.model_dump(mode="json")
    merged = [existing[k] for k in sorted(existing)]
    write_json(path, merged)
    return [SourceRetrieval.model_validate(r) for r in merged]


def load_retrievals(cfg: PipelineConfig) -> List[SourceRetrieval]:
    path = retrievals_path(cfg)
    if not path.exists():
        return []
    import json
    return [SourceRetrieval.model_validate(r) for r in json.loads(path.read_text())]


# --------------------------------------------------------------------------------------
# Stage 2: normalize
# --------------------------------------------------------------------------------------


def stage_normalize(cfg: PipelineConfig, domains: Optional[List[Domain]] = None, log=print) -> Dict[Domain, int]:
    """Convert cached raw payloads into the common record envelope. Offline + pure."""
    cfg.ensure_dirs()
    targets = domains or cfg.enabled_domains()
    counts: Dict[Domain, int] = {}

    for domain in targets:
        try:
            adapter = get_adapter(domain, cfg)
        except KeyError:
            continue
        raw_dir = cfg.raw_dir / adapter.raw_subdir
        if not raw_dir.exists() or not any(raw_dir.glob("*.json")):
            log(f"  [{domain.value}] no raw payloads; run `fetch` first")
            counts[domain] = 0
            continue
        records = adapter.normalize()
        # Deterministic order so the file hash is stable across runs.
        records.sort(key=lambda r: r.record_id)
        n = write_jsonl(normalized_path(cfg, domain), records)
        counts[domain] = n
        log(f"  [{domain.value}] normalized {n} records -> {normalized_path(cfg, domain)}")
    return counts


def load_pool(cfg: PipelineConfig, domains: Optional[List[Domain]] = None) -> Tuple[RecordPool, Dict[Domain, int]]:
    """Load normalized records for the given domains into an indexed pool."""
    targets = domains or cfg.enabled_domains()
    pool = RecordPool()
    counts: Dict[Domain, int] = {}
    for domain in targets:
        path = normalized_path(cfg, domain)
        n = 0
        for rec in iter_models(path, NormalizedRecord):
            pool.add(rec)
            n += 1
        counts[domain] = n
    return pool, counts


# --------------------------------------------------------------------------------------
# Stage 3: question families
# --------------------------------------------------------------------------------------


def stage_generate_questions(cfg: PipelineConfig, log=print) -> List[QuestionFamily]:
    from .questions import generate_families_for_domain

    cfg.ensure_dirs()
    pool, counts = load_pool(cfg)
    commit = git_commit(Path.cwd())
    families: List[QuestionFamily] = []

    for domain in cfg.enabled_domains():
        if counts.get(domain, 0) == 0:
            log(f"  [{domain.value}] no normalized records; skipping question generation")
            continue
        fams = generate_families_for_domain(domain, cfg, pool, git_sha=commit)
        families.extend(fams)
        by_type: Dict[str, int] = {}
        for f in fams:
            by_type[f.question_type.value] = by_type.get(f.question_type.value, 0) + 1
        log(f"  [{domain.value}] {len(fams)} families {by_type}")

    families.sort(key=lambda f: f.question_family_id)
    write_jsonl(families_path(cfg), families)
    log(f"  wrote {len(families)} families -> {families_path(cfg)}")
    return families


# --------------------------------------------------------------------------------------
# Stage 4: contexts
# --------------------------------------------------------------------------------------


def stage_build_contexts(cfg: PipelineConfig, log=print) -> Tuple[int, int]:
    from .context.builder import ContextBuilder
    from .context.tokenizer import get_tokenizer

    cfg.ensure_dirs()
    families = read_models(families_path(cfg), QuestionFamily)
    if not families:
        log("  no question families found; run `generate-questions` first")
        return 0, 0

    pool, _ = load_pool(cfg)
    tok = get_tokenizer(cfg.tokenizer)
    builder = ContextBuilder(cfg, pool, tok)
    log(f"  tokenizer: {tok.tokenizer_id} (version {tok.version})")

    instances: List[Instance] = []
    unavailable: List[UnavailableVariant] = []
    for i, fam in enumerate(families, 1):
        ins, un = builder.build_family(fam)
        instances.extend(ins)
        unavailable.extend(un)
        if i % 5 == 0 or i == len(families):
            log(f"  built {i}/{len(families)} families ({len(instances)} instances, {len(unavailable)} unavailable)")

    write_jsonl(instances_path(cfg), instances)
    write_jsonl(unavailable_path(cfg), unavailable)
    log(f"  wrote {len(instances)} instances -> {instances_path(cfg)}")
    if unavailable:
        log(f"  wrote {len(unavailable)} unavailable variants -> {unavailable_path(cfg)}")

    if cfg.write_parquet:
        rows = [i.model_dump(mode="json") for i in instances]
        ok = write_parquet(cfg.out_dir / "instances.parquet", rows)
        write_parquet(cfg.out_dir / "question_families.parquet",
                      [f.model_dump(mode="json") for f in families])
        log(f"  parquet mirror: {'written' if ok else 'skipped (pyarrow/pandas unavailable)'}")
    return len(instances), len(unavailable)


# --------------------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------------------


def build_manifest(cfg: PipelineConfig, timings: Optional[Dict[str, float]] = None) -> DatasetManifest:
    from .context.tokenizer import get_tokenizer

    try:
        tok = get_tokenizer(cfg.tokenizer)
        tok_id, tok_ver = tok.tokenizer_id, tok.version
    except Exception:  # noqa: BLE001 - a manifest must still be writable offline
        tok_id, tok_ver = cfg.tokenizer.id, None

    counts: Dict[str, int] = {}
    for domain in cfg.enabled_domains():
        p = normalized_path(cfg, domain)
        counts[f"normalized_{domain.value}"] = sum(1 for _ in iter_models(p, NormalizedRecord)) if p.exists() else 0

    fam_n = sum(1 for _ in iter_models(families_path(cfg), QuestionFamily)) if families_path(cfg).exists() else 0
    ins_n = sum(1 for _ in iter_models(instances_path(cfg), Instance)) if instances_path(cfg).exists() else 0
    counts["question_families"] = fam_n
    counts["instances"] = ins_n

    man = DatasetManifest(
        dataset_name=cfg.name,
        config_path=str(cfg.config_path) if cfg.config_path else None,
        config_hash=cfg.config_hash,
        seed=cfg.seed,
        git_commit=git_commit(Path.cwd()),
        tokenizer_id=tok_id,
        tokenizer_version=tok_ver,
        counts=counts,
        source_retrievals=load_retrievals(cfg),
        stage_timings_seconds=timings or {},
        content_sha256={
            "question_families": sha256_jsonl_content(families_path(cfg)),
            "instances": sha256_jsonl_content(instances_path(cfg)),
            "unavailable_variants": sha256_jsonl_content(unavailable_path(cfg)),
        },
    )
    for p in (families_path(cfg), instances_path(cfg), unavailable_path(cfg)):
        man.add_file(p, root=cfg.data_root.parent if cfg.data_root.parent != Path(".") else None)
    for domain in cfg.enabled_domains():
        man.add_file(normalized_path(cfg, domain))
    man.save(manifest_path(cfg))
    return man
