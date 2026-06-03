#!/usr/bin/env python3
# C14.1.1 / C17.5 - totem_updatectl: pull-based updater.
#
# Scope:
#   - C18: applies manual totem-core updates under /data/core/totem.
#   - kiosky-player OTA is frozen until a C18-aware player/runtime package exists.
#   - Pulls assets from GitHub Releases via HTTPS (no git, no apt, no pip).
#   - Validates manifest schema + payload SHA256 before extracting.
#   - Atomic symlink swap of `current`. Keeps `previous` for rollback.
#   - Performs component health check; auto-rollback on failure.
#
# Out of scope (this round):
#   - OS / kernel / U-Boot / DTB / BSP updates.
#   - apt/pip installs on device.
#   - Wi-Fi/NetworkManager changes.
#   - Mender/RAUC/SWUpdate.
#
# Python stdlib only.

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

SCHEMA_MANIFEST = "dadooh.totem.update.v1"
SCHEMA_STATE = "dadooh.totem.update.state.v1"
SCHEMA_POLICY = "dadooh.totem.update.policy.v1"
DEFAULT_COMPONENT = "kiosky-player"  # legacy default; C18 operational OTA must pass --component totem-core.
COMPONENT = DEFAULT_COMPONENT
SUPPORTED_COMPONENTS = ("kiosky-player", "player-runtime", "totem-core")
DEVICE_REQUIRED = "orangepizero3"
DEVICE_TRACK_DEFAULT = "c18-hwdecode"
SUPPORTED_DEVICE_TRACKS = ("c18-hwdecode",)
SUPPORTED_BASE_IMAGE_LINES = ("c17.4.2",)
UPDATER_FEATURES = frozenset({
    "c18-freeze-kiosky-player-v1",
    "c18-rollback-reapply-v1",
    "c18-safe-payload-v1",
    "c18-track-v1",
})
KNOWN_REQUIRES_KEYS = frozenset({
    "device",
    "base_image_min",
    "device_track",
    "updater_features",
    "media_stack_id",
    "mpv_wrapper",
    "hwdec",
    "vo",
    "gpu_context",
    "deep_health_schema",
})
UPDATE_CHANNELS = ("lab", "homologation", "stable")
DEFAULT_DEVICE_CHANNEL = "stable"
SAFE_RELEASE_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
OTA_FROZEN_COMPONENTS = {
    "kiosky-player": "kiosky-player OTA is frozen until a C18-aware player/hwdecode package exists",
    "player-runtime": "player-runtime OTA is frozen until rollback + playback deep-health are validated on hardware",
}

DATA_ROOT = Path(os.environ.get("TOTEM_DATA_ROOT", "/data"))
UPDATES_DIR = DATA_ROOT / "updates"
POLICY_FILE = UPDATES_DIR / "policy.json"
APP_BASE = DATA_ROOT / "apps" / COMPONENT
RELEASES_DIR = APP_BASE / "releases"
CURRENT_LINK = APP_BASE / "current"
PREVIOUS_LINK = APP_BASE / "previous"
INCOMING_DIR = UPDATES_DIR / "incoming"
STATE_FILE = UPDATES_DIR / "state.json"

LOG_DIR = DATA_ROOT / "logs"
LOG_FILE = LOG_DIR / "totem-update.log"
LOG_MAX_BYTES = 1 * 1024 * 1024  # 1 MiB

TOKEN_FILE = Path(os.environ.get("TOTEM_DEVICE_GITHUB_TOKEN_FILE",
                                 "/data/secrets/github-release-token"))

SERVICE_NAME = os.environ.get("TOTEM_KIOSKY_SERVICE", "kiosky-player.service")
SETTINGS_LOCK = Path(os.environ.get("TOTEM_SETTINGS_SESSION_LOCK",
                                    "/run/totem/settings-session.lock"))
OPEN_SETTINGS_SERVICE = os.environ.get("TOTEM_OPEN_SETTINGS_SERVICE",
                                       "totem-open-settings.service")

GITHUB_API = "https://api.github.com"
GITHUB_RELEASE_PAGE_LIMIT = 10
HTTP_TIMEOUT_S = 30
DOWNLOAD_TIMEOUT_S = 300
USER_AGENT = "dadooh-totem-updatectl/0.2 (+orangepizero3)"

HEALTH_GRACE_SECONDS = int(os.environ.get("TOTEM_HEALTH_GRACE_SECONDS", "12"))
HEALTH_CHECK_TIMEOUT_S = int(os.environ.get("TOTEM_HEALTH_CHECK_TIMEOUT_S", "30"))

PLAYER_RUNTIME_MARKER_NAME = ".release_verified.json"
PLAYER_RUNTIME_MARKER_SCHEMA = "dadooh.c18.player_runtime.verified.v1"
PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA = "dadooh.c18.playback.deep_health.v1"
PLAYER_RUNTIME_HEALTH_HOOK: Optional[Callable[[Path, Dict[str, Any]], Any]] = None
PLAYER_RUNTIME_LAB_THAW_ENABLED = False

TOTEM_CORE_REQUIRED_BIN = (
    "totem_setup_visual_wizard.py",
    "totem_wifi_nm_adapter.py",
    "totem_visual_splash.py",
    "totem_status_aggregate.py",
    "totem_status_render_preview.py",
    "totem_config_contract_validate.py",
    "totem_open_settings_session.sh",
    "totem_visual_tty_guard.sh",
    "totem_firstboot_gate.sh",
    "totem_status_renderer.sh",
    "totem_settings_trigger.py",
    "totem_open_settings_cleanup.sh",
    "totem_visual_setup_writer_handoff.py",
    "totem_config_writer_real.py",
    "totem_setup_minimal_server.py",
    "totem_setup_local_wizard.py",
)


def configure_component(component: str) -> None:
    """Select paths and behavior for a supported update component."""
    global COMPONENT, APP_BASE, RELEASES_DIR, CURRENT_LINK, PREVIOUS_LINK
    global INCOMING_DIR, STATE_FILE

    if component not in SUPPORTED_COMPONENTS:
        raise RuntimeError(f"unsupported component: {component}")

    COMPONENT = component
    if component == "kiosky-player":
        APP_BASE = DATA_ROOT / "apps" / "kiosky-player"
        INCOMING_DIR = UPDATES_DIR / "incoming"
        STATE_FILE = UPDATES_DIR / "state.json"
    elif component == "totem-core":
        APP_BASE = DATA_ROOT / "core" / "totem"
        INCOMING_DIR = UPDATES_DIR / "incoming" / "totem-core"
        STATE_FILE = APP_BASE / "state.json"
    else:
        APP_BASE = DATA_ROOT / "player-runtime"
        INCOMING_DIR = UPDATES_DIR / "incoming" / "player-runtime"
        STATE_FILE = APP_BASE / "state.json"

    RELEASES_DIR = APP_BASE / "releases"
    CURRENT_LINK = APP_BASE / "current"
    PREVIOUS_LINK = APP_BASE / "previous"


# ----------------------------------------------------------------------------
# Sanitised logging
# ----------------------------------------------------------------------------

def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log_rotate_if_needed() -> None:
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > LOG_MAX_BYTES:
            rotated = LOG_FILE.with_suffix(LOG_FILE.suffix + ".1")
            try:
                if rotated.exists():
                    rotated.unlink()
            except OSError:
                pass
            try:
                LOG_FILE.rename(rotated)
            except OSError:
                pass
    except OSError:
        pass


def log(level: str, msg: str, **fields: Any) -> None:
    """
    Sanitised log: ISO timestamp + level + message + space-separated key=value.
    Never logs raw token, auth headers, raw response bodies, or env config blobs.
    """
    safe_fields = []
    for k, v in fields.items():
        if k.lower() in {"token", "authorization", "auth", "password", "secret"}:
            v = "<redacted>"
        s = str(v)
        if "Authorization:" in s or "Bearer " in s:
            s = "<redacted>"
        if len(s) > 512:
            s = s[:509] + "..."
        s = s.replace("\n", "\\n").replace("\r", "\\r")
        safe_fields.append(f"{k}={s}")
    line = f"{_utcnow_iso()} {level} {msg}"
    if safe_fields:
        line += " " + " ".join(safe_fields)
    # write to file (best effort) AND stderr
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        _log_rotate_if_needed()
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    print(line, file=sys.stderr)


# ----------------------------------------------------------------------------
# HTTP helpers (token never logged, never printed)
# ----------------------------------------------------------------------------

class HttpError(RuntimeError):
    def __init__(self, code: int, reason: str, url_safe: str):
        super().__init__(f"HTTP {code} {reason} on {url_safe}")
        self.code = code
        self.reason = reason
        self.url_safe = url_safe


def _load_device_token() -> Optional[str]:
    try:
        if TOKEN_FILE.is_file():
            tok = TOKEN_FILE.read_text(encoding="utf-8").strip()
            if tok:
                return tok
    except OSError:
        pass
    return None


def _build_request(url: str, accept: str = "application/json") -> urllib.request.Request:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept", accept)
    token = _load_device_token()
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    return req


def _safe_url(url: str) -> str:
    # never show query strings that might contain tokens (defensive only)
    if "?" in url:
        url = url.split("?", 1)[0] + "?<redacted>"
    return url


def _http_get_json(url: str) -> Any:
    req = _build_request(url, accept="application/vnd.github+json")
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        raise HttpError(e.code, e.reason, _safe_url(url))
    except (urllib.error.URLError, socket.timeout, ssl.SSLError) as e:
        raise RuntimeError(f"network error fetching {_safe_url(url)}: {e}")
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise RuntimeError(f"invalid JSON from {_safe_url(url)}: {e}")


