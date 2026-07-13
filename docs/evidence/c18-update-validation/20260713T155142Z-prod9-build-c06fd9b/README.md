# C18 production image prod9 build

Offline build and direct artifact inspection for the first image candidate
that attempted to consolidate the C25 visible-state work and the exact C25B
player-runtime. This candidate was rejected by independent forensic review.

## Result - BLOCKED / DO NOT FLASH

- image: `c18-hwdecode-prod-9` / `c18.image-prod.9`
- repo commit: `c06fd9b510457f6721be6307aceba3bd1f83c492`
- image SHA256: `4a413bc84d76de045a4e0884a1b1f60db962823e2bdca042e31e17feaee0c050`
- image bytes: `1971322880`
- embedded core: `c25.3-reference-image-20260713-562939e`
- embedded player fallback: `c18.player-runtime-homolog-20260713-c25b-still-fix-54308e4`
- source release gate: `82/82`
- offline image validation: passed, `54/54`
- direct rootfs composition checks: passed, `151/151`
- allocated-file privacy scan: passed, but insufficient and superseded
- filesystem check: clean
- first 4 MiB boot region: byte-identical to the pinned base image

The real image filesystem contains the intended C25 core, exact C25B fallback
and authorization, updater hooks, required media binaries and fonts. However,
the initial scan inspected only allocated files. Independent forensic review
then recovered deleted lab secrets and old SSH host keys from unallocated ext4
blocks. It also found an ambiguous inactive `overlayroot=tmpfs` configuration,
volatile SSH identity if that overlay ever activates, permissive artifact file
mode and stale player provenance metadata.

The image file was removed from the normal `.img` path, renamed with
`.blocked-do-not-flash` and restricted to mode `0600`. Prod9 is preserved only
as negative evidence. The next candidate must zero all free filesystem blocks,
disable the unshipped overlayroot path explicitly, prove persistent device SSH
identity, correct provenance metadata and enforce restricted artifact modes.

## Scope

This evidence does not approve a board flash, publication or distribution. The
exact C25B remote release was intentionally not published.

The source gate and the first offline validator remain useful source/composition
evidence, but neither proves privacy or hardware behavior. Prod8 remains the
distribution reference.
