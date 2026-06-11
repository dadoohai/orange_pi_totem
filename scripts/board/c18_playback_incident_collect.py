#!/usr/bin/env python3
"""Collect a read-only C18 playback incident bundle.

This wrapper reuses the deep-health collector and adds sanitized incident
metadata plus journal signatures. It is intended for intermittent same-media
loops such as: normal playback -> one media loops/freezes -> recovery/reset ->
normal playback -> same media loops again.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import c18_playback_health_collect as health_collect


SCHEMA = "dadooh.c18.playback.incident.v1"
COLLECTOR_VERSION = 1
DEFAULT_OUTPUT_ROOT = Path("/data/e")
VISIBLE_RECOVERY_CHOICES = ("startup_screen", "black_flash", "freeze_loop", "service_restart", "unknown")
SIGNATURE_RE = re.compile(
    r"media_load_failed|Failed to load media|MPV loadfile|command=loadfile|"
    r"MPV IPC unresponsive|MPV IPC ping failed|Restarting MPV|MPV process started|"
    r"Playing media alias=|Dadooh iniciando player|Iniciando player|"
    r"hwdec-current=no|v4l2request-copy|panfrost|drm|gpu|mmc|EXT4|thermal|oom|hung|reset",
    re.I,
)
URL_RE = re.compile(r"https?://\S+")
PRIVATE_IP_RE = re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b")
MAC_RE = re.compile(r"\b[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}\b")
SECRET_RE = re.compile(r"(github_pat_|gh[opsu]_|Bearer\s+\S+|api[_-]?key[=:]\S+|token[=:]\S+)", re.I)


def timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def compact_timestamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def sha1_short(value: Any) -> str:
    return health_collect.sha1_short(value)


def redact_line(line: str, observed_label: str | None) -> str:
    out = line.rstrip("\n")
    if observed_label:
        out = out.replace(observed_label, "<operator-observed-label>")
    out = URL_RE.sub("<url>", out)
    out = PRIVATE_IP_RE.sub("<private-ip>", out)
    out = MAC_RE.sub("<mac>", out)
    out = SECRET_RE.sub("<secret>", out)
    out = re.sub(r"/data/media/[^\s\"']+", "<media-path>", out)
    return out


def run_capture(argv: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def boot_state() -> dict[str, Any]:
    try:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
    except OSError:
        boot_id = ""
    try:
        uptime = float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
    except (OSError, ValueError, IndexError):
        uptime = None
    return {"boot_id_present": bool(boot_id), "uptime_sec": uptime}


def collect_health(args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    health_args = SimpleNamespace(
        duration_sec=args.duration_sec,
        interval_sec=args.interval_sec,
        ipc_timeout_sec=args.ipc_timeout_sec,
        output_dir=output_dir / "deep-health",
        target_mode="service",
        candidate_pid=None,
        service=args.service,
        app_user=args.app_user,
        config=args.config,
        status=args.status,
        match_process_ipc=args.match_process_ipc,
        process_ipc_path=args.process_ipc_path,
        mpv_log=args.mpv_log,
        mpv_generation_dir=args.mpv_generation_dir,
        panfrost_fault_policy=args.panfrost_fault_policy,
    )
    _, result = health_collect.collect(health_args)
    return result


def make_run_dir(output_dir: Path, event: str | None) -> Path:
    event_name = event or "snapshot"
    run_id = f"{compact_timestamp()}-{time.time_ns()}-{event_name}"
    return output_dir / "runs" / run_id


def classify_playlist(args: argparse.Namespace, output_dir: Path) -> dict[str, Any] | None:
    if not args.classify_playlist:
        return None
    script = Path(__file__).with_name("classify_playlist_media.sh")
    if not script.exists():
        return {"returncode": None, "error": "classify_playlist_media_missing"}
    env = os.environ.copy()
    env["TOTEM_DIAG_BASE"] = str(output_dir / "playlist-classification")
    proc = subprocess.run(
        ["bash", str(script)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
        env=env,
    )
    (output_dir / "classification.stdout.txt").write_text(proc.stdout, encoding="utf-8", errors="replace")
    (output_dir / "classification.stderr.txt").write_text(proc.stderr, encoding="utf-8", errors="replace")
    return {"returncode": proc.returncode, "base_dir": env["TOTEM_DIAG_BASE"]}


def journal_text(args: argparse.Namespace) -> list[tuple[str, str]]:
    captures: list[tuple[str, str]] = []
    commands = (
        ("service", ["journalctl", "-b", "-u", args.service, "--no-pager", "--output=short-iso"]),
        ("kernel", ["journalctl", "-k", "-b", "--no-pager", "--output=short-iso"]),
    )
    for source, cmd in commands:
        try:
            proc = run_capture(cmd, timeout=120)
            captures.append((source, proc.stdout + proc.stderr))
        except Exception as exc:
            captures.append((source, f"journal_capture_error:{type(exc).__name__}"))
    return captures


def collect_journal_signatures(args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    signatures_path = output_dir / "journal-signatures.ndjson"
    count = 0
    with signatures_path.open("w", encoding="utf-8") as fh:
        for source, text in journal_text(args):
            for line in text.splitlines():
                if not SIGNATURE_RE.search(line):
                    continue
                count += 1
                fh.write(json.dumps({
                    "source": source,
                    "line": redact_line(line, args.operator_observed_label),
                }, sort_keys=True) + "\n")
    return {"path": str(signatures_path), "count": count}


def append_operator_event(output_dir: Path, event: str | None, note: str | None) -> dict[str, Any] | None:
    if not event:
        return None
    path = output_dir / "operator-events.tsv"
    if not path.exists():
        path.write_text("utc\tevent\tnote_hash\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"{timestamp()}\t{event}\t{sha1_short(note) if note else ''}\n")
    return {"path": str(path), "event": event}


def collect(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = args.output_dir or (args.output_root / f"c18-playback-incident-{compact_timestamp()}")
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = make_run_dir(output_dir, args.operator_event)
    run_dir.mkdir(parents=True, exist_ok=False)
    try:
        os.chmod(output_dir, 0o700)
        os.chmod(run_dir, 0o700)
    except OSError:
        pass

    started_at = timestamp()
    boot_start = boot_state()
    operator_event = append_operator_event(output_dir, args.operator_event, args.operator_note)
    health_result = collect_health(args, run_dir)
    signatures = collect_journal_signatures(args, run_dir)
    classification = classify_playlist(args, run_dir)
    boot_end = boot_state()
    ended_at = timestamp()

    run_summary = {
        "schema": SCHEMA,
        "collector_version": COLLECTOR_VERSION,
        "passed": True,
        "result_claim": "read_only_playback_incident_evidence_collected",
        "output_dir": str(output_dir),
        "run_dir": str(run_dir),
        "run_id": run_dir.name,
        "started_wall_time": started_at,
        "ended_wall_time": ended_at,
        "duration_sec": args.duration_sec,
        "interval_sec": args.interval_sec,
        "boot": {
            "boot_id_present": boot_start["boot_id_present"] and boot_end["boot_id_present"],
            "uptime_start_sec": boot_start["uptime_sec"],
            "uptime_end_sec": boot_end["uptime_sec"],
        },
        "operator": {
            "observed_label_hash": sha1_short(args.operator_observed_label) if args.operator_observed_label else "",
            "observed_label_redacted": "<operator-observed-label>" if args.operator_observed_label else "",
            "loop_count": args.operator_loop_count,
            "visible_recovery": args.operator_visible_recovery,
            "event": operator_event,
        },
        "deep_health": {
            "path": str(run_dir / "deep-health" / "playback-deep-health-public.json"),
            "passed": health_result.get("passed"),
            "failure_reasons": health_result.get("failure_reasons"),
            "counters": health_result.get("counters"),
        },
        "journal_signatures": signatures,
        "classification": classification,
        "non_claims": [
            "root_cause_proven_without_log_review",
            "production_readiness",
            "stable_promotion",
            "public_player_runtime_thaw",
        ],
    }
    write_json(run_dir / "incident-summary.json", run_summary)
    aggregate = {
        "schema": SCHEMA,
        "collector_version": COLLECTOR_VERSION,
        "passed": True,
        "result_claim": "read_only_playback_incident_evidence_collected",
        "output_dir": str(output_dir),
        "latest_run": run_summary,
        "runs": sorted(path.name for path in (output_dir / "runs").iterdir() if path.is_dir()),
        "operator_events": str(output_dir / "operator-events.tsv"),
        "non_claims": run_summary["non_claims"],
    }
    write_json(output_dir / "incident-summary.json", aggregate)
    return aggregate


def self_test() -> None:
    label = "Flor Bela Decoracoes"
    line = "2026 x http://example.test/a 192.168.1.2 aa:bb:cc:dd:ee:ff token=abc Flor Bela Decoracoes /data/media/kiosky-player/a.mp4"
    redacted = redact_line(line, label)
    for forbidden in ("http://", "192.168.", "aa:bb", "token=abc", label, "/data/media/"):
        if forbidden in redacted:
            raise AssertionError(f"redaction failed for {forbidden}")
    if sha1_short(label) == label:
        raise AssertionError("hash helper did not hash")
    if "startup_screen" not in VISIBLE_RECOVERY_CHOICES:
        raise AssertionError("missing visible recovery choice")
    tmp = Path(os.environ.get("TMPDIR", "/tmp")) / f"c18-incident-self-test-{os.getpid()}"
    first = make_run_dir(tmp, "loop_entered")
    second = make_run_dir(tmp, "loop_reentered")
    if first == second or first.parent != second.parent or first.parent.name != "runs":
        raise AssertionError("run dirs must be unique under runs/")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--duration-sec", type=float, default=300.0)
    parser.add_argument("--interval-sec", type=float, default=1.0)
    parser.add_argument("--ipc-timeout-sec", type=float, default=0.8)
    parser.add_argument("--service", default=health_collect.DEFAULT_SERVICE)
    parser.add_argument("--app-user", default=health_collect.DEFAULT_APP_USER)
    parser.add_argument("--config", type=Path, default=health_collect.DEFAULT_CONFIG)
    parser.add_argument("--status", type=Path, default=health_collect.DEFAULT_STATUS)
    parser.add_argument("--match-process-ipc", action="store_true")
    parser.add_argument("--process-ipc-path", type=Path, default=None)
    parser.add_argument("--mpv-log", type=Path, default=health_collect.DEFAULT_MPV_LOG)
    parser.add_argument("--mpv-generation-dir", type=Path, default=health_collect.DEFAULT_MPV_GENERATION_DIR)
    parser.add_argument("--panfrost-fault-policy", choices=("absolute", "delta"), default="delta")
    parser.add_argument("--classify-playlist", action="store_true")
    parser.add_argument("--operator-observed-label", default=None, help="Raw label is hashed/redacted in outputs.")
    parser.add_argument("--operator-loop-count", type=int, default=None)
    parser.add_argument("--operator-visible-recovery", choices=VISIBLE_RECOVERY_CHOICES, default="unknown")
    parser.add_argument("--operator-event", choices=("loop_entered", "loop_recovered", "loop_reentered", "startup_screen_seen", "service_reset_seen"), default=None)
    parser.add_argument("--operator-note", default=None, help="Only a hash of this note is persisted.")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.self_test:
        self_test()
        print(json.dumps({"self_test": True, "schema": SCHEMA}, sort_keys=True))
        return 0
    try:
        result = collect(args)
    except Exception as exc:
        payload = {
            "schema": SCHEMA,
            "passed": False,
            "failure_reasons": ["incident_collector_failed"],
            "collector_error": type(exc).__name__,
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"incident_collector_failed:{type(exc).__name__}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"output_dir={result['output_dir']}")
        print("incident_summary=incident-summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