def _http_download(url: str, dest: Path,
                   expected_sha256: Optional[str] = None) -> Tuple[int, str]:
    """
    Stream-download `url` to `dest`. Returns (bytes_downloaded, sha256_hex).
    If expected_sha256 is provided and mismatch, raises and removes file.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    if tmp.exists():
        tmp.unlink()

    req = _build_request(url, accept="application/octet-stream")
    hasher = hashlib.sha256()
    total = 0
    chunk = 64 * 1024
    try:
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT_S) as resp, \
             tmp.open("wb") as f:
            while True:
                buf = resp.read(chunk)
                if not buf:
                    break
                f.write(buf)
                hasher.update(buf)
                total += len(buf)
    except urllib.error.HTTPError as e:
        if tmp.exists():
            tmp.unlink()
        raise HttpError(e.code, e.reason, _safe_url(url))
    except (urllib.error.URLError, socket.timeout, ssl.SSLError) as e:
        if tmp.exists():
            tmp.unlink()
        raise RuntimeError(f"network error downloading {_safe_url(url)}: {e}")

    sha = hasher.hexdigest()
    if expected_sha256 and sha.lower() != expected_sha256.lower():
        if tmp.exists():
            tmp.unlink()
        raise RuntimeError(
            f"sha256 mismatch downloading {_safe_url(url)}: "
            f"expected={expected_sha256} actual={sha}"
        )

    tmp.replace(dest)
    return total, sha


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


# ----------------------------------------------------------------------------
# Filesystem helpers
# ----------------------------------------------------------------------------

def _ensure_dirs() -> None:
    for d in (APP_BASE, RELEASES_DIR, UPDATES_DIR, INCOMING_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _cleanup_stage(stage: Path) -> None:
    """Best-effort cleanup of a single staging directory under INCOMING_DIR."""
    try:
        if not (stage.exists() or stage.is_symlink()):
            return
        incoming = INCOMING_DIR.resolve()
        target = stage.resolve()
        if target == incoming:
            log("WARN", "stage_cleanup_refused_incoming_root", path=str(stage))
            return
        try:
            target.relative_to(incoming)
        except ValueError:
            log("WARN", "stage_cleanup_refused_outside_incoming", path=str(stage))
            return
        if stage.is_symlink() or stage.is_file():
            stage.unlink()
        else:
            shutil.rmtree(stage)
        log("INFO", "stage_cleanup_ok", path=str(stage))
    except Exception as e:
        log("WARN", "stage_cleanup_failed", path=str(stage), err=str(e))


def _atomic_symlink(target_rel: str, link: Path) -> None:
    """Replace `link` -> `target_rel` atomically (within the same fs)."""
    tmp = link.parent / (link.name + ".__tmp__")
    if tmp.is_symlink() or tmp.exists():
        try:
            tmp.unlink()
        except OSError:
            pass
    os.symlink(target_rel, str(tmp))
    os.replace(str(tmp), str(link))
    _fsync_dir(link.parent)


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".__tmp__")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
        try:
            f.flush()
            os.fsync(f.fileno())
        except OSError:
            pass
    try:
        os.chmod(tmp, 0o644)
    except OSError:
        pass
    os.replace(str(tmp), str(path))
    _fsync_dir(path.parent)


def _read_symlink_target(link: Path) -> Optional[str]:
    try:
        if link.is_symlink():
            return os.readlink(str(link))
    except OSError:
        return None
    return None


def _make_world_traversable(root: Path) -> None:
    """Equivalent of `chmod -R a+rX` on an extracted release tree.

    The kiosky-player.service runs as a NON-root user (`totem`). A restrictive
    umask and/or tar member perms can leave the release dir 0700 root:root, which
    `totem` cannot traverse -- the launcher's `[ -f current/kiosk.py ]` then fails
    and it silently falls back to /opt, so the pulled release NEVER takes effect.
    Normalize so any service user can traverse dirs (a+x) and read files (a+r),
    without granting write or stripping existing executable bits.
    """
    paths: List[Path] = [root]
    paths.extend(sorted(root.rglob("*")))
    for p in paths:
        try:
            st = p.lstat()
        except OSError:
            continue
        if stat.S_ISLNK(st.st_mode):
            continue  # perms of symlink targets are handled when visited directly
        mode = stat.S_IMODE(st.st_mode)
        new_mode = mode | 0o044  # a+r
        if stat.S_ISDIR(st.st_mode) or (mode & 0o111):
            new_mode |= 0o011    # a+x for dirs and already-executable files ('X')
        if new_mode != mode:
            try:
                os.chmod(p, new_mode)
            except OSError:
                pass


def _safe_extract_tar(tar_path: Path, dest: Path) -> None:
    """Tar extraction that rejects traversal and anything except regular files/dirs."""
    dest.mkdir(parents=True, exist_ok=True)
    dest_abs = dest.resolve()
    with tarfile.open(tar_path, mode="r:gz") as tf:
        members = []
        for m in tf.getmembers():
            if m.name.startswith("/") or ".." in Path(m.name).parts:
                raise RuntimeError(f"unsafe tar member rejected: {m.name}")
            if not (m.isreg() or m.isdir()):
                raise RuntimeError(f"unsupported tar member type: {m.name}")
            # ensure resolved target is inside dest
            target_abs = (dest_abs / m.name).resolve()
            try:
                target_abs.relative_to(dest_abs)
            except ValueError:
                raise RuntimeError(f"tar member escapes dest: {m.name}")
            members.append(m)
        tf.extractall(path=str(dest), members=members)
    # Ensure the non-root service user can traverse/read the extracted release.
    _make_world_traversable(dest)


def _tree_hash(root: Path) -> str:
    """Hash regular-file contents and relative paths under a release dir."""
    hasher = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if rel == PLAYER_RUNTIME_MARKER_NAME:
            continue
        try:
            st = path.lstat()
        except OSError:
            continue
        if stat.S_ISDIR(st.st_mode):
            continue
        if not stat.S_ISREG(st.st_mode):
            raise RuntimeError(f"unsupported release member type: {rel}")
        hasher.update(rel.encode("utf-8") + b"\0")
        hasher.update(_sha256_file(path).encode("ascii") + b"\0")
    return hasher.hexdigest()


def _player_runtime_identity(release_dir: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
    kiosk = release_dir / "kiosk.py"
    if not kiosk.is_file():
        raise RuntimeError("player-runtime kiosk.py missing")
    payload_sha = str(manifest["payload_sha256"]).lower()
    return {
        "version": manifest["version"],
        "payload_sha256": payload_sha,
        "kiosk_py_sha256": _sha256_file(kiosk),
        "tree_sha256": _tree_hash(release_dir),
    }


def _quarantine_entries(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries = state.get("quarantine") or state.get("quarantined_identities") or []
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def _player_runtime_is_quarantined(identity: Dict[str, Any], state: Dict[str, Any]) -> Tuple[bool, str]:
    for entry in _quarantine_entries(state):
        if entry.get("payload_sha256") and entry.get("payload_sha256") == identity.get("payload_sha256"):
            return True, "payload_sha256_quarantined"
        if entry.get("tree_sha256") and entry.get("tree_sha256") == identity.get("tree_sha256"):
            return True, "tree_sha256_quarantined"
    return False, "not_quarantined"


def _quarantine_player_runtime_identity(state: Dict[str, Any],
                                        identity: Dict[str, Any],
                                        reason: str) -> None:
    entries = _quarantine_entries(state)
    if not any(
        entry.get("payload_sha256") == identity.get("payload_sha256")
        or entry.get("tree_sha256") == identity.get("tree_sha256")
        for entry in entries
    ):
        entries.append({
            "version": identity.get("version"),
            "payload_sha256": identity.get("payload_sha256"),
            "tree_sha256": identity.get("tree_sha256"),
            "kiosk_py_sha256": identity.get("kiosk_py_sha256"),
            "reason": reason,
            "quarantined_at_utc": _utcnow_iso(),
        })
    state["quarantine"] = entries


def _write_player_runtime_marker(release_dir: Path,
                                 manifest: Dict[str, Any],
                                 identity: Dict[str, Any],
                                 health: Dict[str, Any]) -> Dict[str, Any]:
    marker = {
        "schema": PLAYER_RUNTIME_MARKER_SCHEMA,
        "verdict": "verified",
        "version": identity["version"],
        "payload_sha256": identity["payload_sha256"],
        "kiosk_py_sha256": identity["kiosk_py_sha256"],
        "tree_sha256": identity["tree_sha256"],
        "source_commit": manifest.get("source_commit"),
        "channel": manifest.get("channel"),
        "written_at_utc": _utcnow_iso(),
        "deep_health": {
            "schema": health.get("schema", PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA),
            "passed": bool(health.get("passed")),
            "artifact_id": health.get("artifact_id", "injected"),
            "observed_kiosk_py_sha256": health.get("observed_kiosk_py_sha256"),
            "observed_tree_sha256": health.get("observed_tree_sha256"),
        },
    }
    if not marker["deep_health"]["passed"]:
        raise RuntimeError("refusing to write verified marker for failed health")
    if marker["deep_health"]["observed_kiosk_py_sha256"] != identity["kiosk_py_sha256"]:
        raise RuntimeError("health did not observe candidate kiosk.py identity")
    if marker["deep_health"]["observed_tree_sha256"] != identity["tree_sha256"]:
        raise RuntimeError("health did not observe candidate tree identity")
    _atomic_write_json(release_dir / PLAYER_RUNTIME_MARKER_NAME, marker)
    return marker


def _load_player_runtime_marker(release_dir: Path) -> Dict[str, Any]:
    marker_path = release_dir / PLAYER_RUNTIME_MARKER_NAME
    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"marker_invalid:{e}") from e
    if not isinstance(data, dict):
        raise RuntimeError("marker_not_object")
    if data.get("schema") != PLAYER_RUNTIME_MARKER_SCHEMA:
        raise RuntimeError("marker_schema")
    if data.get("verdict") != "verified":
        raise RuntimeError("marker_not_verified")
    return data


def _validate_player_runtime_marker(release_dir: Path,
                                    state: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, Dict[str, Any]]:
    try:
        marker = _load_player_runtime_marker(release_dir)
        kiosk = release_dir / "kiosk.py"
        if not kiosk.is_file():
            return False, "kiosk_missing", marker
        identity = {
            "version": marker.get("version"),
            "payload_sha256": marker.get("payload_sha256"),
            "kiosk_py_sha256": _sha256_file(kiosk),
            "tree_sha256": _tree_hash(release_dir),
        }
        if marker.get("kiosk_py_sha256") != identity["kiosk_py_sha256"]:
            return False, "kiosk_sha_mismatch", marker
        if marker.get("tree_sha256") != identity["tree_sha256"]:
            return False, "tree_sha_mismatch", marker
        if state is not None:
            quarantined, reason = _player_runtime_is_quarantined(identity, state)
            if quarantined:
                return False, reason, marker
        return True, "verified", marker
    except Exception as e:
        return False, str(e), {}


def _default_player_runtime_health_hook(release_dir: Path,
                                        identity: Dict[str, Any]) -> Dict[str, Any]:
    """Run/collect candidate health.

    Production callers must observe the isolated candidate release_dir. Observing
    the currently launched service or /opt fallback is intentionally rejected by
    _write_player_runtime_marker via observed_* identity matching.
    """
    if PLAYER_RUNTIME_HEALTH_HOOK is not None:
        result = PLAYER_RUNTIME_HEALTH_HOOK(release_dir, identity)
        if isinstance(result, tuple):
            ok, reason = result
            return {
                "schema": PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA,
                "passed": bool(ok),
                "failure_reasons": [] if ok else [str(reason)],
                "observed_kiosk_py_sha256": identity["kiosk_py_sha256"],
                "observed_tree_sha256": identity["tree_sha256"],
                "artifact_id": "injected_tuple",
            }
        if isinstance(result, dict):
            return result
        raise RuntimeError("player-runtime health hook returned unsupported result")
    return {
        "schema": PLAYER_RUNTIME_DEEP_HEALTH_SCHEMA,
        "passed": False,
        "failure_reasons": ["player_runtime_health_hook_not_configured"],
        "observed_kiosk_py_sha256": None,
        "observed_tree_sha256": None,
        "artifact_id": "missing_health_hook",
    }


# ----------------------------------------------------------------------------
# State file
# ----------------------------------------------------------------------------

def _read_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {
            "schema": SCHEMA_STATE,
            "component": COMPONENT,
            "current": None,
            "previous": None,
            "last_operation": None,
        }
    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {
            "schema": SCHEMA_STATE,
            "component": COMPONENT,
            "current": None,
            "previous": None,
            "last_operation": None,
            "state_file_recovered_from_corruption": True,
        }


def _write_state(state: Dict[str, Any]) -> None:
    _atomic_write_json(STATE_FILE, state)


# ----------------------------------------------------------------------------
# Update channel policy
# ----------------------------------------------------------------------------

def _default_policy() -> Dict[str, Any]:
    return {
        "schema": SCHEMA_POLICY,
        "device_channel": DEFAULT_DEVICE_CHANNEL,
        "device_track": DEVICE_TRACK_DEFAULT,
        "allowed_components": [],
        "allow_prerelease": False,
        "allow_downgrade": False,
        "policy_source": "missing_policy_fail_closed",
    }


def _normalise_policy(raw: Any, source: str = "file") -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise RuntimeError("policy must be a JSON object")
    if raw.get("schema") != SCHEMA_POLICY:
        raise RuntimeError(f"unsupported policy schema: {raw.get('schema')!r}")
    channel = raw.get("device_channel")
    if channel not in UPDATE_CHANNELS:
        raise RuntimeError(f"unsupported device_channel: {channel!r}")
    device_track = raw.get("device_track", DEVICE_TRACK_DEFAULT)
    if device_track not in SUPPORTED_DEVICE_TRACKS:
        raise RuntimeError(f"unsupported device_track: {device_track!r}")
    allowed_components = raw.get("allowed_components")
    if not isinstance(allowed_components, list) or not allowed_components:
        raise RuntimeError("policy allowed_components must be a non-empty list")
    clean_components = []
    for item in allowed_components:
        if item not in SUPPORTED_COMPONENTS:
            raise RuntimeError(f"unsupported policy component: {item!r}")
        clean_components.append(item)
    return {
        "schema": SCHEMA_POLICY,
        "device_channel": channel,
        "device_track": device_track,
        "allowed_components": sorted(set(clean_components)),
        "allow_prerelease": bool(raw.get("allow_prerelease", False)),
        "allow_downgrade": bool(raw.get("allow_downgrade", False)),
        "policy_source": source,
    }


def _load_update_policy() -> Dict[str, Any]:
    if not POLICY_FILE.exists():
        return _default_policy()
    try:
        return _normalise_policy(json.loads(POLICY_FILE.read_text(encoding="utf-8")))
    except Exception as e:
        policy = _default_policy()
        policy["policy_source"] = "invalid_file_fail_closed_stable"
        policy["policy_error"] = str(e)
        log("WARN", "update_policy_invalid_fail_closed", err=str(e))
        return policy


def _policy_allows_manifest(policy: Dict[str, Any],
                            component: str,
                            manifest_channel: str) -> Tuple[bool, str]:
    if component not in policy.get("allowed_components", []):
        return False, "component_not_allowed_by_policy"
    # Conservative C17.9 policy: devices accept only their exact channel.
    if manifest_channel != policy.get("device_channel"):
        return False, "channel_incompatible_with_device_policy"
    return True, "ok"


def _apply_frozen_reason(component: Optional[str] = None) -> Optional[str]:
    return OTA_FROZEN_COMPONENTS.get(component or COMPONENT)


def _block_frozen_apply() -> Optional[int]:
    reason = _apply_frozen_reason()
    if reason is None:
        return None
    log("WARN", "apply_blocked_component_frozen", component=COMPONENT, reason=reason)
    print(f"component_frozen_for_ota: {COMPONENT}: {reason}", file=sys.stderr)
    return 44


def _state_entry_identity(entry: Any) -> Optional[Tuple[str, str]]:
    if not isinstance(entry, dict):
        return None
    version = entry.get("version")
    sha = entry.get("payload_sha256")
    if not isinstance(version, str) or not version:
        return None
    if not isinstance(sha, str) or not sha:
        return None
    return version, sha.lower()


def _parse_utc_timestamp(raw: Any) -> Optional[_dt.datetime]:
    if not isinstance(raw, str) or not raw:
        return None
    value = raw
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = _dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(_dt.timezone.utc)


def _state_entry_created_at(entry: Any) -> Optional[_dt.datetime]:
    if not isinstance(entry, dict):
        return None
    return _parse_utc_timestamp(entry.get("manifest_created_at_utc") or entry.get("created_at_utc"))


def _candidate_created_at(manifest: Dict[str, Any]) -> Optional[_dt.datetime]:
    return _parse_utc_timestamp(manifest.get("created_at_utc"))


def _downgrade_policy_allows_manifest(policy: Dict[str, Any],
                                      manifest: Dict[str, Any],
                                      state: Dict[str, Any]) -> Tuple[bool, str]:
    """Conservative downgrade guard using exact identity and optional manifest timestamps."""
    allow_downgrade = bool(policy.get("allow_downgrade"))
    version = manifest["version"]
    sha = str(manifest["payload_sha256"]).lower()
    candidate_identity = (version, sha)
    current = state.get("current")
    previous = state.get("previous")
    current_identity = _state_entry_identity(current)
    previous_identity = _state_entry_identity(previous)

    for label, identity in (("current", current_identity), ("previous", previous_identity)):
        if identity and identity[0] == version and identity[1] != sha:
            return False, f"{label}_version_payload_sha256_mismatch"

    if current_identity == candidate_identity:
        return True, "same_current_identity"

    current_created = _state_entry_created_at(current)
    candidate_created = _candidate_created_at(manifest)
    if current_created is not None:
        if candidate_created is None:
            if allow_downgrade:
                return True, "candidate_missing_created_at_allowed_by_policy"
            return False, "candidate_created_at_required_to_rule_out_downgrade"
        if candidate_created < current_created and not allow_downgrade:
            return False, "downgrade_not_allowed_by_policy"

    if previous_identity == candidate_identity:
        if allow_downgrade:
            return True, "previous_identity_allowed_by_policy"
        if current_created is not None and candidate_created is not None and candidate_created >= current_created:
            return True, "previous_identity_not_older_than_current"
        return False, "downgrade_not_allowed_by_policy"

    return True, "not_a_known_downgrade"


def _validate_release_version(version: Any) -> str:
    if not isinstance(version, str) or not SAFE_RELEASE_VERSION_RE.fullmatch(version):
        raise RuntimeError(f"unsafe version string: {version!r}")
    if version in {".", ".."} or ".." in version:
        raise RuntimeError(f"unsafe version string: {version!r}")
    return version


def _validate_payload_name(payload: Any, *, component: str, version: str) -> str:
    if not isinstance(payload, str) or not payload:
        raise RuntimeError(f"unsafe payload name: {payload!r}")
    if payload != Path(payload).name or payload in {".", ".."} or "\x00" in payload:
        raise RuntimeError(f"unsafe payload name: {payload!r}")
    expected = f"dadooh-{component}-{version}.tar.gz"
    if payload != expected:
        raise RuntimeError(f"unexpected payload name: {payload!r} != {expected!r}")
    return payload


# ----------------------------------------------------------------------------
# Manifest validation
# ----------------------------------------------------------------------------

REQUIRED_MANIFEST_FIELDS = (
    "schema", "component", "version", "payload",
    "payload_sha256", "requires", "channel", "created_at_utc",
)


def _validate_manifest(m: Dict[str, Any],
                       policy: Optional[Dict[str, Any]] = None,
                       component: Optional[str] = None) -> None:
    expected_component = component or COMPONENT
    if expected_component not in SUPPORTED_COMPONENTS:
        raise RuntimeError(f"unsupported component: {expected_component}")
    missing = [k for k in REQUIRED_MANIFEST_FIELDS if k not in m]
    if missing:
        raise RuntimeError(f"manifest missing fields: {missing}")
    if m["schema"] != SCHEMA_MANIFEST:
        raise RuntimeError(f"unsupported manifest schema: {m['schema']!r}")
    if m["component"] != expected_component:
        raise RuntimeError(f"manifest component mismatch: {m['component']!r} != {expected_component!r}")
    if _candidate_created_at(m) is None:
        raise RuntimeError("manifest created_at_utc must be an ISO-8601 UTC timestamp")
    channel = m["channel"]
    if channel not in UPDATE_CHANNELS:
        raise RuntimeError(f"unsupported manifest channel: {channel!r}")
    active_policy = policy or _load_update_policy()
    allowed, reason = _policy_allows_manifest(active_policy, expected_component, channel)
    if not allowed:
        raise RuntimeError(
            f"manifest channel rejected by policy: component={expected_component!r} "
            f"channel={channel!r} device_channel={active_policy.get('device_channel')!r} "
            f"reason={reason}"
        )
    req = m.get("requires") or {}
    if not isinstance(req, dict):
        raise RuntimeError("manifest requires must be a JSON object")
    unknown_requires = sorted(set(req) - KNOWN_REQUIRES_KEYS)
    if unknown_requires:
        raise RuntimeError(f"manifest requires unsupported keys: {unknown_requires}")
    dev = req.get("device")
    if dev and dev != DEVICE_REQUIRED:
        raise RuntimeError(f"manifest device requirement not met: {dev!r} != {DEVICE_REQUIRED!r}")
    base_image_min = req.get("base_image_min")
    if not isinstance(base_image_min, str) or not base_image_min:
        raise RuntimeError("manifest base_image_min requirement must be a string")
    if expected_component in {"totem-core", "player-runtime"} and base_image_min not in SUPPORTED_BASE_IMAGE_LINES:
        raise RuntimeError(f"manifest base_image_min requirement not met: {base_image_min!r}")
    device_track = req.get("device_track")
    if expected_component in {"totem-core", "player-runtime"} and not isinstance(device_track, str):
        raise RuntimeError(f"{expected_component} manifest requires device_track")
    if device_track is not None:
        if not isinstance(device_track, str):
            raise RuntimeError("manifest device_track requirement must be a string")
        policy_track = active_policy.get("device_track", DEVICE_TRACK_DEFAULT)
        if device_track != policy_track:
            raise RuntimeError(
                f"manifest device_track requirement not met: {device_track!r} != {policy_track!r}"
            )
    updater_features = req.get("updater_features")
    if expected_component == "totem-core" and updater_features is None:
        raise RuntimeError("totem-core manifest requires updater_features")
    if updater_features is not None:
        if (
            not isinstance(updater_features, list)
            or not updater_features
            or not all(isinstance(item, str) and item for item in updater_features)
        ):
            raise RuntimeError("manifest updater_features requirement must be a non-empty string list")
        missing_features = sorted(UPDATER_FEATURES - set(updater_features))
        if expected_component == "totem-core" and missing_features:
            raise RuntimeError(f"totem-core manifest missing required updater features: {missing_features}")
        unsupported_features = sorted(set(updater_features) - UPDATER_FEATURES)
        if unsupported_features:
            raise RuntimeError(f"manifest requires unsupported updater features: {unsupported_features}")
    ver = _validate_release_version(m["version"])
    _validate_payload_name(m["payload"], component=expected_component, version=ver)
    sha = m["payload_sha256"]
    if not isinstance(sha, str) or len(sha) != 64 or not all(c in "0123456789abcdefABCDEF" for c in sha):
        raise RuntimeError("payload_sha256 must be a 64-char hex digest")
    if expected_component == "kiosky-player":
        if "entrypoint" not in m:
            raise RuntimeError("manifest missing fields: ['entrypoint']")
        if m["entrypoint"] != "kiosk.py":
            raise RuntimeError(f"unsupported entrypoint: {m['entrypoint']!r}")
    elif expected_component == "player-runtime":
        expected_runtime_requires = {
            "media_stack_id": "c18-hwdecode-v4l2request-copy",
            "mpv_wrapper": "/opt/totem/bin/totem-mpv-hwdecode",
            "hwdec": "v4l2request-copy",
            "vo": "gpu",
            "gpu_context": "drm",
            "deep_health_schema": "dadooh.c18.playback.deep_health.v1",
        }
        for key, expected_value in expected_runtime_requires.items():
            if req.get(key) != expected_value:
                raise RuntimeError(f"player-runtime manifest requires {key}={expected_value!r}")
        entrypoint = m.get("entrypoint", "kiosk.py")
        if entrypoint != "kiosk.py":
            raise RuntimeError(f"unsupported player-runtime entrypoint: {entrypoint!r}")
    elif expected_component == "totem-core":
        entrypoint = m.get("entrypoint")
        if entrypoint is not None and (
            not isinstance(entrypoint, str)
            or not entrypoint.startswith("bin/")
            or "/" not in entrypoint
            or ".." in Path(entrypoint).parts
        ):
            raise RuntimeError(f"unsupported totem-core entrypoint: {entrypoint!r}")
        updates = m.get("updates")
        if not isinstance(updates, list) or not updates:
            raise RuntimeError("totem-core manifest requires non-empty updates list")


# ----------------------------------------------------------------------------
# requirements.txt comparison (block if device cannot satisfy new deps)
# ----------------------------------------------------------------------------

def _parse_requirements_txt(path: Path) -> List[str]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def _normalise_pkg(spec: str) -> str:
    # crude: strip version specifiers; lowercase
    for ch in "<>=!~":
        i = spec.find(ch)
        if i != -1:
            spec = spec[:i]
            break
    return spec.strip().lower()


def _check_requirements_compat(new_release_dir: Path) -> Tuple[bool, str]:
    """
    Returns (ok, reason). If new requirements.txt introduces a package
    not present in the current image (probed via python3 -c 'import X'),
    we block. Otherwise ok.
    """
    new_req = new_release_dir / "requirements.txt"
    if not new_req.exists():
        return True, "no requirements.txt in new release"
    new_specs = _parse_requirements_txt(new_req)
    if not new_specs:
        return True, "empty requirements.txt"
    new_pkgs = sorted({_normalise_pkg(s) for s in new_specs if _normalise_pkg(s)})

    # If a current release exists, compare to its requirements first; identical -> OK
    cur = _read_symlink_target(CURRENT_LINK)
    if cur:
        cur_path = (APP_BASE / cur).resolve()
        cur_req = cur_path / "requirements.txt"
        if cur_req.exists():
            cur_specs = sorted({_normalise_pkg(s)
                                for s in _parse_requirements_txt(cur_req)
                                if _normalise_pkg(s)})
            if cur_specs == new_pkgs:
                return True, "requirements unchanged"

    # Otherwise probe each pkg in the current Python
    missing = []
    for pkg in new_pkgs:
        if not pkg:
            continue
        mod = pkg.replace("-", "_")
        # heuristic: requests->requests, but some pkgs have different import names
        # We try the literal name and the underscored fallback.
        candidates = {mod, pkg}
        ok = False
        for c in candidates:
            r = subprocess.run(
                ["/usr/bin/python3", "-c", f"import {c}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            if r.returncode == 0:
                ok = True
                break
        if not ok:
            missing.append(pkg)
    if missing:
        return False, f"new release requires Python packages not present in image: {missing}"
    return True, "all required packages present"


# ----------------------------------------------------------------------------
# GitHub Releases discovery
# ----------------------------------------------------------------------------

def _gh_list_releases(repo: str) -> List[Dict[str, Any]]:
    releases: List[Dict[str, Any]] = []
    for page in range(1, GITHUB_RELEASE_PAGE_LIMIT + 1):
        url = f"{GITHUB_API}/repos/{repo}/releases?per_page=100&page={page}"
        data = _http_get_json(url)
        if not isinstance(data, list):
            raise RuntimeError("unexpected /releases response shape")
        releases.extend(r for r in data if isinstance(r, dict))
        if len(data) < 100:
            break
    return releases


def _release_sort_key(rel: Dict[str, Any]) -> str:
    return str(rel.get("published_at") or rel.get("created_at") or "")


def _gh_pick_assets(rel: Dict[str, Any],
                    component: Optional[str] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    expected_component = component or COMPONENT
    assets = rel.get("assets") or []
    manifest = next(
        (a for a in assets
         if isinstance(a, dict)
         and a.get("name", "").startswith(f"dadooh-{expected_component}-")
         and a.get("name", "").endswith(".manifest.json")),
        None,
    )
    payload = next(
        (a for a in assets
         if isinstance(a, dict)
         and a.get("name", "").startswith(f"dadooh-{expected_component}-")
         and a.get("name", "").endswith(".tar.gz")),
        None,
    )
    if manifest is None or payload is None:
        raise RuntimeError(f"release {rel.get('tag_name')} missing manifest or payload asset")
    return manifest, payload


def select_update_release(
    releases: List[Dict[str, Any]],
    policy: Dict[str, Any],
    component: str,
    manifest_loader: Optional[Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Select the newest release matching component and device channel policy.

    `manifest_loader` lets production code fetch the manifest asset. Tests can
    embed a synthetic `manifest` dict directly in the release fixture.
    """
    decisions: List[Dict[str, Any]] = []
    for rel in sorted(releases, key=_release_sort_key, reverse=True):
        tag = str(rel.get("tag_name") or rel.get("name") or "unknown")
        item = {
            "tag_name": tag,
            "draft": bool(rel.get("draft")),
            "prerelease": bool(rel.get("prerelease")),
            "selected": False,
            "reason": "",
        }
        if rel.get("draft"):
            item["reason"] = "draft_release_ignored"
            decisions.append(item)
            continue
        if rel.get("prerelease") and not bool(policy.get("allow_prerelease")):
            item["reason"] = "prerelease_not_allowed_by_policy"
            decisions.append(item)
            continue
        try:
            manifest_asset, payload_asset = _gh_pick_assets(rel, component)
        except Exception:
            item["reason"] = "missing_component_assets"
            decisions.append(item)
            continue
        try:
            manifest = manifest_loader(rel, manifest_asset) if manifest_loader else rel.get("manifest")
            if not isinstance(manifest, dict):
                raise RuntimeError("manifest missing or not JSON object")
            _validate_manifest(manifest, policy=policy, component=component)
        except Exception as e:
            item["reason"] = "invalid_manifest_ignored"
            item["detail"] = str(e)
            decisions.append(item)
            continue
        item["selected"] = True
        item["reason"] = "selected"
        item["manifest_channel"] = manifest.get("channel")
        item["manifest_version"] = manifest.get("version")
        decisions.append(item)
        return {
            "release": rel,
            "manifest": manifest,
            "manifest_asset": manifest_asset,
            "payload_asset": payload_asset,
            "decisions": decisions,
            "policy": policy,
        }
    return {
        "release": None,
        "manifest": None,
        "manifest_asset": None,
        "payload_asset": None,
        "decisions": decisions,
        "policy": policy,
    }


