# Implementation program recipe (summary)

Full recipe: `docs/ARTIFACT_RECIPES.md` (canonical).

Composed `ASSESS + SPECIFY`.

```text
ASSESS:  why program exists · current evidence · constraints · risk
SPECIFY: destination · work units · dependency graph · invariant set
         · acceptance criteria · stop conditions · deferred work
```

Programs stay shardable. Do not collapse locally closed work units into one
elegant narrative section if doing so damages downstream extraction. Each work
unit should be operatively intelligible from the unit plus its declared
dependencies.
