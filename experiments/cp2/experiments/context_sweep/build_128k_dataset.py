#!/usr/bin/env python3
"""Extend the frozen benchmark to 128K using its embedded authentic records.

The 64K rows are copied unchanged. Each 128K row starts from the corresponding frozen
82K row and adds unique, same-domain records harvested from other frozen 82K contexts.
The Qwen tokenizer and exact CP2 prompt determine the final rendered input length.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from common import extract_input_ids


HERE = Path(__file__).resolve().parent
REPOSITORY_ROOT = HERE.parents[3]
PARENT_NAME = "preproduction_llama32_3b_500f_6ctx_v1"
PARENT_DATASET_SHA256 = "dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6"
NEW_DATASET_NAME = "preproduction_qwen25_7b_500f_128k_v1"
MODEL_REPO = "Qwen/Qwen2.5-7B-Instruct-1M"
MODEL_REVISION = "e28526f7bb80e2a9c8af03b831a9af3812f18fba"
EXPECTED_FAMILIES = 500
TARGET_INPUT_TOKENS = 128 * 1024
MAX_NEW_TOKENS = 128
MAX_INPUT_TOKENS = TARGET_INPUT_TOKENS - MAX_NEW_TOKENS
MIN_INPUT_TOKENS = int(TARGET_INPUT_TOKENS * 0.98)
CONTEXT_LABELS = ("64K", "128K")
RECORD_RE = re.compile(r'(<RECORD id="([^"]+)"[^>]*>.*?</RECORD>)', re.S)
LINE_RE = re.compile(r"^([^:\n]+):\s*(.*)$")
BRACKET_RE = re.compile(r"\[([^\]]+)\]\s*$")
RESPONSE_FORMAT_INSTRUCTIONS = """Return only one short line:
ANSWER: <answer>

If the supplied records are insufficient, return exactly:
ANSWER: INSUFFICIENT_EVIDENCE

