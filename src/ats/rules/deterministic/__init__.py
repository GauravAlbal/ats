"""Deterministic detectors for ATS-1 rules, evaluated over TextIR.

Each module registers detectors through :func:`register`. A detector receives an
:class:`~ats.ir.model.IrEvaluation` and returns exactly one
:class:`~ats.rules.results.RuleResult`, always built through
:func:`~ats.rules.results.decide` so that no detector can hand itself a PASS it
did not earn.
"""

from __future__ import annotations

from typing import Callable, Iterable, Protocol

from ...rules.results import RuleResult


class IrDetector(Protocol):
    """The detector calling convention."""

    rule_id: str

    def __call__(self, ev: "IrEvaluation") -> RuleResult:  # noqa: F821
        ...


#: rule_id -> detector callable. Populated by the modules imported below.
DETECTORS: dict[str, IrDetector] = {}


def register(rule_id: str) -> Callable[[Callable], Callable]:
    """Decorator binding a detector function to its rule id."""

    def wrap(fn: Callable) -> Callable:
        if rule_id in DETECTORS:
            raise RuntimeError(f"duplicate detector registration for {rule_id}")
        fn.rule_id = rule_id  # type: ignore[attr-defined]
        DETECTORS[rule_id] = fn  # type: ignore[assignment]
        return fn

    return wrap


def load_detectors(rule_ids: Iterable[str] | None = None) -> dict[str, IrDetector]:
    """Import every detector module and return the populated registry.

    Every module registers its detectors as a side effect of import. When
    ``rule_ids`` is given, only the detectors whose rule id is in it are
    returned; the lint call site passes the active context's registry ids, so
    each normative edition sees exactly its own rule set.
    """
    from . import (  # noqa: F401
        basis,
        closure,
        coordinates,
        deontics,
        discourse,
        epistemics,
        evidence,
        preservation,
        quantity,
        reference,
        requirements,
        requirements_draft3,
        terminology,
        time_rules,
    )

    if rule_ids is None:
        return DETECTORS
    wanted = set(rule_ids)
    return {rid: fn for rid, fn in DETECTORS.items() if rid in wanted}
