# ATS Adjudication Bench

## Register

product — a tool. Design serves the task and disappears into it.

## What this is

The public corpus layer defines a staged, two-pass adjudication protocol for
caller-supplied artifacts. A source-only view keeps instrument conclusions and
revision material withheld; a disagreement-review view unlocks only after the
source-only record exists. Validated judgments are sealed into append-only gold
records, and the corpus modules own the refusal rules. The public tree
contains reusable mechanics and synthetic fixtures, not private corpus payloads
or pilot results.

## Who uses it

Maintainers and integrators use the corpus layer to inspect reproducible
fixtures or their own authorized artifacts. The code does not assume a
particular operator, repository, or private data source.

## The scene sentence

A reviewer reads a bounded technical artifact and must keep the source-only
decision separate from later instrument evidence, so the reading surface keeps
the source and its context primary while the adjudication state remains
explicit.

## What the design must protect

- **The blinding is law.** Source-only surfaces never contain instrument
  conclusions, selector signals, or revision material. The contract is enforced
  before display rather than by hiding bytes.
- **The reviewer's words are the record.** Rationale fields are retained in
  validated gold records; they are not silently truncated or templated.
- **No steering.** Vocabulary options are presented with their glosses
  evenhandedly, in fixed order, without privileging an outcome.
- **Reading is the work.** Source artifact, containing context, and explicit
  adjudication state remain primary; forms are secondary.


## Anti-references

- Dashboard-ware: metric heroes, card grids, progress gamification.
- Annotation-farm UIs (Mechanical Turk, Label Studio): pace pressure, timers,
  batch-completion nudges. This tool must never rush a judgment.
- Anything that looks like the instruments' opinion leaked into the layout.

## Strategic principles

1. Familiar affordances, judicial tone: closer to reading a well-typeset case
   file than operating a console.
2. Keyboard-reachable, mouse-optional; but no shortcut ever submits a
   judgment without an explicit confirm.
3. State lives in the gold file on disk. The browser holds nothing worth
   losing; a refresh always resumes exactly.