def _safe_stage_name(raw: str) -> str:
    return "".join(c for c in raw if c.isalnum() or c in "._-") or "unknown"


def _download_manifest_asset(asset: Dict[str, Any], dest_dir: Path) -> Path:
    url = asset.get("browser_download_url")
    if not isinstance(url, str) or not url:
        raise RuntimeError("manifest asset missing browser_download_url")
    name = _safe_stage_name(str(asset.get("name") or "manifest.json"))
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name
    log("INFO", "downloading_manifest", url=_safe_url(url), dest=str(dest))
    _http_download(url, dest, expected_sha256=None)
    return dest


def _gh_select_latest_release(repo: str,
                              stage_dir: Path) -> Dict[str, Any]:
    releases = _gh_list_releases(repo)
    policy = _load_update_policy()
    manifest_paths: Dict[Tuple[str, str], Path] = {}

    def load_manifest(rel: Dict[str, Any], asset: Dict[str, Any]) -> Dict[str, Any]:
        tag = _safe_stage_name(str(rel.get("tag_name") or "unknown"))
        path = _download_manifest_asset(asset, stage_dir / tag)
        manifest_paths[(tag, str(asset.get("name") or ""))] = path
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    selected = select_update_release(releases, policy, COMPONENT, load_manifest)
    rel = selected.get("release")
    if not isinstance(rel, dict):
        raise RuntimeError(
            f"no release on {repo} matched component={COMPONENT} "
            f"device_channel={policy.get('device_channel')}"
        )
    tag = _safe_stage_name(str(rel.get("tag_name") or "unknown"))
    asset = selected["manifest_asset"]
    selected["manifest_path"] = manifest_paths.get((tag, str(asset.get("name") or "")))
    return selected


