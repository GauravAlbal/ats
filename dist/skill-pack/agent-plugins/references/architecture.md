# Architecture recipe (summary)

Full recipe: `docs/ARTIFACT_RECIPES.md` (canonical).

Composed `ASSESS + SPECIFY`.

```text
ASSESS:  current state · evidence · problem · constraints · alternatives
         · judgment · unresolved points
SPECIFY: target state · authority boundary · requirements · dependencies
         · failure behavior · migration · acceptance · update indicators
```

Recoverable roles: what the current system does (observation) vs what the
target must do (requirement) vs why this target was chosen (judgment).

Rules: stable coordinates only where they pay for themselves; local semantic
closure for extractable units; unknown stays unknown; transformation never
strengthens; new authoring may use AUTHOR_JUDGMENT under granted authority.
