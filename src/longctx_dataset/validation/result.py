"""Validation result containers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

MAX_RECORDED_FAILURES = 25
"""Failures are capped per check so a systemic bug cannot produce a gigabyte of report."""


class Severity:
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class CheckResult:
    check_id: str
    name: str
    severity: str
    n_checked: int = 0
    failures: List[Dict[str, Any]] = field(default_factory=list)
    n_failed: int = 0
    message: str = ""
    skipped: bool = False
    skip_reason: Optional[str] = None

    def fail(self, **detail: Any) -> None:
        self.n_failed += 1
        if len(self.failures) < MAX_RECORDED_FAILURES:
            self.failures.append(detail)

    @property
    def passed(self) -> bool:
        return self.n_failed == 0 and not self.skipped

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "severity": self.severity,
            "passed": self.passed,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "n_checked": self.n_checked,
            "n_failed": self.n_failed,
            "message": self.message,
            "failures_truncated": self.n_failed > len(self.failures),
            "failures": self.failures,
        }


@dataclass
class ValidationReport:
    dataset_name: str
    checks: List[CheckResult] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    def add(self, check: CheckResult) -> CheckResult:
        self.checks.append(check)
        return check

    def has_critical_failures(self) -> bool:
        return any(c.severity == Severity.CRITICAL and not c.passed and not c.skipped for c in self.checks)

    def has_warnings(self) -> bool:
        return any(c.severity == Severity.WARNING and not c.passed and not c.skipped for c in self.checks)

    def counts(self) -> Dict[str, int]:
        return {
            "total": len(self.checks),
            "passed": sum(1 for c in self.checks if c.passed),
            "failed": sum(1 for c in self.checks if not c.passed and not c.skipped),
            "skipped": sum(1 for c in self.checks if c.skipped),
            "critical_failed": sum(
                1 for c in self.checks
                if c.severity == Severity.CRITICAL and not c.passed and not c.skipped
            ),
            "warning_failed": sum(
                1 for c in self.checks
                if c.severity == Severity.WARNING and not c.passed and not c.skipped
            ),
        }

    def one_line(self) -> str:
        c = self.counts()
        return (
            f"{c['passed']}/{c['total']} checks passed, {c['critical_failed']} critical failures, "
            f"{c['warning_failed']} warnings, {c['skipped']} skipped"
        )

    def summary_text(self) -> str:
        lines = ["", "  check                                                        result"]
        lines.append("  " + "-" * 74)
        for c in sorted(self.checks, key=lambda x: x.check_id):
            if c.skipped:
                status = "SKIP"
            elif c.passed:
                status = "PASS"
            else:
                status = f"FAIL({c.severity[:4]})"
            name = f"{c.check_id}. {c.name}"
            lines.append(f"  {name:<58} {status:>8} {c.n_failed}/{c.n_checked}")
            if not c.passed and c.message:
                lines.append(f"       -> {c.message}")
        lines.append("  " + "-" * 74)
        lines.append(f"  {self.one_line()}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "counts": self.counts(),
            "has_critical_failures": self.has_critical_failures(),
            "stats": self.stats,
            "checks": [c.to_dict() for c in sorted(self.checks, key=lambda x: x.check_id)],
        }