# ----------------------------------------------------------------------------
# Systemd helpers
# ----------------------------------------------------------------------------

def _systemctl(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    cmd = ["/bin/systemctl"] + list(args)
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, check=check)


def _service_is_active() -> bool:
    r = _systemctl("is-active", SERVICE_NAME)
    return r.stdout.strip() == "active"


def _service_restart() -> Tuple[bool, str]:
    r = _systemctl("restart", SERVICE_NAME)
    if r.returncode != 0:
        return False, (r.stderr or r.stdout).strip()
    return True, "restart issued"


def _service_health_check() -> Tuple[bool, str]:
    """
    Health check:
      1) systemctl is-active == active
      2) Wait HEALTH_GRACE_SECONDS, then re-check is-active
      3) NRestarts must not have grown (suggest crash-loop)
    """
    deadline = time.monotonic() + HEALTH_CHECK_TIMEOUT_S

    # Pre-check: grab NRestarts baseline
    n0 = _systemctl("show", SERVICE_NAME, "-p", "NRestarts", "--value").stdout.strip()
    try:
        n0_int = int(n0)
    except ValueError:
        n0_int = -1

    # Wait for it to come up
    while time.monotonic() < deadline:
        if _service_is_active():
            break
        time.sleep(1)
    else:
        return False, "service did not reach active state within timeout"

    # Grace period
    time.sleep(HEALTH_GRACE_SECONDS)

    if not _service_is_active():
        return False, "service is not active after grace period"

    n1 = _systemctl("show", SERVICE_NAME, "-p", "NRestarts", "--value").stdout.strip()
    try:
        n1_int = int(n1)
    except ValueError:
        n1_int = -1

    if n0_int >= 0 and n1_int > n0_int:
        return False, f"NRestarts grew during health window: {n0_int}->{n1_int}"

    return True, "service active and stable"