Do not output JSON. Do not output evidence IDs, citations, explanations, reasoning, booleans, or extra lines."""
METADATA_LABELS = {
    "accn": "accession",
    "fy": "fiscal_year",
    "fp": "fiscal_period",
    "arm_label": "arm",
    "outcome_measure": "outcome",
    "intervention_name": "intervention",
    "sponsor_name": "sponsor",
    "overall_status": "status",
}


@dataclass(frozen=True)
class RecordBlock:
    record_id: str
    display_id: str
    domain: str
    text: str
    fields: dict[str, str]
    distractor: dict[str, Any] | None


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            )
    temporary.replace(path)


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def dataset_sha256(dataset_dir: Path) -> str:
    digest = hashlib.sha256()
    prefix = f"data/{dataset_dir.name}"
    for name in ("question_families.jsonl", "instances.jsonl"):
        path = dataset_dir / name
        digest.update(f"{prefix}/{name}".encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


def git_commit() -> str:
    completed = subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("cannot finalize provenance: git rev-parse failed")
    return completed.stdout.strip()


def require_clean_repository() -> str:
    commit = git_commit()
    completed = subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("cannot finalize provenance: git status failed")
    if completed.stdout.strip():
        raise RuntimeError(
            "cannot finalize provenance from a dirty repository; commit or remove changes first"
        )
    return commit


def parse_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block.splitlines()[1:-1]:
        match = LINE_RE.match(line.strip())
        if match:
            fields[match.group(1).strip().lower()] = match.group(2).strip()
    for label, key in (("entity", "entity_id"), ("field", "concept")):
        match = BRACKET_RE.search(fields.get(label, ""))
        if match:
            fields[key] = match.group(1)
    return fields


def extract_blocks(instance: dict[str, Any]) -> list[RecordBlock]:
    mapping = instance["display_id_to_record_id"]
    distractors = {row["record_id"]: row for row in instance.get("distractors", [])}
    blocks = []
    for match in RECORD_RE.finditer(instance["context"]):
        text, display_id = match.group(1), match.group(2)
        record_id = mapping.get(display_id)
        if not record_id:
            raise RuntimeError(f"{instance['instance_id']}: no canonical mapping for {display_id}")
        blocks.append(
            RecordBlock(
                record_id=record_id,
                display_id=display_id,
                domain=instance["domain"],
                text=text,
                fields=parse_fields(text),
                distractor=distractors.get(record_id),
            )
        )
    if [block.record_id for block in blocks] != instance["context_record_ids"]:
        raise RuntimeError(f"{instance['instance_id']}: parsed record order mismatch")
    return blocks


def load_parent(source: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, list[RecordBlock]]]:
    families = list(iter_jsonl(source / "question_families.jsonl"))
    instances_path = source / "instances.jsonl"
    if len(families) != EXPECTED_FAMILIES:
        raise RuntimeError(f"expected 500 question families, observed {len(families)}")
    observed_hash = dataset_sha256(source)
    if observed_hash != PARENT_DATASET_SHA256:
        raise RuntimeError(
            f"parent dataset hash mismatch: expected {PARENT_DATASET_SHA256}, observed {observed_hash}"
        )
    selected: dict[str, dict[str, Any]] = {}
    pools: dict[str, dict[str, RecordBlock]] = {}
    counts = Counter()
    for row in iter_jsonl(instances_path):
        counts[row["context_length_label"]] += 1
        if row["context_length_label"] not in ("64K", "82K"):
            continue
        selected[row["instance_id"]] = row
        if row["context_length_label"] == "82K":
            pool = pools.setdefault(row["domain"], {})
            for block in extract_blocks(row):
                previous = pool.setdefault(block.record_id, block)
                if previous.text != block.text or previous.display_id != block.display_id:
                    raise RuntimeError(f"inconsistent embedded record: {block.record_id}")
    if any(counts[label] != EXPECTED_FAMILIES for label in ("64K", "82K")):
        raise RuntimeError(f"parent context accounting mismatch: {dict(counts)}")
    return families, selected, {domain: list(pool.values()) for domain, pool in pools.items()}


def normalize_value(value: Any) -> str:
    text = str(value).strip().casefold().replace(",", "")
    if text.endswith("%"):
        text = text[:-1].strip()
    try:
        return f"{float(text):.12g}"
    except ValueError:
        return " ".join(text.split())


def condition_matches(fields: dict[str, str], condition: dict[str, Any]) -> bool:
    for key in ("entity_id", "concept", "period", "unit", "version"):
        wanted = condition.get(key)
        if wanted is not None and fields.get(key) != str(wanted):
            return False
    for key, wanted in (condition.get("metadata_match") or {}).items():
        label = METADATA_LABELS.get(key, key)
        if fields.get(label) != str(wanted):
            return False
    return True


def core_target_matches(fields: dict[str, str], condition: dict[str, Any]) -> bool:
    """Conservatively match a target fact without version or metadata refinements."""
    compared = False
    for key in ("entity_id", "concept", "period"):
        wanted = condition.get(key)
        if wanted is None:
            continue
        compared = True
        if fields.get(key) != str(wanted):
            return False
    return compared


def safe_candidate(block: RecordBlock, family: dict[str, Any], existing: set[str]) -> bool:
    if block.record_id in existing or block.record_id in set(family.get("gold_evidence_ids", [])):
        return False
    conditions = family.get("target_conditions", {}).get("records") or []
    if any(
        condition_matches(block.fields, condition)
        or core_target_matches(block.fields, condition)
        for condition in conditions
    ):
        return False
    if family["answerable"]:
        value = block.fields.get("value")
        if value is not None and normalize_value(value) == normalize_value(
            family["gold_answer_normalized"]
        ):
            return False
    spec = family.get("unanswerable_spec")
    if spec:
        concept_aliases = set(spec.get("forbidden_concept_aliases") or [])
        if spec.get("missing_concept"):
            concept_aliases.add(spec["missing_concept"])
        if block.fields.get("concept") in concept_aliases:
            entity_matches = (
                spec.get("missing_entity_id") is None
                or block.fields.get("entity_id") == str(spec["missing_entity_id"])
            )
            period_matches = (
                spec.get("missing_period") is None
                or block.fields.get("period") == str(spec["missing_period"])
            )
            if entity_matches and period_matches:
                return False
    return True


def deterministic_candidates(
    pool: list[RecordBlock], family: dict[str, Any], existing: set[str]
) -> list[RecordBlock]:
    candidates = [block for block in pool if safe_candidate(block, family, existing)]
    family_id = family["question_family_id"]
    return sorted(
        candidates,
        key=lambda block: hashlib.sha256(
            f"20260812|{family_id}|{block.record_id}".encode("utf-8")
        ).digest(),
    )


def render_input_tokens(tokenizer, evaluation_prompt: str, context: str, question: str) -> list[int]:
    user = "\n\n".join(
        [
            "KNOWLEDGE RECORDS:",
            context,
            "TARGET QUESTION:",
            question,
            "OUTPUT FORMAT:",
            RESPONSE_FORMAT_INSTRUCTIONS,
        ]
    )
    messages = [
        {"role": "system", "content": evaluation_prompt},
        {"role": "user", "content": user},
    ]
    encoded = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=True)
    return extract_input_ids(encoded)


def block_token_count(tokenizer, block: RecordBlock, cache: dict[str, int]) -> int:
    cached = cache.get(block.record_id)
    if cached is None:
        cached = len(tokenizer.encode("\n" + block.text, add_special_tokens=False))
        cache[block.record_id] = cached
    return cached


def make_128k_instance(
    base: dict[str, Any],
    family: dict[str, Any],
    pool: list[RecordBlock],
    tokenizer,
    evaluation_prompt: str,
    token_costs: dict[str, int],
    model_context_limit: int,
) -> dict[str, Any]:
    base_blocks = extract_blocks(base)
    existing = {block.record_id for block in base_blocks}
    conditions = family.get("target_conditions", {}).get("records") or []
    gold_blocks = [
        block for block in base_blocks if block.record_id in set(base["gold_evidence_ids"])
    ]
    if family["answerable"] and (
        not gold_blocks
        or not all(
            any(core_target_matches(block.fields, condition) for condition in conditions)
            for block in gold_blocks
        )
    ):
        raise RuntimeError(
            f"{base['instance_id']}: embedded gold records do not match target core fields"
        )
    candidates = deterministic_candidates(pool, family, existing)
    if not candidates:
        raise RuntimeError(f"{base['instance_id']}: no safe extension records")

    gold = set(base["gold_evidence_ids"])
    gold_indexes = [index for index, block in enumerate(base_blocks) if block.record_id in gold]
    if bool(gold) != bool(gold_indexes):
        raise RuntimeError(f"{base['instance_id']}: gold evidence mapping mismatch")
    pivot = (
        (min(gold_indexes) + max(gold_indexes)) / 2
        if gold_indexes
        else (len(base_blocks) - 1) / 2
    )
    base_left = base_blocks[: int(pivot) + 1]
    base_right = base_blocks[int(pivot) + 1 :]
    added_left: list[RecordBlock] = []
    added_right: list[RecordBlock] = []
    left_tokens = right_tokens = 0
    initial_tokens = len(
        render_input_tokens(tokenizer, evaluation_prompt, base["context"], base["question"])
    )
    estimated = initial_tokens
    remaining: list[RecordBlock] = []
    for index, block in enumerate(candidates):
        cost = block_token_count(tokenizer, block, token_costs)
        if estimated + cost <= MAX_INPUT_TOKENS - 256:
            if left_tokens <= right_tokens:
                added_left.append(block)
                left_tokens += cost
            else:
                added_right.append(block)
                right_tokens += cost
            estimated += cost
        else:
            remaining.append(block)
        if estimated >= MAX_INPUT_TOKENS - 512:
            remaining.extend(candidates[index + 1 :])
            break

    def assembled() -> list[RecordBlock]:
        return [*reversed(added_left), *base_left, *base_right, *added_right]

    def rendered_count() -> tuple[str, int]:
        context = "\n".join(block.text for block in assembled())
        count = len(render_input_tokens(tokenizer, evaluation_prompt, context, base["question"]))
        return context, count

    context, input_tokens = rendered_count()
    while input_tokens > MAX_INPUT_TOKENS and (added_left or added_right):
        if left_tokens >= right_tokens and added_left:
            removed = added_left.pop()
            left_tokens -= block_token_count(tokenizer, removed, token_costs)
            remaining.insert(0, removed)
        elif added_right:
            removed = added_right.pop()
            right_tokens -= block_token_count(tokenizer, removed, token_costs)
            remaining.insert(0, removed)
        context, input_tokens = rendered_count()

    refinement_attempts = 0
    for block in remaining:
        if input_tokens >= MIN_INPUT_TOKENS:
            break
        cost = block_token_count(tokenizer, block, token_costs)
        if cost > MAX_INPUT_TOKENS - input_tokens + 32:
            continue
        refinement_attempts += 1
        if refinement_attempts > 50:
            break
        destination = added_left if left_tokens <= right_tokens else added_right
        destination.append(block)
        candidate_context, candidate_count = rendered_count()
        if candidate_count <= MAX_INPUT_TOKENS:
            context, input_tokens = candidate_context, candidate_count
            if destination is added_left:
                left_tokens += cost
            else:
                right_tokens += cost
        else:
            destination.pop()
    if not (MIN_INPUT_TOKENS <= input_tokens <= MAX_INPUT_TOKENS):
        raise RuntimeError(
            f"{base['instance_id']}: rendered input {input_tokens} is outside "
            f"{MIN_INPUT_TOKENS}..{MAX_INPUT_TOKENS}"
        )

    blocks = assembled()
    record_ids = [block.record_id for block in blocks]
    display_ids = [block.display_id for block in blocks]
    if len(record_ids) != len(set(record_ids)) or len(display_ids) != len(set(display_ids)):
        raise RuntimeError(f"{base['instance_id']}: duplicate extension records or display IDs")
    if not set(base["context_record_ids"]).issubset(record_ids):
        raise RuntimeError(f"{base['instance_id']}: frozen 82K records are not nested")

    gold_positions = [index for index, record_id in enumerate(record_ids) if record_id in gold]
    if gold_positions:
        prefix = "\n".join(block.text for block in blocks[: min(gold_positions)])
        gold_text = "\n".join(block.text for block in blocks[min(gold_positions) : max(gold_positions) + 1])
        start = len(tokenizer.encode(prefix + ("\n" if prefix else ""), add_special_tokens=False))
        end = start + len(tokenizer.encode(gold_text, add_special_tokens=False))
        context_tokens = len(tokenizer.encode(context, add_special_tokens=False))
        target_relative = ((start + end) / 2) / context_tokens
    else:
        start = end = None
        context_tokens = len(tokenizer.encode(context, add_special_tokens=False))
        target_relative = 0.5
    if abs(target_relative - 0.5) > 0.05:
        raise RuntimeError(
            f"{base['instance_id']}: target position {target_relative:.4f} is outside tolerance"
        )

    old_distractors = {row["record_id"]: row for row in base.get("distractors", [])}
    distractors = []
    counts = Counter()
    for position, block in enumerate(blocks):
        if block.record_id in gold:
            continue
        source = old_distractors.get(block.record_id)
        row = copy.deepcopy(source) if source else {
            "record_id": block.record_id,
            "display_id": block.display_id,
            "distractor_type": "OTHER_SAME_DOMAIN",
            "relationship_to_target": {},
        }
        row["record_id"] = block.record_id
        row["display_id"] = block.display_id
        row["position_index"] = position
        row["side"] = "before" if position < (gold_positions[0] if gold_positions else len(blocks) / 2) else "after"
        distractors.append(row)
        counts[row["distractor_type"]] += 1

    result = copy.deepcopy(base)
    result.update(
        {
            "instance_id": f"{family['question_family_id']}_128K",
            "context_length_nominal": TARGET_INPUT_TOKENS,
            "context_length_label": "128K",
            "context_tokens_actual": context_tokens,
            "tokenizer": MODEL_REPO,
            "tokenizer_version": None,
            "tokenizer_revision": MODEL_REVISION,
            "tokenizer_class": type(tokenizer).__name__,
            "model_id": MODEL_REPO,
            "model_config_revision": MODEL_REVISION,
            "rendered_input_tokens_actual": input_tokens,
            "prompt_overhead_tokens": input_tokens - context_tokens,
            "generation_tokens_reserved": MAX_NEW_TOKENS,
            "model_context_limit": model_context_limit,
            "remaining_context_margin": MAX_INPUT_TOKENS - input_tokens,
            "near_model_maximum": False,
            "prompt_version": "qwen25_cp_chat_v1",
            "prompt_hash": "80f8dce3d4e24ea9",
            "response_format_version": "answer_only_line_v1",
            "target_evidence_start_token": start,
            "target_evidence_end_token": end,
            "target_position_relative": target_relative,
            "target_position_relative_in_records_context": target_relative,
            "target_position_relative_in_rendered_input": None,
            "distractor_counts": dict(counts),
            "distractors": distractors,
            "context": context,
            "context_record_ids": record_ids,
            "context_display_ids": display_ids,
            "display_id_to_record_id": {
                block.display_id: block.record_id for block in blocks
            },
            "context_sha256": hashlib.sha256(context.encode("utf-8")).hexdigest(),
            "lineage": {
                "extends_instance_id": base["instance_id"],
                "extends_n_records": len(base_blocks),
                "added_record_ids": [
                    block.record_id for block in [*added_left, *added_right]
                ],
                "extension_method": "qwen_tokenized_authentic_same_domain_v1",
                "rendered_input_fill_ratio": input_tokens / TARGET_INPUT_TOKENS,
            },
            "stats": {
                "context_length_nominal": TARGET_INPUT_TOKENS,
                "context_length_label": "128K",
                "context_tokens_actual": context_tokens,
                "fill_ratio": context_tokens / TARGET_INPUT_TOKENS,
                "tokenizer_id": MODEL_REPO,
                "tokenizer_version": None,
                "n_records_total": len(blocks),
                "n_records_before_target": gold_positions[0] if gold_positions else len(blocks) // 2,
                "n_records_after_target": (
                    len(blocks) - gold_positions[-1] - 1
                    if gold_positions
                    else len(blocks) - len(blocks) // 2
                ),
                "target_evidence_start_token": start,
                "target_evidence_end_token": end,
                "target_position_relative": target_relative,
                "target_position_tolerance": 0.05,
                "target_position_ok": True,
                "rendered_input_tokens_actual": input_tokens,
                "prompt_overhead_tokens": input_tokens - context_tokens,
                "generation_tokens_reserved": MAX_NEW_TOKENS,
                "model_context_limit": model_context_limit,
                "remaining_context_margin": MAX_INPUT_TOKENS - input_tokens,
                "near_model_maximum": False,
            },
        }
    )
    return result


def finalize_config(
    template: Path,
    output: Path,
    dataset_digest: str,
    repository_commit: str,
    generation_digest: str,
) -> None:
    config = json.loads(template.read_text(encoding="utf-8"))
    benchmark = config["source_benchmark"]
    benchmark.update(
        {
            "name": NEW_DATASET_NAME,
            "repository_commit": repository_commit,
            "dataset_sha256": dataset_digest,
            "generation_code_sha256": generation_digest,
        }
    )
    output.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    workspace = Path(os.environ.get("CP_WORKSPACE", "/workspace/context-parallel-repro"))
    default_model = workspace / "models" / "qwen" / MODEL_REVISION
    parser = argparse.ArgumentParser(description="Build Qwen-tokenized 64K/128K CP2 inputs.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, default=default_model)
    parser.add_argument(
        "--cp2-template",
        type=Path,
        default=HERE / "experiment_config_64k_128k.template.json",
    )
    args = parser.parse_args()
    source, output, tokenizer_path = args.source.resolve(), args.out.resolve(), args.tokenizer.resolve()
    if source.name != PARENT_NAME:
        raise SystemExit(f"--source must be the directory named {PARENT_NAME}")
    if output.name != NEW_DATASET_NAME:
        raise SystemExit(f"--out must be a directory named {NEW_DATASET_NAME}")
    if not tokenizer_path.is_dir():
        raise SystemExit(
            f"staged Qwen tokenizer/model is missing: {tokenizer_path}; run stage_model.py first"
        )

    repository_commit = require_clean_repository()
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, local_files_only=True)
    model_config_path = tokenizer_path / "config.json"
    if not model_config_path.is_file():
        raise RuntimeError(f"staged Qwen config is missing: {model_config_path}")
    model_config = json.loads(model_config_path.read_text(encoding="utf-8"))
    model_context_limit = int(model_config.get("max_position_embeddings", 0))
    if model_context_limit < TARGET_INPUT_TOKENS:
        raise RuntimeError(
            f"Qwen model context limit {model_context_limit} is below {TARGET_INPUT_TOKENS}"
        )
    evaluation_prompt = (HERE / "evaluation_v1.txt").read_text(encoding="utf-8")
    families, parent, pools = load_parent(source)
    family_by_id = {row["question_family_id"]: row for row in families}
    output.mkdir(parents=True, exist_ok=True)

    rows_64k = []
    generation_digest = normalized_sha256(Path(__file__))
    partial_path = output / (
        f"128k.{generation_digest[:12]}.{repository_commit[:12]}.partial.jsonl"
    )
    partial_rows = list(iter_jsonl(partial_path)) if partial_path.is_file() else []
    rows_128k = {
        row["question_family_id"]: row
        for row in partial_rows
        if row.get("context_length_label") == "128K"
    }
    if len(rows_128k) != len(partial_rows):
        raise RuntimeError(f"invalid or duplicate partial rows: {partial_path}")
    unexpected_partial = sorted(set(rows_128k) - set(family_by_id))
    if unexpected_partial:
        raise RuntimeError(
            f"partial file contains unknown families: {unexpected_partial[:20]}"
        )
    token_costs: dict[str, int] = {}
    for index, family in enumerate(families, 1):
        family_id = family["question_family_id"]
        row_64k = parent.get(f"{family_id}_64K")
        row_82k = parent.get(f"{family_id}_82K")
        if not row_64k or not row_82k:
            raise RuntimeError(f"{family_id}: frozen 64K or 82K parent is missing")
        rows_64k.append(row_64k)
        if family_id not in rows_128k:
            extended = make_128k_instance(
                row_82k,
                family_by_id[family_id],
                pools[family["domain"]],
                tokenizer,
                evaluation_prompt,
                token_costs,
                model_context_limit,
            )
            metadata = dict(extended.get("generation_metadata") or {})
            metadata.update(
                {
                    "git_commit": repository_commit,
                    "generated_at": None,
                    "tokenizer_id": MODEL_REPO,
                    "notes": "Qwen-tokenized 128K extension from frozen authentic records",
                }
            )
            extended["generation_metadata"] = metadata
            with partial_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    json.dumps(
                        extended,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                handle.flush()
                os.fsync(handle.fileno())
            rows_128k[family_id] = extended
        if index % 10 == 0 or index == len(families):
            print(
                f"prepared {index}/{len(families)} 128K extensions "
                f"({len(rows_128k)} persisted)",
                flush=True,
            )

    published = [
        row
        for pair in zip(
            sorted(rows_64k, key=lambda row: row["question_family_id"]),
            sorted(rows_128k.values(), key=lambda row: row["question_family_id"]),
        )
        for row in pair
    ]
    if len(rows_128k) != EXPECTED_FAMILIES:
        raise RuntimeError(
            f"expected 500 completed 128K families, observed {len(rows_128k)}"
        )
    if len(published) != 2 * EXPECTED_FAMILIES:
        raise RuntimeError(f"expected 1,000 published rows, observed {len(published)}")
    write_jsonl(output / "question_families.jsonl", families)
    write_jsonl(output / "instances.jsonl", published)
    digest = dataset_sha256(output)
    if require_clean_repository() != repository_commit:
        raise RuntimeError("repository commit changed during dataset construction")
    finalized_config = output / "cp2_experiment_config.json"
    finalize_config(
        args.cp2_template.resolve(),
        finalized_config,
        digest,
        repository_commit,
        generation_digest,
    )
    counts = Counter(row["context_length_label"] for row in published)
    report = {
        "status": "PASS",
        "dataset": NEW_DATASET_NAME,
        "dataset_sha256": digest,
        "parent_dataset_sha256": PARENT_DATASET_SHA256,
        "families": len(families),
        "instances": len(published),
        "instances_by_context": dict(counts),
        "frozen_64k_rows_preserved": True,
        "new_128k_instances": len(rows_128k),
        "128k_definition": "Qwen-rendered input tokens, including prompt, question, and chat template",
        "128k_input_range": [MIN_INPUT_TOKENS, MAX_INPUT_TOKENS],
        "extension_records": "unique authentic same-domain records harvested from frozen 82K contexts",
        "tokenizer": MODEL_REPO,
        "tokenizer_revision": MODEL_REVISION,
        "generation_code_sha256": generation_digest,
        "repository_commit": repository_commit,
        "cp2_experiment_config": str(finalized_config),
    }
    (output / "extension_manifest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    partial_path.unlink()
    print(json.dumps(report, indent=2))
    print("64K/128K DATASET PREPARATION COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
