"""The ATS-1 corpus pipeline (spec Sections 12.9, 17, and 18).

``records``
    Typed constructors, content addressing, and append-only JSONL storage for
    the five corpus record types.
``inventory``
    Local Git inventory of source documents. Read-only, never networked.
``authority``
    Per-use corpus authority, resolved by intersection. Absence never inherits
    permission.
``authorship``
    Who authored a document: declared, never inferred. ``unknown`` is the
    default and the only value reachable without explicit evidence.
``acceptance``
    Whether an authority accepted a document: decided, never derived from
    topology. ``unknown`` is the default and the only state reachable without
    an authoritative artifact; merge structure, deletion, and Git's revert
    marker are observed and promote nothing.
``context``
    Context bundles: the minimum an annotator needs to adjudicate one span.
``mine``
    Deterministic candidate extraction, and the three inferences Section 17.4
    refuses to make.
``mutate``
    The 22 synthetic mutation operators, one semantic feature at a time.
``annotate``
    Blind annotation queues and the two-independent-judgment floor.
``adjudicate``
    Resolution of judgments into an adjudication, with disagreement retained.
``split``
    Deterministic, leakage-grouped splits. Never a random sentence split.
``stats``
    Coverage, agreement, and gold eligibility, with synthetic and natural
    evidence reported separately and never summed.
``coverage``
    Per-rule mining coverage, with a derived mechanism attached to every rule
    that received no candidate. Counts are diagnostic, never a target.
``profile``
    Section-scoped profile hypotheses. A hypothesis, never an inference from a
    filename.
``receipt``
    Receipts for inventory and authority observations at caller-supplied
    revisions.
``frame``
    The stratified sampling frame over a caller-supplied corpus, with its
    constraints evaluated rather than asserted.
``round``
    One round of blind annotation over a frozen frame. A round never writes
    back to the frame it drew from.
``agreement``
    The agreement vector, per-rule confusion, and declines that would
    otherwise vanish between two metrics. No overall score exists.
``recon``
    Profile-reconnaissance helpers over caller-supplied context bundles.
``gold``
    Operator adjudication: the queue, the two-pass discipline, and
    caller-supplied gold. A third model vote is refused by construction.
``validity``
    Each annotation instrument scored against caller-supplied gold. Validity
    and reproducibility are named separately and never pooled.
"""