def _systemd_unit_state(unit: str) -> str:
    r = _systemctl("is-active", unit)
    return (r.stdout or "").strip() or "unknown"


def _totem_core_apply_guard() -> Tuple[bool, str]:
    """Block totem-core apply while settings/writer visual session owns the device."""
    if COMPONENT != "totem-core":
        return True, "not totem-core"
    if SETTINGS_LOCK.exists():
        return False, "settings_session_lock_present"
    state = _systemd_unit_state(OPEN_SETTINGS_SERVICE)
    if state in {"active", "activating"}:
        return False, f"open_settings_service_{state}"
    request_file = Path("/run/dadooh-settings/request.json")
    if request_file.exists():
        return False, "settings_request_present"
    return True, "settings_session_inactive"


def _run_health_cmd(args: List[str], timeout_s: int = 45) -> Tuple[bool, str]:
    try:
        r = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except Exception as e:
        return False, f"{Path(args[0]).name}_failed_to_run:{e}"
    if r.returncode != 0:
        stderr = (r.stderr or r.stdout or "").strip().splitlines()
        detail = stderr[-1] if stderr else f"rc={r.returncode}"
        return False, f"{Path(args[-2] if args[0].endswith('python3') else args[-1]).name}:{detail}"
    return True, "ok"


def _restore_order_static_check(bin_dir: Path) -> Tuple[bool, str]:
    session = bin_dir / "totem_open_settings_session.sh"
    try:
        text = session.read_text(encoding="utf-8")
        restore_start = text.index("restore_service() {")
        restore_end = text.index("\n}\n\nkill_visual_if_running()", restore_start)
        release_start = text.index("release_session_lock_for_restore() {")
        release_end = text.index("\n}\n\nwrite_final_status()", release_start)
        normal_start = text.index('c1523_phase "session_cleanup_start rc=0"')
        normal_end = text.index('c1523_phase "session_done rc=0"', normal_start)
    except Exception as e:
        return False, f"restore_order_parse_failed:{e}"

    restore = text[restore_start:restore_end]
    release = text[release_start:release_end]
    normal = text[normal_start:normal_end]
    checks = {
        "restore_has_lock_guard": '[ -e "$LOCK_DIR" ]' in restore,
        "restore_guard_before_start": (
            '[ -e "$LOCK_DIR" ]' in restore
            and "systemctl start kiosky-player.service" in restore
            and restore.index('[ -e "$LOCK_DIR" ]') < restore.index("systemctl start kiosky-player.service")
        ),
        "release_removes_lock": "cleanup_session_lock" in release,
        "release_logs_before_restore": "session_lock_released_before_restore" in release,
        "normal_releases_before_restore": (
            "release_session_lock_for_restore" in normal
            and "restore_service" in normal
            and normal.index("release_session_lock_for_restore") < normal.index("restore_service")
        ),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        return False, "restore_order_failed:" + ",".join(failed)
    return True, "restore order ok"


def _totem_core_health_check(release_dir: Path) -> Tuple[bool, str]:
    bin_dir = release_dir / "bin"
    if not bin_dir.is_dir():
        return False, "bin_dir_missing"
    missing = [name for name in TOTEM_CORE_REQUIRED_BIN if not (bin_dir / name).is_file()]
    if missing:
        return False, "missing_bin:" + ",".join(missing)

    checks = [
        ["/usr/bin/python3", str(bin_dir / "totem_setup_visual_wizard.py"), "--self-test"],
        ["/usr/bin/python3", str(bin_dir / "totem_wifi_nm_adapter.py"), "--self-test"],
        ["/usr/bin/python3", str(bin_dir / "totem_visual_splash.py"), "--self-test"],
        ["/usr/bin/python3", str(bin_dir / "totem_config_contract_validate.py"), "--self-test"],
        ["/usr/bin/env", "bash", "-n", str(bin_dir / "totem_open_settings_session.sh")],
        ["/usr/bin/env", "bash", "-n", str(bin_dir / "totem_visual_tty_guard.sh")],
        ["/usr/bin/env", "bash", "-n", str(bin_dir / "totem_firstboot_gate.sh")],
        ["/usr/bin/env", "bash", "-n", str(bin_dir / "totem_status_renderer.sh")],
    ]
    for cmd in checks:
        ok, info = _run_health_cmd(cmd)
        if not ok:
            return False, info

    ok, info = _restore_order_static_check(bin_dir)
    if not ok:
        return False, info
    return True, "totem-core health checks passed"


# ----------------------------------------------------------------------------
# Apply flow
# ----------------------------------------------------------------------------

def _apply_from_manifest_path(manifest_path: Path, payload_url: Optional[str],
                              source: str,
                              payload_path_override: Optional[Path] = None) -> int:
    """
    Common apply logic.
    `manifest_path` must already exist on disk (validated JSON).
    `payload_url` is required (used to download the payload).
    `source` is a sanitised string for log/state (e.g. "github:owner/repo:tag").
    """
    started_at = _utcnow_iso()
    log("INFO", "apply_start", source=source, manifest=str(manifest_path))

    frozen_rc = _block_frozen_apply()
    if frozen_rc is not None:
        return frozen_rc

    return _apply_from_manifest_path_unfrozen(
        manifest_path,
        payload_url,
        source,
        payload_path_override=payload_path_override,
    )


def _apply_from_manifest_path_unfrozen(manifest_path: Path, payload_url: Optional[str],
                                       source: str,
                                       payload_path_override: Optional[Path] = None) -> int:
    """Internal apply path. Tests may call this for frozen components."""
    if COMPONENT == "player-runtime":
        if not PLAYER_RUNTIME_LAB_THAW_ENABLED:
            raise RuntimeError("player-runtime unfrozen apply requires explicit lab thaw guard")
        return _apply_player_runtime_from_manifest_path_unfrozen(
            manifest_path,
            payload_url,
            source,
            payload_path_override=payload_path_override,
        )

    started_at = _utcnow_iso()

    ok, reason = _totem_core_apply_guard()
    if not ok:
        log("WARN", "apply_blocked_by_component_guard", component=COMPONENT, reason=reason)
        return 40

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        log("ERROR", "manifest_read_failed", err=str(e))
        return 4
    policy = _load_update_policy()
    _validate_manifest(manifest, policy=policy)
    state = _read_state()
    ok, reason = _downgrade_policy_allows_manifest(policy, manifest, state)
    if not ok:
        log("ERROR", "manifest_rejected_by_downgrade_policy", reason=reason,
            version=manifest.get("version"))
        return 45

    version = manifest["version"]
    sha = manifest["payload_sha256"].lower()
    payload_name = manifest["payload"]

    # Stage payload
    stage = INCOMING_DIR / version
    stage.mkdir(parents=True, exist_ok=True)
    payload_local = stage / payload_name

    if payload_path_override is not None:
        try:
            actual_sha = _sha256_file(payload_path_override)
            if actual_sha.lower() != sha:
                log("ERROR", "local_payload_sha256_mismatch",
                    expected=sha, actual=actual_sha)
                _cleanup_stage(stage)
                return 6
            shutil.copy2(payload_path_override, payload_local)
            n = payload_local.stat().st_size
        except Exception as e:
            log("ERROR", "local_payload_stage_failed", err=str(e))
            _cleanup_stage(stage)
            return 6
        log("INFO", "local_payload_staged", bytes=n, sha256=actual_sha)
    elif payload_url is None:
        log("ERROR", "apply_failed_no_payload_url")
        _cleanup_stage(stage)
        return 5
    else:
        log("INFO", "downloading_payload", version=version, dest=str(payload_local))
        try:
            n, actual_sha = _http_download(payload_url, payload_local, expected_sha256=sha)
        except HttpError as e:
            log("ERROR", "payload_download_http_error", code=e.code, reason=e.reason)
            _cleanup_stage(stage)
            return 6
        except Exception as e:
            log("ERROR", "payload_download_failed", err=str(e))
            _cleanup_stage(stage)
            return 6
        log("INFO", "payload_downloaded", bytes=n, sha256=actual_sha)

    # Extract
    release_dir = RELEASES_DIR / version
    if release_dir.exists():
        log("WARN", "release_dir_exists_will_overwrite", path=str(release_dir))
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True, exist_ok=True)
    try:
        _safe_extract_tar(payload_local, release_dir)
    except Exception as e:
        log("ERROR", "extract_failed", err=str(e))
        try:
            shutil.rmtree(release_dir)
        except OSError:
            pass
        _cleanup_stage(stage)
        return 7

    if COMPONENT == "kiosky-player":
        # Entrypoint must exist post-extract
        entry = release_dir / manifest["entrypoint"]
        if not entry.is_file():
            log("ERROR", "entrypoint_missing", entry=str(entry))
            try:
                shutil.rmtree(release_dir)
            except OSError:
                pass
            _cleanup_stage(stage)
            return 8

        # requirements compat
        ok, reason = _check_requirements_compat(release_dir)
        if not ok:
            log("ERROR", "requirements_incompatible", reason=reason)
            try:
                shutil.rmtree(release_dir)
            except OSError:
                pass
            _cleanup_stage(stage)
            return 9
    else:
        ok, reason = _totem_core_health_check(release_dir)
        if not ok:
            log("ERROR", "totem_core_health_precheck_failed", reason=reason)
            try:
                shutil.rmtree(release_dir)
            except OSError:
                pass
            _cleanup_stage(stage)
            return 9

    # Remember the existing current as "previous_before_apply" for rollback
    prev_target_before_apply = _read_symlink_target(CURRENT_LINK)

    # Move the previous "previous" out of the way (keep one back-step)
    # current -> new ; previous -> (old current)
    _atomic_symlink(f"releases/{version}", CURRENT_LINK)
    if prev_target_before_apply and prev_target_before_apply != f"releases/{version}":
        _atomic_symlink(prev_target_before_apply, PREVIOUS_LINK)

    # Record state (preliminary)
    state["component"] = COMPONENT
    state["schema"] = SCHEMA_STATE
    state["previous"] = state.get("current")
    state["current"] = {
        "version": version,
        "applied_at_utc": _utcnow_iso(),
        "source": source,
        "source_repo": manifest.get("source_repo"),
        "source_branch": manifest.get("source_branch"),
        "source_commit": manifest.get("source_commit"),
        "channel": manifest.get("channel"),
        "payload_sha256": sha,
        "manifest_created_at_utc": manifest.get("created_at_utc"),
        "path": str(release_dir),
    }
    state["last_operation"] = {
        "type": "apply",
        "status": "pending_health_check",
        "started_at_utc": started_at,
        "version": version,
        "source": source,
    }
    _write_state(state)

    if COMPONENT == "kiosky-player":
        # Restart service
        log("INFO", "restarting_service", service=SERVICE_NAME)
        ok, info = _service_restart()
        if not ok:
            log("ERROR", "service_restart_failed", err=info)
            rc = _rollback_with_reason(state, started_at, "service_restart_failed")
            _cleanup_stage(stage)
            return rc

        # Health check
        log("INFO", "health_check_starting")
        ok, info = _service_health_check()
        if not ok:
            log("ERROR", "health_check_failed", reason=info)
            rc = _rollback_with_reason(state, started_at, info)
            _cleanup_stage(stage)
            return rc
    else:
        log("INFO", "totem_core_health_check_starting")
        ok, info = _totem_core_health_check(release_dir)
        if not ok:
            log("ERROR", "totem_core_health_check_failed", reason=info)
            rc = _rollback_with_reason(state, started_at, info)
            _cleanup_stage(stage)
            return rc

    state["last_operation"] = {
        "type": "apply",
        "status": "success",
        "started_at_utc": started_at,
        "finished_at_utc": _utcnow_iso(),
        "version": version,
        "source": source,
    }
    _write_state(state)
    log("INFO", "apply_success", version=version)
    _cleanup_stage(stage)
    return 0


