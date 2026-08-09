"""Validation suite. Critical failures make the CLI exit nonzero."""

from .result import CheckResult, Severity, ValidationReport  # noqa: F401

__all__ = ["CheckResult", "Severity", "ValidationReport"]
