#!/usr/bin/env python3
"""Run deterministic offline fault scenarios against the governed kiosk.py.

The campaign loads player-runtime/kiosky-player/kiosk.py directly and replaces
network, sleep, free-space checks, telemetry, and image transcode process calls
with local fakes. The JSON report intentionally exposes aliases instead of raw
URLs or temporary filesystem paths.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
KIOSK_PATH = REPO_ROOT / "player-runtime" / "kiosky-player" / "kiosk.py"
SCHEMA = "dadooh.c22.player_fault_campaign.v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def alias(value: object, prefix: str = "alias") -> str:
    raw = str(value or "")
    return f"{prefix}-{hashlib.sha1(raw.encode('utf-8'), usedforsecurity=False).hexdigest()[:12]}"


def load_kiosk_module():
    spec = importlib.util.spec_from_file_location("c22_kiosk_fault_campaign", KIOSK_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load kiosk module: {KIOSK_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        json_data: dict[str, Any] | None = None,
        body: bytes = b"",
        headers: dict[str, str] | None = None,
        json_error: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self._body = body
        self.headers = dict(headers or {})
        self._json_error = json_error

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        if self._json_error is not None:
            raise self._json_error
        return self._json_data

    def iter_content(self, chunk_size: int) -> Any:
        for offset in range(0, len(self._body), chunk_size):
            yield self._body[offset : offset + chunk_size]


class FakeRequests:
    def __init__(self) -> None:
        self.post_responses: list[FakeResponse] = []
        self.get_responses: dict[str, FakeResponse] = {}
        self.post_calls = 0
        self.get_calls: list[str] = []

    def queue_api(self, playlist: list[dict[str, Any]]) -> None:
        self.post_responses.append(FakeResponse(json_data=api_payload(playlist)))

    def post(self, *_args: Any, **_kwargs: Any) -> FakeResponse:
        self.post_calls += 1
        if not self.post_responses:
            raise RuntimeError("unexpected API request in offline harness")
        return self.post_responses.pop(0)

    def get(self, url: str, *_args: Any, **_kwargs: Any) -> FakeResponse:
        self.get_calls.append(url)
        response = self.get_responses.get(url)
        if response is None:
            raise RuntimeError("unexpected media request in offline harness")
        return response


def api_payload(items: list[dict[str, Any]]) -> dict[str, Any]:
    campaigns: list[dict[str, Any]] = []
    for item in items:
        campaigns.append(
            {
                "id": item.get("campaign_id", alias(item["url"], "campaign")),
                "name": item.get("campaign_name", "fault-campaign"),
                "status": "active",
                "exposure_time_ms": item.get("duration_ms", 1000),
                "media_urls": [item["url"]],
            }
        )
    return {"units": [{"campaigns": campaigns}]}


def media_item(url: str, duration_ms: int = 1000) -> dict[str, Any]:
    return {
        "url": url,
        "duration_ms": duration_ms,
        "campaign_id": alias(url, "campaign"),
        "campaign_name": alias(url, "name"),
    }


def media_kind(path: str, source_path: str = "") -> str:
    candidate = source_path or path
    suffix = Path(candidate).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
        return "image"
    if suffix in {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".mpeg", ".mpg"}:
        return "video"
    return suffix.lstrip(".") or "unknown"


def summarize_items(items: list[Any]) -> list[dict[str, Any]]:
    summary = []
    for item in items:
        path = str(getattr(item, "path", ""))
        source_path = str(getattr(item, "source_path", ""))
        summary.append(
            {
                "url_alias": alias(getattr(item, "url", ""), "url"),
                "path_alias": alias(path, "path"),
                "source_path_alias": alias(source_path, "source") if source_path else "",
                "kind": media_kind(path, source_path),
                "duration_ms": int(getattr(item, "duration_ms", 0) or 0),
            }
        )
    return summary


def summarize_status(snapshot: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "playlist_size",
        "playlist_update_state",
        "pending_playlist_size",
        "failed_media_count",
        "content_stale",
        "content_stale_reason",
        "content_state",
        "startup_phase",
        "playback_state",
        "player_state",
        "first_frame_ready",
        "first_content_load_accepted",
        "last_poll_success",
        "last_poll_error",
        "consecutive_failures",
    )
    return {key: snapshot.get(key) for key in keys}


def expectation(name: str, passed: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "details": details or {}}


def scenario_result(
    name: str,
    expectations: list[dict[str, Any]],
    observations: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": name,
        "passed": all(item["passed"] for item in expectations),
        "expectations": expectations,
        "observations": observations,
    }


def get_expectation(report: dict[str, Any], scenario_name: str, expectation_name: str) -> dict[str, Any]:
    for scenario in report["scenarios"]:
        if scenario["name"] != scenario_name:
            continue
        for item in scenario["expectations"]:
            if item["name"] == expectation_name:
                return item
    raise KeyError(f"{scenario_name}:{expectation_name}")


class Campaign:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.kiosk = load_kiosk_module()
        self.requests = FakeRequests()
        self.cache_dir = root / "cache"
        self.state_dir = root / "state"
        self.cfg = dict(self.kiosk.DEFAULT_CONFIG)
        self.cfg.update(
            {
                "api_url": "mock:///api/search",
                "api_key": "offline-test-key",
                "environment_id": "offline-env",
                "cache_dir": str(self.cache_dir),
                "state_dir": str(self.state_dir),
                "request_timeout_sec": 1,
                "poll_interval_sec": 1,
                "default_duration_ms": 1000,
                "min_free_space_bytes": 0,
                "max_download_bytes": 1024 * 1024,
                "require_full_download_before_switch": True,
                "allow_empty_playlist_from_api": False,
                "cache_max_files": 1000,
                "cache_max_bytes": 0,
                "telemetry_enabled": False,
                "startup_feedback_enabled": False,
            }
        )
        self.cfg_lock = threading.Lock()
        self.state = self.kiosk.PlaylistState()
        self.status = self.kiosk.StatusState()
        self.cache_index = self.kiosk.CacheIndex(self.cfg)
        self.scenarios: list[dict[str, Any]] = []
        self._restore: list[Callable[[], None]] = []

    def install_fakes(self) -> None:
        original_requests = self.kiosk.requests
        original_sleep = self.kiosk.time.sleep
        original_free_space = self.kiosk.free_space_bytes
        original_send_telemetry = self.kiosk.send_telemetry
        original_subprocess_run = self.kiosk.subprocess.run

        self.kiosk.requests = self.requests
        self.kiosk.free_space_bytes = lambda _path: 1024 * 1024 * 1024
        self.kiosk.send_telemetry = lambda *_args, **_kwargs: False

        def fake_sleep(_seconds: float) -> None:
            current_stop = getattr(self, "_current_stop_event", None)
            if current_stop is not None:
                current_stop.set()

        def fake_subprocess_run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
            executable = Path(command[0]).name
            if "ffprobe" in executable:
                probe_path = Path(command[-1])
                try:
                    data = probe_path.read_bytes()
                except OSError:
                    return subprocess.CompletedProcess(command, 1, b"", b"missing")
                valid = data.startswith(b"valid-") or data == b"offline-transcoded-image-sidecar"
                if not valid:
                    return subprocess.CompletedProcess(command, 1, b"", b"invalid")
                codec = "h264" if ".mp4" in probe_path.name.lower() else "mjpeg"
                stdout = json.dumps(
                    {
                        "streams": [
                            {
                                "codec_type": "video",
                                "codec_name": codec,
                                "width": 1280,
                                "height": 720,
                            }
                        ]
                    }
                ).encode("utf-8")
                return subprocess.CompletedProcess(command, 0, stdout, b"")

            if "-f" in command and command[command.index("-f") + 1] == "null":
                probe_path = Path(command[command.index("-i") + 1])
                try:
                    data = probe_path.read_bytes()
                except OSError:
                    return subprocess.CompletedProcess(command, 1, b"", b"missing")
                valid = data.startswith(b"valid-") or data == b"offline-transcoded-image-sidecar"
                return subprocess.CompletedProcess(command, 0 if valid else 1, b"", b"" if valid else b"decode failed")

            output_path = Path(command[-1])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"offline-transcoded-image-sidecar")
            return subprocess.CompletedProcess(command, 0, b"", b"")

        self.kiosk.time.sleep = fake_sleep
        self.kiosk.subprocess.run = fake_subprocess_run
        self._restore.extend(
            [
                lambda: setattr(self.kiosk, "requests", original_requests),
                lambda: setattr(self.kiosk.time, "sleep", original_sleep),
                lambda: setattr(self.kiosk, "free_space_bytes", original_free_space),
                lambda: setattr(self.kiosk, "send_telemetry", original_send_telemetry),
                lambda: setattr(self.kiosk.subprocess, "run", original_subprocess_run),
            ]
        )

    def close(self) -> None:
        for restore in reversed(self._restore):
            restore()

    def register_media(
        self,
        url: str,
        body: bytes,
        *,
        content_length: int | None | str = "actual",
        status_code: int = 200,
    ) -> None:
        headers: dict[str, str] = {}
        if content_length == "actual":
            headers["Content-Length"] = str(len(body))
        elif isinstance(content_length, int):
            headers["Content-Length"] = str(content_length)
        self.requests.get_responses[url] = FakeResponse(status_code=status_code, body=body, headers=headers)

    def run_poller_once(self, playlist: list[dict[str, Any]]) -> None:
        self.requests.queue_api(playlist)
        poll_now = threading.Event()
        stop_event = threading.Event()
        self._current_stop_event = stop_event
        try:
            self.kiosk.poller(
                self.cfg,
                self.cfg_lock,
                poll_now,
                self.state,
                self.status,
                self.cache_index,
                stop_event,
            )
        finally:
            self._current_stop_event = None

    def current_items(self) -> list[Any]:
        items, _version = self.state.get()
        return items

    def current_fingerprint_alias(self) -> str:
        raw_items, fingerprint, _saved_at = self.kiosk.load_playlist_state(self.cfg)
        if not raw_items and not fingerprint:
            return ""
        return alias(fingerprint or json.dumps(raw_items, sort_keys=True), "fingerprint")

    def mark_playing(self) -> None:
        items = self.current_items()
        current_item = summarize_items(items[:1])[0] if items else None
        self.status.update(
            playback_state="playing",
            content_state="playing",
            first_frame_ready=True,
            first_content_load_accepted=True,
            current_item=current_item,
        )

    def download_only(self, raw_items: list[dict[str, Any]]) -> list[Any]:
        return self.kiosk.download_media(self.cfg, raw_items, self.cache_index)

    def add_scenario(self, name: str, expectations: list[dict[str, Any]], observations: dict[str, Any]) -> None:
        self.scenarios.append(scenario_result(name, expectations, observations))

    def run(self) -> dict[str, Any]:
        self.install_fakes()
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.state_dir.mkdir(parents=True, exist_ok=True)
            self.scenario_mixed_playlist()
            self.scenario_truncated_with_content_length()
            self.scenario_truncated_without_content_length()
            self.scenario_http_200_invalid_body()
            self.scenario_corrupt_existing_sidecar()
            self.scenario_incomplete_playlist_preserves_lkg()
            self.scenario_partial_playlist_is_explicitly_stale()
            self.scenario_empty_api_preserves_lkg()
            self.scenario_recovery_to_valid_playlist()
        finally:
            self.close()

        return {
            "schema": SCHEMA,
            "snapshot": {
                "path": "player-runtime/kiosky-player/kiosk.py",
                "sha256": sha256_file(KIOSK_PATH),
            },
            "offline": {
                "network": "fake_requests_only",
                "board": "not_touched",
                "mpv": "not_started",
            },
            "monkeypatches": [
                "requests",
                "time.sleep",
                "free_space_bytes",
                "send_telemetry",
                "subprocess.run_for_media_probe_and_image_transcode",
            ],
            "scenarios": self.scenarios,
            "passed": all(scenario["passed"] for scenario in self.scenarios),
        }

    def scenario_mixed_playlist(self) -> None:
        video = media_item("mock:///media/mixed-video.mp4", 1200)
        image = media_item("mock:///media/mixed-image.jpg", 900)
        self.register_media(video["url"], b"valid-video-body")
        self.register_media(image["url"], b"valid-image-body")
        self.run_poller_once([video, image])
        items = self.current_items()
        self.mark_playing()
        kinds = [item["kind"] for item in summarize_items(items)]
        self.add_scenario(
            "mixed_video_image_playlist",
            [
                expectation("adopted_two_items", len(items) == 2, {"count": len(items)}),
                expectation("contains_video_and_image", kinds == ["video", "image"], {"kinds": kinds}),
                expectation("playlist_state_persisted", bool(self.current_fingerprint_alias())),
            ],
            {
                "items": summarize_items(items),
                "status": summarize_status(self.status.snapshot()),
                "fingerprint_alias": self.current_fingerprint_alias(),
            },
        )

    def scenario_truncated_with_content_length(self) -> None:
        item = media_item("mock:///media/truncated-with-length.mp4", 1000)
        self.register_media(item["url"], b"short", content_length=20)
        downloaded = self.download_only([item])
        self.add_scenario(
            "download_truncated_with_content_length",
            [
                expectation("rejected_truncated_download", len(downloaded) == 0, {"accepted_count": len(downloaded)}),
            ],
            {"items": summarize_items(downloaded)},
        )

    def scenario_truncated_without_content_length(self) -> None:
        item = media_item("mock:///media/truncated-without-length.mp4", 1000)
        self.register_media(item["url"], b"short", content_length=None)
        downloaded = self.download_only([item])
        self.add_scenario(
            "download_truncated_without_content_length",
            [
                expectation("rejected_truncated_download", len(downloaded) == 0, {"accepted_count": len(downloaded)}),
            ],
            {"items": summarize_items(downloaded)},
        )

    def scenario_http_200_invalid_body(self) -> None:
        item = media_item("mock:///media/http-200-invalid-body.mp4", 1000)
        self.register_media(item["url"], b"not-a-valid-media-container", content_length="actual", status_code=200)
        downloaded = self.download_only([item])
        self.add_scenario(
            "http_200_invalid_body",
            [
                expectation("rejected_invalid_media_body", len(downloaded) == 0, {"accepted_count": len(downloaded)}),
            ],
            {"items": summarize_items(downloaded)},
        )

    def scenario_corrupt_existing_sidecar(self) -> None:
        item = media_item("mock:///media/corrupt-sidecar.jpg", 1000)
        source_path = Path(self.kiosk.cache_path(self.cfg["cache_dir"], item["url"]))
        sidecar_path = Path(self.kiosk.transcoded_image_path(str(source_path)))
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b"valid-source-image-body")
        sidecar_path.write_bytes(b"corrupt-sidecar-body")
        now = time.time()
        os.utime(source_path, (now - 10, now - 10))
        os.utime(sidecar_path, (now, now))

        downloaded = self.download_only([item])
        sidecar_rebuilt = sidecar_path.read_bytes() == b"offline-transcoded-image-sidecar"
        downloaded_summary = summarize_items(downloaded)
        self.add_scenario(
            "corrupt_existing_sidecar",
            [
                expectation(
                    "rebuilt_corrupt_sidecar",
                    sidecar_rebuilt,
                    {"sidecar_rebuilt": sidecar_rebuilt},
                ),
                expectation(
                    "accepted_rebuilt_sidecar",
                    len(downloaded) == 1 and [item["kind"] for item in downloaded_summary] == ["image"],
                    {"accepted_count": len(downloaded), "items": downloaded_summary},
                ),
            ],
            {"items": downloaded_summary, "sidecar_rebuilt": sidecar_rebuilt},
        )

    def scenario_incomplete_playlist_preserves_lkg(self) -> None:
        before_items = self.current_items()
        before_fp = self.current_fingerprint_alias()
        good = media_item("mock:///media/partial-good.mp4", 1000)
        bad = media_item("mock:///media/partial-bad.mp4", 1000)
        self.register_media(good["url"], b"valid-partial-body")
        self.register_media(bad["url"], b"tiny", content_length=30)
        self.run_poller_once([good, bad])
        after_items = self.current_items()
        after_fp = self.current_fingerprint_alias()
        status = summarize_status(self.status.snapshot())
        self.add_scenario(
            "incomplete_playlist_preserves_last_known_good",
            [
                expectation(
                    "preserved_last_known_good",
                    summarize_items(after_items) == summarize_items(before_items) and after_fp == before_fp,
                    {"before_count": len(before_items), "after_count": len(after_items)},
                ),
                expectation(
                    "explicit_failed_adoption_state",
                    status.get("playlist_update_state") == "download_incomplete_retaining_last_known_good"
                    and status.get("content_stale") is True
                    and status.get("content_stale_reason") == "playlist_download_incomplete",
                    {
                        "playlist_update_state": status.get("playlist_update_state"),
                        "content_stale": status.get("content_stale"),
                        "content_stale_reason": status.get("content_stale_reason"),
                    },
                ),
            ],
            {
                "before_items": summarize_items(before_items),
                "after_items": summarize_items(after_items),
                "before_fingerprint_alias": before_fp,
                "after_fingerprint_alias": after_fp,
                "status": status,
            },
        )

    def scenario_empty_api_preserves_lkg(self) -> None:
        before_items = self.current_items()
        before_fp = self.current_fingerprint_alias()
        self.run_poller_once([])
        after_items = self.current_items()
        after_fp = self.current_fingerprint_alias()
        status = summarize_status(self.status.snapshot())
        self.add_scenario(
            "empty_api_preserves_availability",
            [
                expectation(
                    "preserved_available_content",
                    summarize_items(after_items) == summarize_items(before_items) and after_fp == before_fp,
                    {"before_count": len(before_items), "after_count": len(after_items)},
                ),
                expectation(
                    "explicit_stale_empty_state",
                    status.get("playlist_update_state") == "api_empty_retaining_last_known_good"
                    and status.get("content_stale") is True
                    and status.get("content_stale_reason") == "api_empty_playlist",
                    {
                        "playlist_update_state": status.get("playlist_update_state"),
                        "content_stale": status.get("content_stale"),
                        "content_stale_reason": status.get("content_stale_reason"),
                    },
                ),
            ],
            {
                "before_items": summarize_items(before_items),
                "after_items": summarize_items(after_items),
                "before_fingerprint_alias": before_fp,
                "after_fingerprint_alias": after_fp,
                "status": status,
            },
        )

    def scenario_partial_playlist_is_explicitly_stale(self) -> None:
        good = media_item("mock:///media/legacy-partial-good.mp4", 1000)
        bad = media_item("mock:///media/legacy-partial-bad.mp4", 1000)
        self.register_media(good["url"], b"valid-legacy-partial-body")
        self.register_media(bad["url"], b"tiny", content_length=30)
        original_policy = self.cfg["require_full_download_before_switch"]
        self.cfg["require_full_download_before_switch"] = False
        try:
            self.run_poller_once([good, bad])
        finally:
            self.cfg["require_full_download_before_switch"] = original_policy
        items = self.current_items()
        status = summarize_status(self.status.snapshot())
        self.add_scenario(
            "legacy_partial_playlist_stays_stale",
            [
                expectation("adopted_available_item", len(items) == 1, {"count": len(items)}),
                expectation(
                    "partial_adoption_not_false_green",
                    status.get("playlist_update_state") == "partial_playlist_applied"
                    and status.get("content_stale") is True
                    and status.get("content_stale_reason") == "partial_playlist"
                    and status.get("failed_media_count") == 1,
                    {
                        "playlist_update_state": status.get("playlist_update_state"),
                        "content_stale": status.get("content_stale"),
                        "content_stale_reason": status.get("content_stale_reason"),
                        "failed_media_count": status.get("failed_media_count"),
                    },
                ),
            ],
            {"items": summarize_items(items), "status": status},
        )

    def scenario_recovery_to_valid_playlist(self) -> None:
        before_fp = self.current_fingerprint_alias()
        video = media_item("mock:///media/recovery-video.mp4", 1300)
        image = media_item("mock:///media/recovery-image.jpg", 1100)
        self.register_media(video["url"], b"valid-recovery-video")
        self.register_media(image["url"], b"valid-recovery-image")
        self.run_poller_once([video, image])
        items = self.current_items()
        after_fp = self.current_fingerprint_alias()
        kinds = [item["kind"] for item in summarize_items(items)]
        self.add_scenario(
            "recovery_to_valid_playlist",
            [
                expectation("adopted_recovery_playlist", len(items) == 2 and after_fp != before_fp),
                expectation("recovery_contains_video_and_image", kinds == ["video", "image"], {"kinds": kinds}),
            ],
            {
                "items": summarize_items(items),
                "before_fingerprint_alias": before_fp,
                "after_fingerprint_alias": after_fp,
                "status": summarize_status(self.status.snapshot()),
            },
        )


def run_campaign() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="c22-player-fault-campaign-") as tmp:
        return Campaign(Path(tmp)).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compact", action="store_true", help="Emit compact JSON")
    parser.add_argument(
        "--fail-on-expectation",
        action="store_true",
        help="Exit 1 when any scenario expectation fails",
    )
    args = parser.parse_args(argv)
    report = run_campaign()
    indent = None if args.compact else 2
    print(json.dumps(report, indent=indent, sort_keys=True))
    if args.fail_on_expectation and not report["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