def _apply_player_runtime_from_manifest_path_unfrozen(
    manifest_path: Path,
    payload_url: Optional[str],
    source: str,
    payload_path_override: Optional[Path] = None,
) -> int:
    """C18 player-runtime candidate verify-then-promote path for lab thaw tests."""
    started_at = _utcnow_iso()
    if COMPONENT != "player-runtime":
        raise RuntimeError("player-runtime apply path called for wrong component")

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        log("ERROR", "manifest_read_failed", err=str(e))
        return 4
    policy = _load_update_policy()
    _validate_manifest(manifest, policy=policy, component="player-runtime")
    state = _read_state()
    ok, reason = _downgrade_policy_allows_manifest(policy, manifest, state)
    if not ok:
        log("ERROR", "manifest_rejected_by_downgrade_policy", reason=reason,
            version=manifest.get("version"))
        return 45

    version = manifest["version"]
    sha = str(manifest["payload_sha256"]).lower()
    payload_name = manifest["payload"]
    stage = INCOMING_DIR / version
    stage.mkdir(parents=True, exist_ok=True)
    payload_local = stage / payload_name

    try:
        if payload_path_override is not None:
            actual_sha = _sha256_file(payload_path_override)
            if actual_sha.lower() != sha:
                log("ERROR", "local_payload_sha256_mismatch", expected=sha, actual=actual_sha)
                _cleanup_stage(stage)
                return 6
            shutil.copy2(payload_path_override, payload_local)
        elif payload_url is None:
            log("ERROR", "apply_failed_no_payload_url")
            _cleanup_stage(stage)
            return 5
        else:
            _http_download(payload_url, payload_local, expected_sha256=sha)
    except Exception as e:
        log("ERROR", "player_runtime_payload_stage_failed", err=str(e))
        _cleanup_stage(stage)
        return 6

    release_dir = RELEASES_DIR / version
    if release_dir.exists():
        current_target = _read_symlink_target(CURRENT_LINK)
        if current_target == f"releases/{version}":
            log("ERROR", "player_runtime_refusing_to_overwrite_current_release", version=version)
            _cleanup_stage(stage)
            return 46
        try:
            shutil.rmtree(release_dir)
        except OSError as e:
            log("ERROR", "release_dir_remove_failed", err=str(e))
            _cleanup_stage(stage)
            return 7
    release_dir.mkdir(parents=True, exist_ok=True)
    try:
        _safe_extract_tar(payload_local, release_dir)
    except Exception as e:
        log("ERROR", "extract_failed", err=str(e))
        try:
            shutil.rmtree(release_dir)
        except OSError:
            pass
        _cleanup_stage(stage)
        return 7

    try:
        identity = _player_runtime_identity(release_dir, manifest)
    except Exception as e:
        log("ERROR", "player_runtime_identity_failed", err=str(e))
        _cleanup_stage(stage)
        return 8

    quarantined, quarantine_reason = _player_runtime_is_quarantined(identity, state)
    if quarantined:
        log("ERROR", "player_runtime_candidate_quarantined", reason=quarantine_reason)
        _cleanup_stage(stage)
        return 47

    old_current = _read_symlink_target(CURRENT_LINK)
    state["component"] = COMPONENT
    state["schema"] = SCHEMA_STATE
    state["last_operation"] = {
        "type": "apply",
        "status": "verifying",
        "started_at_utc": started_at,
        "version": version,
        "source": source,
        "candidate_identity": identity,
    }
    _write_state(state)

    health = _default_player_runtime_health_hook(release_dir, identity)
    if not bool(health.get("passed")):
        reason = ",".join(str(item) for item in health.get("failure_reasons", [])) or "deep_health_failed"
        _quarantine_player_runtime_identity(state, identity, reason)
        if not old_current:
            state["current"] = None
        state["last_operation"] = {
            "type": "apply",
            "status": "candidate_rejected",
            "started_at_utc": started_at,
            "finished_at_utc": _utcnow_iso(),
            "version": version,
            "source": source,
            "rollback_reason": reason,
            "rolled_back_to": "previous" if old_current else "image_fallback",
        }
        _write_state(state)
        _cleanup_stage(stage)
        return 11 if not old_current else 10

    try:
        marker = _write_player_runtime_marker(release_dir, manifest, identity, health)
    except Exception as e:
        reason = f"marker_write_failed:{e}"
        _quarantine_player_runtime_identity(state, identity, reason)
        if not old_current:
            state["current"] = None
        state["last_operation"] = {
            "type": "apply",
            "status": "candidate_rejected",
            "started_at_utc": started_at,
            "finished_at_utc": _utcnow_iso(),
            "version": version,
            "source": source,
            "rollback_reason": reason,
            "rolled_back_to": "previous" if old_current else "image_fallback",
        }
        _write_state(state)
        _cleanup_stage(stage)
        return 12

    if old_current and old_current != f"releases/{version}":
        _atomic_symlink(old_current, PREVIOUS_LINK)
    _atomic_symlink(f"releases/{version}", CURRENT_LINK)
    state["previous"] = state.get("current")
    state["current"] = {
        "version": version,
        "applied_at_utc": _utcnow_iso(),
        "source": source,
        "source_repo": manifest.get("source_repo"),
        "source_branch": manifest.get("source_branch"),
        "source_commit": manifest.get("source_commit"),
        "channel": manifest.get("channel"),
        "payload_sha256": sha,
        "manifest_created_at_utc": manifest.get("created_at_utc"),
        "path": str(release_dir),
        "kiosk_py_sha256": identity["kiosk_py_sha256"],
        "tree_sha256": identity["tree_sha256"],
        "verified_marker": marker,
    }
    state["last_operation"] = {
        "type": "apply",
        "status": "success",
        "started_at_utc": started_at,
        "finished_at_utc": _utcnow_iso(),
        "version": version,
        "source": source,
    }
    _write_state(state)
    _cleanup_stage(stage)
    return 0


def _rollback_with_reason(state: Dict[str, Any], started_at: str, reason: str) -> int:
    log("WARN", "auto_rollback_starting", reason=reason)
    prev_link = _read_symlink_target(PREVIOUS_LINK)
    if not prev_link:
        if COMPONENT == "totem-core":
            try:
                if CURRENT_LINK.is_symlink() or CURRENT_LINK.exists():
                    CURRENT_LINK.unlink()
            except OSError:
                pass
            state["current"] = None
            state["last_operation"] = {
                "type": "apply",
                "status": "rolled_back_to_fallback",
                "started_at_utc": started_at,
                "finished_at_utc": _utcnow_iso(),
                "rollback_reason": reason,
                "rolled_back_to": "fallback",
            }
            _write_state(state)
            log("INFO", "auto_rollback_complete", rolled_to="fallback")
            return 10
        log("ERROR", "auto_rollback_failed_no_previous")
        state["last_operation"] = {
            "type": "apply",
            "status": "failed_no_rollback",
            "started_at_utc": started_at,
            "finished_at_utc": _utcnow_iso(),
            "rollback_reason": reason,
        }
        _write_state(state)
        return 11

    # Atomic swap: current <- previous
    _atomic_symlink(prev_link, CURRENT_LINK)

    if COMPONENT == "kiosky-player":
        ok, info = _service_restart()
    else:
        ok, info = _totem_core_health_check(APP_BASE / prev_link)
    if not ok:
        log("ERROR", "rollback_restart_failed", err=info)
    else:
        if COMPONENT == "kiosky-player":
            ok, info = _service_health_check()
            if not ok:
                log("ERROR", "rollback_health_check_failed", reason=info)

    rolled_to_version = prev_link.split("/")[-1] if "/" in prev_link else prev_link
    state["current"] = state.get("previous")
    state["last_operation"] = {
        "type": "apply",
        "status": "rolled_back",
        "started_at_utc": started_at,
        "finished_at_utc": _utcnow_iso(),
        "rollback_reason": reason,
        "rolled_back_to": rolled_to_version,
    }
    _write_state(state)
    log("INFO", "auto_rollback_complete", rolled_to=rolled_to_version)
    return 10


