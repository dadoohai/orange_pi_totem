# C18 totem-core stable promotion

Evidence created at 2026-07-05T18:40:13Z for the production auto-pull path of
`totem-core`.

Scope:

- authorizes only `totem-core` stable auto-pull;
- binds the decision to production image `c18-hwdecode-prod-1`;
- keeps rollback responsibility explicit;
- does not publish a release by itself;
- does not thaw `player-runtime`;
- does not authorize `player-runtime` stable;
- does not update `media-system`;
- still requires board validation of the production image and timer.

