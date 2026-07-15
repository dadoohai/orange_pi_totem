# Board harness audit trail

Two independent reviews rejected earlier versions of the board QA harness
before the decisive run.

First review findings incorporated:

- identify the exact wizard process rather than the `openvt` wrapper;
- prove the presented state from framebuffer pixels, not only source SVG;
- make cleanup and final-state checks authoritative before emitting success;
- preserve config, context, network and player state;
- reject stale artifact directories and bind the input helper by SHA-256.

Second review findings incorporated:

- distinguish the Ethernet port shape from Wi-Fi bars;
- require the live adapter result to be exactly `ethernet` + `online`;
- observe distinct exact service-probe child PIDs during the session;
- bound upper duration, files, screens, threads, children, FDs and RSS;
- validate session cancellation proves no writer, config write or network
  mutation and that playback/MPV were restored;
- persist the small raw RGB region used by the pixel verdict.

The final visual and instrumented runs use the hardened scripts committed in
`scripts/qa/`. Earlier harness results are retained only where they prove the
separate 600-second resource observation; exact refresh-process proof comes
from the final 60-second run.