def _rollback_player_runtime_unfrozen(reason: str = "manual_rollback") -> int:
    """Rollback player-runtime current->previous, or fall back to image."""
    if COMPONENT != "player-runtime":
        raise RuntimeError("player-runtime rollback path called for wrong component")
    if not PLAYER_RUNTIME_LAB_THAW_ENABLED:
        raise RuntimeError("player-runtime unfrozen rollback requires explicit lab thaw guard")
    started_at = _utcnow_iso()
    state = _read_state()
    cur_link = _read_symlink_target(CURRENT_LINK)
    prev_link = _read_symlink_target(PREVIOUS_LINK)

    if prev_link:
        prev_dir = APP_BASE / prev_link
        ok, info, marker = _validate_player_runtime_marker(prev_dir, state)
        if ok:
            _atomic_symlink(prev_link, CURRENT_LINK)
            if cur_link and cur_link != prev_link:
                _atomic_symlink(cur_link, PREVIOUS_LINK)
            rolled_to_version = prev_link.split("/")[-1] if "/" in prev_link else prev_link
            previous_entry = state.get("previous")
            state["previous"] = state.get("current")
            if isinstance(previous_entry, dict) and previous_entry.get("version") == rolled_to_version:
                state["current"] = previous_entry
            else:
                state["current"] = {
                    "version": rolled_to_version,
                    "payload_sha256": marker.get("payload_sha256"),
                    "kiosk_py_sha256": marker.get("kiosk_py_sha256"),
                    "tree_sha256": marker.get("tree_sha256"),
                    "via": "player_runtime_rollback",
                    "applied_at_utc": _utcnow_iso(),
                }
            state["last_operation"] = {
                "type": "rollback",
                "status": "success",
                "started_at_utc": started_at,
                "finished_at_utc": _utcnow_iso(),
                "rollback_reason": reason,
                "rolled_back_to": rolled_to_version,
            }
            _write_state(state)
            return 0
        log("WARN", "player_runtime_previous_not_adopted", reason=info, previous=prev_link)

    try:
        if CURRENT_LINK.is_symlink() or CURRENT_LINK.exists():
            CURRENT_LINK.unlink()
    except OSError:
        pass
    state["current"] = None
    state["last_operation"] = {
        "type": "rollback",
        "status": "success",
        "started_at_utc": started_at,
        "finished_at_utc": _utcnow_iso(),
        "rollback_reason": reason,
        "rolled_back_to": "image_fallback",
    }
    _write_state(state)
    return 0


def _player_runtime_state_entry_from_marker(link: str,
                                            marker: Dict[str, Any],
                                            via: str) -> Dict[str, Any]:
    version = str(marker.get("version") or link.split("/")[-1] or "unknown")
    return {
        "version": version,
        "payload_sha256": marker.get("payload_sha256"),
        "kiosk_py_sha256": marker.get("kiosk_py_sha256"),
        "tree_sha256": marker.get("tree_sha256"),
        "path": str(APP_BASE / link),
        "via": via,
        "applied_at_utc": _utcnow_iso(),
    }


def _reconcile_player_runtime_state(reason: str = "manual_reconcile") -> Tuple[int, Dict[str, Any]]:
    """Fail closed for stale player-runtime state; launcher already validates at adopt time."""
    if COMPONENT != "player-runtime":
        raise RuntimeError("player-runtime reconcile path called for wrong component")
    started_at = _utcnow_iso()
    state = _read_state()
    state["component"] = COMPONENT
    state["schema"] = SCHEMA_STATE
    cur_link = _read_symlink_target(CURRENT_LINK)
    prev_link = _read_symlink_target(PREVIOUS_LINK)

    def finish(status: str, **extra: Any) -> Tuple[int, Dict[str, Any]]:
        state["last_operation"] = {
            "type": "reconcile",
            "status": status,
            "started_at_utc": started_at,
            "finished_at_utc": _utcnow_iso(),
            "reason": reason,
            **extra,
        }
        _write_state(state)
        result = {
            "component": COMPONENT,
            "status": status,
            "current_link": _read_symlink_target(CURRENT_LINK),
            **extra,
        }
        return 0, result

    if cur_link:
        ok, info, marker = _validate_player_runtime_marker(APP_BASE / cur_link, state)
        if ok:
            state["current"] = _player_runtime_state_entry_from_marker(
                cur_link, marker, "player_runtime_reconcile"
            )
            return finish("current_verified", verified=cur_link)

        if prev_link:
            prev_ok, prev_info, prev_marker = _validate_player_runtime_marker(APP_BASE / prev_link, state)
            if prev_ok:
                _atomic_symlink(prev_link, CURRENT_LINK)
                state["current"] = _player_runtime_state_entry_from_marker(
                    prev_link, prev_marker, "player_runtime_reconcile_previous"
                )
                return finish(
                    "previous_adopted",
                    rejected_current=cur_link,
                    reject_reason=info,
                    adopted_previous=prev_link,
                )
            log("WARN", "player_runtime_previous_not_adopted_during_reconcile",
                previous=prev_link, reason=prev_info)

        try:
            if CURRENT_LINK.is_symlink() or CURRENT_LINK.exists():
                CURRENT_LINK.unlink()
        except OSError:
            pass
        state["current"] = None
        return finish("image_fallback", rejected_current=cur_link, reject_reason=info)

    last = state.get("last_operation")
    last_status = last.get("status") if isinstance(last, dict) else None
    if state.get("current") is not None or last_status in {
        "verifying",
        "pending_health_check",
        "candidate_rejected",
    }:
        state["current"] = None
        return finish("image_fallback", reject_reason="no_current_symlink")
    return finish("noop")


