"""Command-line interface.

    python -m longctx_dataset <command> --config config/pilot.yaml

Commands mirror the pipeline stages one-to-one, plus ``build-pilot`` which runs the whole
chain. Every stage reads and writes disk, so any stage can be re-run in isolation and the
end-to-end command is restartable.

``validate`` exits nonzero when a CRITICAL check fails; that is the gate for scaling up.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import List, Optional

from .config import load_config
from .schemas import Domain, export_json_schemas
from .storage.io import write_json

BANNER = "longctx-dataset"


def _log(msg: str = "") -> None:
    print(msg, flush=True)


def _section(title: str) -> None:
    _log(f"\n=== {title} ===")


def _parse_domains(value: Optional[str]) -> Optional[List[Domain]]:
    if not value:
        return None
    out = []
    for part in value.split(","):
        part = part.strip().upper()
        if not part:
            continue
        try:
            out.append(Domain(part))
        except ValueError as exc:
            raise SystemExit(f"unknown domain {part!r}; valid: {[d.value for d in Domain]}") from exc
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="longctx-dataset", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp, with_domain: bool = False):
        sp.add_argument("--config", "-c", default="config/pilot.yaml", help="path to a YAML config")
        if with_domain:
            sp.add_argument("--domain", "-d", default=None,
                            help="comma-separated domains (default: all enabled in config)")
        return sp

    add_common(sub.add_parser("fetch", help="retrieve raw payloads from primary sources"), True)
    add_common(sub.add_parser("normalize", help="convert raw payloads to normalized records"), True)
    add_common(sub.add_parser("generate-questions", help="derive question families with deterministic gold answers"))
    add_common(sub.add_parser("build-contexts", help="build nested contexts at every configured length"))

    sp = add_common(sub.add_parser("validate", help="run the validation suite (nonzero exit on CRITICAL failures)"))
    sp.add_argument("--strict", action="store_true", help="also fail on WARNING-severity checks")

    sp = add_common(sub.add_parser("report", help="write the pilot report (markdown + json)"))
    sp.add_argument("--examples", type=int, default=4, help="representative families to include")

    sp = add_common(sub.add_parser("audit", help="assemble the human-audit package"))
    sp.add_argument("--also", action="append", default=[],
                    help="additional config(s) whose datasets should be sampled too "
                         "(repeatable, e.g. --also config/fred_pilot.yaml)")
    sp.add_argument("--n", type=int, default=12, help="how many families to sample")
    sp.add_argument("--out", default="data/audit", help="output directory")

    sp = add_common(sub.add_parser("build-pilot", help="end-to-end: fetch -> ... -> report"), True)
    sp.add_argument("--skip-fetch", action="store_true", help="reuse cached raw payloads")
    sp.add_argument("--strict", action="store_true")

    sp = add_common(sub.add_parser("readiness", help="write the pre-production readiness report"))
    sp.add_argument("--fred-config", default="config/fred_pilot.yaml")
    sp.add_argument("--preproduction", default="config/preproduction.yaml")
    sp.add_argument("--production", default="config/production.yaml")
    sp.add_argument("--audit-dir", default="data/audit")

    sp = sub.add_parser("export-schemas", help="write JSON Schema for every public model")
    sp.add_argument("--out", default="data/schemas", help="output directory")

    add_common(sub.add_parser("stats", help="summarize what currently exists on disk"), True)
    return p


# --------------------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------------------


def cmd_fetch(args) -> int:
    from .pipeline import stage_fetch

    cfg = load_config(args.config)
    _section(f"FETCH  (config={cfg.name}, hash={cfg.config_hash})")
    rets = stage_fetch(cfg, _parse_domains(args.domain), log=_log)
    blocked = [r for r in rets if r.blocked]
    for r in blocked:
        _log(f"\n  !! {r.domain} BLOCKED: {r.blocker_reason}")
    _log(f"\n  {len(rets) - len(blocked)}/{len(rets)} sources retrieved.")
    return 0


def cmd_normalize(args) -> int:
    from .pipeline import stage_normalize

    cfg = load_config(args.config)
    _section(f"NORMALIZE  (config={cfg.name})")
    counts = stage_normalize(cfg, _parse_domains(args.domain), log=_log)
    _log(f"\n  total normalized records: {sum(counts.values())}")
    return 0


def cmd_generate_questions(args) -> int:
    from .pipeline import stage_generate_questions

    cfg = load_config(args.config)
    _section(f"GENERATE-QUESTIONS  (seed={cfg.seed})")
    fams = stage_generate_questions(cfg, log=_log)
    return 0 if fams else 1


def cmd_build_contexts(args) -> int:
    from .pipeline import stage_build_contexts

    cfg = load_config(args.config)
    _section(f"BUILD-CONTEXTS  (lengths={cfg.context.lengths})")
    n_ins, n_un = stage_build_contexts(cfg, log=_log)
    return 0 if n_ins else 1


def cmd_validate(args) -> int:
    from .pipeline import build_manifest, validation_path
    from .validation.dataset import run_validation

    cfg = load_config(args.config)
    _section("VALIDATE")
    report = run_validation(cfg, log=_log)
    write_json(validation_path(cfg), report.to_dict())
    build_manifest(cfg)
    _log(report.summary_text())
    _log(f"\n  full report -> {validation_path(cfg)}")
    failed = report.has_critical_failures() or (args.strict and report.has_warnings())
    return 1 if failed else 0


def cmd_report(args) -> int:
    from .report import generate_report

    cfg = load_config(args.config)
    _section("REPORT")
    md_path, json_path = generate_report(cfg, n_examples=args.examples, log=_log)
    _log(f"  markdown -> {md_path}")
    _log(f"  json     -> {json_path}")
    return 0


def cmd_build_pilot(args) -> int:
    from .pipeline import (build_manifest, stage_build_contexts, stage_fetch,
                           stage_generate_questions, stage_normalize, validation_path)
    from .report import generate_report
    from .validation.dataset import run_validation

    cfg = load_config(args.config)
    domains = _parse_domains(getattr(args, "domain", None))
    timings = {}
    _log(f"{BANNER}: end-to-end build of '{cfg.name}' (config hash {cfg.config_hash}, seed {cfg.seed})")

    if not args.skip_fetch:
        _section("1/6 FETCH")
        t = time.time(); stage_fetch(cfg, domains, log=_log); timings["fetch"] = time.time() - t
    else:
        _log("\n=== 1/6 FETCH (skipped; using cached raw payloads) ===")

    _section("2/6 NORMALIZE")
    t = time.time(); stage_normalize(cfg, domains, log=_log); timings["normalize"] = time.time() - t

    _section("3/6 GENERATE-QUESTIONS")
    t = time.time(); fams = stage_generate_questions(cfg, log=_log); timings["generate_questions"] = time.time() - t
    if not fams:
        _log("\n  FATAL: no question families generated; cannot continue.")
        return 1

    _section("4/6 BUILD-CONTEXTS")
    t = time.time(); stage_build_contexts(cfg, log=_log); timings["build_contexts"] = time.time() - t

    _section("5/6 VALIDATE")
    t = time.time(); report = run_validation(cfg, log=_log); timings["validate"] = time.time() - t
    write_json(validation_path(cfg), report.to_dict())
    _log(report.summary_text())

    _section("6/6 REPORT")
    t = time.time()
    build_manifest(cfg, timings)
    md_path, json_path = generate_report(cfg, n_examples=4, log=_log)
    timings["report"] = time.time() - t
    build_manifest(cfg, timings)
    _log(f"  markdown -> {md_path}")

    failed = report.has_critical_failures() or (args.strict and report.has_warnings())
    _log(f"\n{BANNER}: {'FAILED' if failed else 'OK'} — {report.one_line()}")
    return 1 if failed else 0


def cmd_audit(args) -> int:
    from .audit import build_audit_package

    cfgs = [load_config(args.config)] + [load_config(p) for p in args.also]
    _section(f"AUDIT  ({', '.join(c.name for c in cfgs)})")
    summary = build_audit_package(cfgs, Path(args.out), n_families=args.n,
                                  seed=cfgs[0].seed, log=_log)
    _log(f"\n  {summary['n_families']} families -> {args.out}")
    _log(f"  index -> {Path(args.out) / 'audit_index.md'}")
    _log("  checklist status: PENDING_HUMAN_REVIEW (intentionally unticked)")
    return 0


def cmd_readiness(args) -> int:
    from .readiness import build_readiness

    pilot = load_config(args.config)
    fred = load_config(args.fred_config)
    _section("PRE-PRODUCTION READINESS")
    md, js = build_readiness(pilot, fred, args.preproduction, args.production,
                             Path(args.audit_dir), pilot.report_dir, log=_log)
    _log(f"  markdown -> {md}")
    _log(f"  json     -> {js}")
    return 0


def cmd_export_schemas(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, schema in export_json_schemas().items():
        write_json(out / f"{name}.schema.json", schema)
        _log(f"  wrote {out / (name + '.schema.json')}")
    return 0


def cmd_stats(args) -> int:
    from .pipeline import (families_path, instances_path, load_retrievals,
                           normalized_path, unavailable_path)
    from .schemas import Instance, NormalizedRecord, QuestionFamily
    from .storage.io import iter_models, iter_jsonl

    cfg = load_config(args.config)
    _section(f"STATS  ({cfg.name})")
    for domain in cfg.enabled_domains():
        p = normalized_path(cfg, domain)
        n = sum(1 for _ in iter_models(p, NormalizedRecord)) if p.exists() else 0
        _log(f"  normalized {domain.value:<16} {n:>8}")
    for label, path, model in (
        ("question_families", families_path(cfg), QuestionFamily),
        ("instances", instances_path(cfg), Instance),
    ):
        n = sum(1 for _ in iter_models(path, model)) if path.exists() else 0
        _log(f"  {label:<27} {n:>8}")
    n_un = sum(1 for _ in iter_jsonl(unavailable_path(cfg))) if unavailable_path(cfg).exists() else 0
    _log(f"  {'unavailable_variants':<27} {n_un:>8}")
    for r in load_retrievals(cfg):
        flag = "BLOCKED" if r.blocked else "ok"
        _log(f"  source {r.domain:<20} {flag:<8} raw_records={r.n_raw_records} at {r.retrieved_at}")
    return 0


COMMANDS = {
    "fetch": cmd_fetch,
    "normalize": cmd_normalize,
    "generate-questions": cmd_generate_questions,
    "build-contexts": cmd_build_contexts,
    "validate": cmd_validate,
    "report": cmd_report,
    "build-pilot": cmd_build_pilot,
    "audit": cmd_audit,
    "readiness": cmd_readiness,
    "export-schemas": cmd_export_schemas,
    "stats": cmd_stats,
}


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except KeyboardInterrupt:
        _log("\ninterrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
