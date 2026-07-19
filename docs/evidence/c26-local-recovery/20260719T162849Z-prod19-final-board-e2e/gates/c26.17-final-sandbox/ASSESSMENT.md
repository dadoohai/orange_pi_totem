# C26.17 first sandbox replay assessment

The first post-publication replay used the sandbox default
`<repo>/.sim/totem`, which is a shared mutable path. It returned
`apply_local_failed` without changing `current`.

This result is retained as a negative, but it is not attributed to the release:

1. an immediate direct apply in a fresh `/tmp` sandbox returned zero and
   completed package health;
2. the full replay was repeated with a unique `/tmp` sandbox;
3. that isolated replay passed apply, wrapper checks, rollback, channel guard,
   settings-session guard and final reapply.

Canonical isolated result:
`../c26.17-final-sandbox-isolated/totem-core-sandbox.json`.

Operational lesson: parallel QA must never share the default `.sim/totem`
state. The failed record remains evidence of test-harness contention, not a
green release artifact.