# ----------------------------------------------------------------------------
# Subcommands
# ----------------------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> int:
    configure_component(args.component)
    _ensure_dirs()
    state = _read_state()
    policy = _load_update_policy()
    cur_link = _read_symlink_target(CURRENT_LINK)
    prev_link = _read_symlink_target(PREVIOUS_LINK)
    guard_ok, guard_reason = _totem_core_apply_guard()
    out = {
        "schema": SCHEMA_STATE,
        "component": COMPONENT,
        "data_root": str(DATA_ROOT),
        "component_base": str(APP_BASE),
        "update_policy": policy,
        "current_symlink_target": cur_link,
        "previous_symlink_target": prev_link,
        "state": state,
        "service_active": _service_is_active(),
        "component_apply_guard_ok": guard_ok,
        "component_apply_guard_reason": guard_reason,
        "token_file_present": TOKEN_FILE.is_file(),
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


def cmd_self_test(args: argparse.Namespace) -> int:
    configure_component(args.component)
    _ensure_dirs()
    checks = {
        "data_root_writable": os.access(str(DATA_ROOT), os.W_OK),
        "component_base_exists": APP_BASE.is_dir(),
        "updates_dir_exists": UPDATES_DIR.is_dir(),
        "log_dir_writable": os.access(str(LOG_DIR), os.W_OK),
        "systemctl_present": Path("/bin/systemctl").exists(),
        "python_stdlib_only": True,
        "service_unit_known": False,
    }
    if COMPONENT == "kiosky-player":
        r = _systemctl("show", SERVICE_NAME, "-p", "LoadState", "--value")
        checks["service_unit_known"] = (r.stdout.strip() == "loaded")
    elif COMPONENT == "totem-core":
        checks["service_unit_known"] = True
        checks["fallback_bin_exists"] = Path("/opt/totem/core-fallback/bin").is_dir()
        checks["settings_lock_guard_available"] = True
        guard_ok, _ = _totem_core_apply_guard()
        checks["settings_lock_guard_clear"] = guard_ok
    else:
        checks["service_unit_known"] = True
        checks["component_apply_frozen"] = _apply_frozen_reason() is not None
    out = {
        "self_test": all(checks.values()),
        "checks": checks,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    log("INFO", "self_test", passed=out["self_test"])
    return 0 if out["self_test"] else 1


def cmd_check_github_latest(args: argparse.Namespace) -> int:
    configure_component(args.component)
    _ensure_dirs()
    tmp = tempfile.TemporaryDirectory(prefix="totem-update-check-")
    try:
        selected = _gh_select_latest_release(args.repo, Path(tmp.name))
    except HttpError as e:
        if e.code == 404:
            print("PRIVATE_RELEASE_REQUIRES_DEVICE_TOKEN" if not _load_device_token()
                  else "GITHUB_RELEASE_ASSET_NOT_ACCESSIBLE_FROM_DEVICE",
                  file=sys.stderr)
            log("ERROR", "github_latest_404", repo=args.repo)
            return 20
        log("ERROR", "github_latest_http_error", code=e.code, reason=e.reason)
        return 21
    except Exception as e:
        log("ERROR", "github_latest_failed", err=str(e))
        return 21

    rel = selected["release"]
    manifest = selected["manifest"]
    m_asset = selected["manifest_asset"]
    p_asset = selected["payload_asset"]

    out = {
        "dry_run": True,
        "repo": args.repo,
        "tag_name": rel.get("tag_name"),
        "name": rel.get("name"),
        "prerelease": rel.get("prerelease"),
        "published_at": rel.get("published_at"),
        "component": COMPONENT,
        "manifest_channel": manifest.get("channel"),
        "device_channel": selected["policy"].get("device_channel"),
        "manifest_asset": m_asset.get("name"),
        "manifest_url": m_asset.get("browser_download_url"),
        "payload_asset": p_asset.get("name"),
        "payload_url": p_asset.get("browser_download_url"),
        "payload_size": p_asset.get("size"),
        "selection_decisions": selected.get("decisions", []),
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    log("INFO", "github_latest_check_ok", tag=rel.get("tag_name"))
    return 0


def cmd_list_github(args: argparse.Namespace) -> int:
    configure_component(args.component)
    _ensure_dirs()
    tmp = tempfile.TemporaryDirectory(prefix="totem-update-list-")
    try:
        selected = _gh_select_latest_release(args.repo, Path(tmp.name))
    except HttpError as e:
        if e.code == 404:
            print("PRIVATE_RELEASE_REQUIRES_DEVICE_TOKEN" if not _load_device_token()
                  else "GITHUB_RELEASE_ASSET_NOT_ACCESSIBLE_FROM_DEVICE",
                  file=sys.stderr)
            log("ERROR", "list_github_404", repo=args.repo)
            return 20
        log("ERROR", "list_github_http_error", code=e.code, reason=e.reason)
        return 21
    except Exception as e:
        log("ERROR", "list_github_failed", err=str(e))
        return 21

    rel = selected.get("release")
    manifest = selected.get("manifest") or {}
    out = {
        "dry_run": bool(args.dry_run),
        "repo": args.repo,
        "component": COMPONENT,
        "device_channel": selected["policy"].get("device_channel"),
        "allow_prerelease": selected["policy"].get("allow_prerelease"),
        "selected_tag": rel.get("tag_name") if isinstance(rel, dict) else None,
        "selected_version": manifest.get("version") if isinstance(manifest, dict) else None,
        "selected_channel": manifest.get("channel") if isinstance(manifest, dict) else None,
        "selection_decisions": selected.get("decisions", []),
        "state_changed": False,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if rel else 21


def cmd_apply_github_latest(args: argparse.Namespace) -> int:
    configure_component(args.component)
    if not args.dry_run:
        frozen_rc = _block_frozen_apply()
        if frozen_rc is not None:
            return frozen_rc
    _ensure_dirs()
    tmp = None
    if args.dry_run:
        tmp = tempfile.TemporaryDirectory(prefix="totem-update-apply-dry-run-")
        stage = Path(tmp.name)
    else:
        stage = INCOMING_DIR / f"github-select-{int(time.time())}"
    try:
        try:
            selected = _gh_select_latest_release(args.repo, stage)
        except HttpError as e:
            if e.code == 404:
                print("PRIVATE_RELEASE_REQUIRES_DEVICE_TOKEN" if not _load_device_token()
                      else "GITHUB_RELEASE_ASSET_NOT_ACCESSIBLE_FROM_DEVICE",
                      file=sys.stderr)
                log("ERROR", "apply_github_latest_404", repo=args.repo)
                return 20
            log("ERROR", "apply_github_latest_http_error", code=e.code, reason=e.reason)
            return 21
        except Exception as e:
            log("ERROR", "apply_github_latest_failed", err=str(e))
            return 21

        rel = selected["release"]
        manifest = selected["manifest"]
        p_asset = selected["payload_asset"]
        p_url = p_asset["browser_download_url"]
        tag = rel.get("tag_name") or "unknown"
        manifest_dest = selected.get("manifest_path")
        if not isinstance(manifest_dest, Path) or not manifest_dest.is_file():
            log("ERROR", "selected_manifest_missing_after_selection")
            return 23

        if args.dry_run:
            out = {
                "dry_run": True,
                "repo": args.repo,
                "component": COMPONENT,
                "tag_name": tag,
                "prerelease": rel.get("prerelease"),
                "manifest_channel": manifest.get("channel"),
                "manifest_version": manifest.get("version"),
                "device_channel": selected["policy"].get("device_channel"),
                "payload_asset": p_asset.get("name"),
                "state_changed": False,
            }
            print(json.dumps(out, indent=2, sort_keys=True))
            log("INFO", "apply_github_latest_dry_run_ok", tag=tag)
            return 0

        source = f"github:{args.repo}:{tag}"
        return _apply_from_manifest_path(manifest_dest, p_url, source)
    finally:
        if not args.dry_run:
            _cleanup_stage(stage)


def cmd_apply_manifest_url(args: argparse.Namespace) -> int:
    configure_component(args.component)
    frozen_rc = _block_frozen_apply()
    if frozen_rc is not None:
        return frozen_rc
    _ensure_dirs()
    manifest_url = args.url
    log("INFO", "fetching_manifest", url=_safe_url(manifest_url))
    # use safe_tag from URL basename
    base = manifest_url.rsplit("/", 1)[-1]
    safe = "".join(c for c in base if c.isalnum() or c in "._-") or "manual"
    stage = INCOMING_DIR / f"manual-{int(time.time())}"
    stage.mkdir(parents=True, exist_ok=True)
    manifest_dest = stage / safe
    try:
        try:
            _http_download(manifest_url, manifest_dest, expected_sha256=None)
        except HttpError as e:
            log("ERROR", "manifest_url_http_error", code=e.code, reason=e.reason)
            return 23
        except Exception as e:
            log("ERROR", "manifest_url_failed", err=str(e))
            return 23

        # Parse manifest to find payload URL: must be sibling URL of manifest
        with manifest_dest.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
        payload_name = manifest["payload"]
        # construct payload URL relative to manifest URL
        payload_url = manifest_url.rsplit("/", 1)[0] + "/" + payload_name
        return _apply_from_manifest_path(manifest_dest, payload_url, f"manifest_url:{_safe_url(manifest_url)}")
    finally:
        _cleanup_stage(stage)


def cmd_apply_local(args: argparse.Namespace) -> int:
    configure_component(args.component)
    frozen_rc = _block_frozen_apply()
    if frozen_rc is not None:
        return frozen_rc
    _ensure_dirs()
    manifest_path = Path(args.manifest)
    if not manifest_path.is_file() or manifest_path.is_symlink():
        print("local_manifest_not_found", file=sys.stderr)
        return 41
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        log("ERROR", "local_manifest_read_failed", err=str(e))
        return 41
    try:
        _validate_manifest(manifest)
    except Exception as e:
        log("ERROR", "local_manifest_validate_failed", err=str(e))
        return 41
    payload_path = Path(args.payload) if args.payload else manifest_path.parent / str(manifest["payload"])
    if not payload_path.is_file() or payload_path.is_symlink():
        print("local_payload_not_found", file=sys.stderr)
        return 42
    return _apply_from_manifest_path(
        manifest_path,
        payload_url=None,
        source=f"local:{manifest_path.name}",
        payload_path_override=payload_path,
    )


def cmd_rollback(args: argparse.Namespace) -> int:
    configure_component(args.component)
    frozen_reason = _apply_frozen_reason()
    if COMPONENT == "player-runtime" and frozen_reason:
        print(f"component_frozen_for_ota: {COMPONENT}: {frozen_reason}", file=sys.stderr)
        log("WARN", "rollback_blocked_component_frozen", component=COMPONENT, reason=frozen_reason)
        return 44
    if COMPONENT == "player-runtime":
        _ensure_dirs()
        rc = _rollback_player_runtime_unfrozen()
        if rc == 0:
            print(json.dumps({"rollback": "ok", "component": COMPONENT}, indent=2, sort_keys=True))
        return rc
    _ensure_dirs()
    prev_link = _read_symlink_target(PREVIOUS_LINK)
    if not prev_link:
        if COMPONENT == "totem-core":
            started_at = _utcnow_iso()
            cur_link = _read_symlink_target(CURRENT_LINK)
            try:
                if CURRENT_LINK.is_symlink() or CURRENT_LINK.exists():
                    CURRENT_LINK.unlink()
                if cur_link:
                    _atomic_symlink(cur_link, PREVIOUS_LINK)
            except OSError:
                pass
            state = _read_state()
            state["previous"] = state.get("current")
            state["current"] = None
            state["last_operation"] = {
                "type": "rollback",
                "status": "success",
                "started_at_utc": started_at,
                "finished_at_utc": _utcnow_iso(),
                "rolled_back_to": "fallback",
            }
            _write_state(state)
            log("INFO", "manual_rollback_ok", rolled_to="fallback")
            print(json.dumps({"rollback": "ok", "rolled_to": "fallback"},
                             indent=2, sort_keys=True))
            return 0
        print("rollback_not_available_no_previous", file=sys.stderr)
        log("WARN", "rollback_no_previous")
        return 30

    started_at = _utcnow_iso()
    cur_link = _read_symlink_target(CURRENT_LINK)
    _atomic_symlink(prev_link, CURRENT_LINK)
    if cur_link:
        _atomic_symlink(cur_link, PREVIOUS_LINK)  # swap

    if COMPONENT == "kiosky-player":
        ok, info = _service_restart()
        if not ok:
            log("ERROR", "manual_rollback_restart_failed", err=info)
            return 31
        ok, info = _service_health_check()
        if not ok:
            log("ERROR", "manual_rollback_health_failed", reason=info)
            return 32
    else:
        ok, info = _totem_core_health_check(APP_BASE / prev_link)
        if not ok:
            log("ERROR", "manual_rollback_health_failed", reason=info)
            return 32

    state = _read_state()
    previous_entry = state.get("previous")
    rolled_to_version = prev_link.split("/")[-1] if "/" in prev_link else prev_link
    state["previous"] = state.get("current")
    if isinstance(previous_entry, dict) and previous_entry.get("version") == rolled_to_version:
        state["current"] = previous_entry
        state["current"]["via"] = "manual_rollback"
        state["current"]["applied_at_utc"] = _utcnow_iso()
    else:
        # The "previous" entry in state should reflect the prior current; reconstruct lazily
        state["current"] = {
            "version": rolled_to_version,
            "applied_at_utc": _utcnow_iso(),
            "via": "manual_rollback",
        }
    state["last_operation"] = {
        "type": "rollback",
        "status": "success",
        "started_at_utc": started_at,
        "finished_at_utc": _utcnow_iso(),
        "rolled_back_to": rolled_to_version,
    }
    _write_state(state)
    log("INFO", "manual_rollback_ok", rolled_to=rolled_to_version)
    print(json.dumps({"rollback": "ok", "rolled_to": rolled_to_version},
                     indent=2, sort_keys=True))
    return 0


def cmd_reconcile(args: argparse.Namespace) -> int:
    configure_component(args.component)
    _ensure_dirs()
    if COMPONENT == "player-runtime":
        rc, result = _reconcile_player_runtime_state()
        print(json.dumps(result, indent=2, sort_keys=True))
        return rc
    result = {
        "component": COMPONENT,
        "status": "noop",
        "reason": "reconcile currently has player-runtime semantics only",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="totem-updatectl",
        description="Pull-based updater. C18 operational OTA must use --component totem-core.",
    )
    sub = parser.add_subparsers(dest="cmd")
    sub.required = True
    component_parent = argparse.ArgumentParser(add_help=False)
    component_parent.add_argument(
        "--component",
        choices=SUPPORTED_COMPONENTS,
        default=DEFAULT_COMPONENT,
        help="update component (legacy default: kiosky-player; C18 OTA must pass --component totem-core)",
    )

    sub.add_parser("status", parents=[component_parent],
                   help="Show updater state and current/previous links")
    sub.add_parser("self-test", parents=[component_parent],
                   help="Sanity check that updater can run on this device")

    p_check = sub.add_parser("check-github-latest",
                             parents=[component_parent],
                             help="Inspect the latest release on a GitHub repo")
    p_check.add_argument("--repo", required=True,
                         help="owner/repo, e.g. dadoohai/kiosky-player")

    p_list = sub.add_parser("list-github",
                            parents=[component_parent],
                            help="Dry-run GitHub release selection with channel policy")
    p_list.add_argument("--repo", required=True)
    p_list.add_argument("--dry-run", action="store_true", default=True)

    p_apply = sub.add_parser("apply-github-latest",
                             parents=[component_parent],
                             help="Apply the latest release from a GitHub repo")
    p_apply.add_argument("--repo", required=True)
    p_apply.add_argument("--dry-run", action="store_true",
                         help="Select and validate a release without applying it")

    p_url = sub.add_parser("apply-manifest-url",
                           parents=[component_parent],
                           help="Apply from an explicit manifest URL")
    p_url.add_argument("url")

    p_local = sub.add_parser("apply-local", parents=[component_parent],
                             help="Apply a local manifest + sibling payload")
    p_local.add_argument("manifest")
    p_local.add_argument("--payload", default="")

    sub.add_parser("rollback", parents=[component_parent],
                   help="Roll back current -> previous")
    sub.add_parser("reconcile", parents=[component_parent],
                   help="Reconcile stale state; player-runtime falls closed to verified current or image fallback")

    args = parser.parse_args(argv)
    handlers = {
        "status": cmd_status,
        "self-test": cmd_self_test,
        "check-github-latest": cmd_check_github_latest,
        "list-github": cmd_list_github,
        "apply-github-latest": cmd_apply_github_latest,
        "apply-manifest-url": cmd_apply_manifest_url,
        "apply-local": cmd_apply_local,
        "rollback": cmd_rollback,
        "reconcile": cmd_reconcile,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        log("WARN", "interrupted_by_user")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as e:  # last-resort hard guard
        log("ERROR", "unhandled_exception", err=str(e))
        sys.exit(99)
