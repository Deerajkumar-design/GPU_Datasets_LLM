"""Merge the frozen 100-family Llama v2 benchmark into the 500-family expansion.

The generator can create a 500-family candidate pool directly, but family IDs 0001-0025
per domain are already validated/audited in ``preproduction_llama32_3b_v2``. This script
replaces those slots with the frozen v2 records and fills the remaining per-domain/type
quotas from non-duplicate generated candidates.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PER_DOMAIN_TYPE = {
    "SEC": {
        "DIRECT_RETRIEVAL": 25,
        "RETRIEVAL_CALCULATION": 40,
        "TEMPORAL_VERSION": 20,
        "ENTITY_UNIT_BINDING": 15,
        "UNANSWERABLE": 25,
    },
    "FDA": {
        "DIRECT_RETRIEVAL": 25,
        "RETRIEVAL_CALCULATION": 40,
        "TEMPORAL_VERSION": 15,
        "ENTITY_UNIT_BINDING": 20,
        "UNANSWERABLE": 25,
    },
    "CLINICAL_TRIALS": {
        "DIRECT_RETRIEVAL": 25,
        "RETRIEVAL_CALCULATION": 35,
        "TEMPORAL_VERSION": 0,
        "ENTITY_UNIT_BINDING": 40,
        "UNANSWERABLE": 25,
    },
    "FRED": {
        "DIRECT_RETRIEVAL": 25,
        "RETRIEVAL_CALCULATION": 35,
        "TEMPORAL_VERSION": 20,
        "ENTITY_UNIT_BINDING": 20,
        "UNANSWERABLE": 25,
    },
}

PREFIX = {"SEC": "SEC", "FDA": "FDA", "CLINICAL_TRIALS": "CT", "FRED": "FRED"}
DOMAIN_ORDER = {"SEC": 0, "FDA": 1, "CLINICAL_TRIALS": 2, "FRED": 3}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.open()]


def target_sig(family: dict[str, Any]) -> tuple[Any, ...]:
    records = family.get("target_conditions", {}).get("records") or []
    normalized = []
    for record in records:
        normalized.append(
            tuple(
                (key, str(record.get(key)))
                for key in ("entity_id", "concept", "period", "unit", "version")
                if record.get(key) is not None
            )
        )
    return (
        family["domain"],
        family["question_type"],
        family.get("answerable"),
        tuple(normalized),
        str(family.get("gold_answer_normalized")),
        family["question"],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    old = load_jsonl(args.old)
    candidates = load_jsonl(args.candidates)

    old_by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for family in old:
        old_by_domain[family["domain"]].append(family)
    for domain, families in old_by_domain.items():
        families.sort(key=lambda family: family["question_family_id"])
        if len(families) != 25:
            raise ValueError(f"{domain}: expected 25 frozen families, found {len(families)}")

    final: list[dict[str, Any]] = []
    used_questions = {family["question"] for family in old}
    used_signatures = {target_sig(family) for family in old}

    for domain in ("SEC", "FDA", "CLINICAL_TRIALS", "FRED"):
        final.extend(old_by_domain[domain])

    counts = Counter((family["domain"], family["question_type"]) for family in final)
    next_num = {domain: 26 for domain in PER_DOMAIN_TYPE}

    for domain in ("SEC", "FDA", "CLINICAL_TRIALS", "FRED"):
        for question_type, wanted in PER_DOMAIN_TYPE[domain].items():
            needed = wanted - counts[(domain, question_type)]
            added = 0
            pool = [
                family
                for family in candidates
                if family["domain"] == domain and family["question_type"] == question_type
            ]
            for family in pool:
                if added >= needed:
                    break
                if family["question"] in used_questions or target_sig(family) in used_signatures:
                    continue
                merged = json.loads(json.dumps(family))
                merged["question_family_id"] = f"{PREFIX[domain]}_{next_num[domain]:04d}"
                next_num[domain] += 1
                metadata = merged.get("generation_metadata") or {}
                metadata["notes"] = (
                    "500-family expansion candidate; ID remapped after preserving v2 families"
                )
                merged["generation_metadata"] = metadata
                final.append(merged)
                used_questions.add(merged["question"])
                used_signatures.add(target_sig(merged))
                counts[(domain, question_type)] += 1
                added += 1
            if added != needed:
                raise ValueError(
                    f"{domain} {question_type}: needed {needed}, added {added}, pool={len(pool)}"
                )

    final.sort(
        key=lambda family: (
            DOMAIN_ORDER[family["domain"]],
            int(family["question_family_id"].split("_")[1]),
        )
    )
    ids = [family["question_family_id"] for family in final]
    if len(final) != 500 or len(set(ids)) != 500:
        raise ValueError("merged family set is not exactly 500 unique IDs")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as handle:
        for family in final:
            handle.write(json.dumps(family, sort_keys=True, separators=(",", ":")) + "\n")

    old_by_id = {family["question_family_id"]: family for family in old}
    old_preserved = sum(
        1
        for family in final
        if family["question_family_id"] in old_by_id
        and family["question"] == old_by_id[family["question_family_id"]]["question"]
        and family["gold_answer"] == old_by_id[family["question_family_id"]]["gold_answer"]
        and family["target_conditions"] == old_by_id[family["question_family_id"]]["target_conditions"]
    )
    print("domain", Counter(family["domain"] for family in final))
    print("type", Counter(family["question_type"] for family in final))
    print("answerable", Counter(family["answerable"] for family in final))
    print("frozen_old_semantics_preserved", old_preserved)
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
