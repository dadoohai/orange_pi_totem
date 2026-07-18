# Prod18 C26 build evidence

Date: 2026-07-18

This directory records a clean production-image build that was rejected by
the final semantic audit before any card was written.

- image: `c18-hwdecode-prod-18-c26`;
- version: `c18.image-prod.18-c26`;
- build commit: `50f808e412b3f70d8313ee731b63073a47458907`;
- image SHA256:
  `fbaf93d0438567f5312363415c9e6778c74ca1e8e9642c6e46f79f02b5ad0a4d`;
- current: `c26.7-local-recovery-20260718-01464f8-actions`;
- previous: `c26.5-local-recovery-20260718-f1d0da9-actions`;
- C18 release gate: `85/85`, no failed steps;
- offline image validation: green;
- extracted ext4 filesystem check: clean.

The current and previous slots have distinct versions and payload hashes. A
direct read of the built image confirmed both symlinks and exact state
records. Removing `previous` only from a copied filesystem made validation
fail on the two expected previous-slot checks.

Final verdict: **do not flash or distribute prod18**. C26.5 is a real previous
slot, but an invalid API URL can cross its destructive reset boundary and be
rejected only by the later revocation client. Independent probes also found
that C26.7 still accepts oversized or non-ASCII API keys and malformed host
grammar that can fail after local cleanup. The successor must embed two new,
distinct slots that share the corrected transport contract.

The production support credential and its CSPRNG provenance remain external
mode-0600 files. No credential plaintext is stored here.

Non-claim: this artifact was never written to a card and is not a candidate or
distribution baseline. It is retained only as negative build/audit evidence.
