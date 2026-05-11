#!/usr/bin/env python3
# C14.1.1 - totem_updatectl: pull-based app updater for kiosky-player.
#
# Scope:
#   - Updates ONLY the kiosky-player application under /data/apps/kiosky-player.
#   - Pulls assets from GitHub Releases via HTTPS (no git, no apt, no pip).
#   - Validates manifest schema + payload SHA256 before extracting.
#   - Atomic symlink swap of `current`. Keeps `previous` for rollback.
#   - Restarts kiosky-player.service via systemctl.
#   - Performs health check; auto-rollback on failure.
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
import shutil
import socket
import ssl
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

SCHEMA_MANIFEST = "dadooh.totem.update.v1"
SCHEMA_STATE = "dadooh.totem.update.state.v1"
COMPONENT = "kiosky-player"
DEVICE_REQUIRED = "orangepizero3"

DATA_ROOT = Path(os.environ.get("TOTEM_DATA_ROOT", "/data"))
APP_BASE = DATA_ROOT / "apps" / COMPONENT
RELEASES_DIR = APP_BASE / "releases"
CURRENT_LINK = APP_BASE / "current"
PREVIOUS_LINK = APP_BASE / "previous"

UPDATES_DIR = DATA_ROOT / "updates"
INCOMING_DIR = UPDATES_DIR / "incoming"
STATE_FILE = UPDATES_DIR / "state.json"

LOG_DIR = DATA_ROOT / "logs"
LOG_FILE = LOG_DIR / "totem-update.log"
LOG_MAX_BYTES = 1 * 1024 * 1024  # 1 MiB

TOKEN_FILE = Path(os.environ.get("TOTEM_DEVICE_GITHUB_TOKEN_FILE",
                                 "/data/secrets/github-release-token"))

SERVICE_NAME = os.environ.get("TOTEM_KIOSKY_SERVICE", "kiosky-player.service")

GITHUB_API = "https://api.github.com"
HTTP_TIMEOUT_S = 30
DOWNLOAD_TIMEOUT_S = 300
USER_AGENT = "dadooh-totem-updatectl/0.1 (+orangepizero3)"

HEALTH_GRACE_SECONDS = int(os.environ.get("TOTEM_HEALTH_GRACE_SECONDS", "12"))
HEALTH_CHECK_TIMEOUT_S = int(os.environ.get("TOTEM_HEALTH_CHECK_TIMEOUT_S", "30"))


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


# ----------------------------------------------------------------------------
# Filesystem helpers
# ----------------------------------------------------------------------------

def _ensure_dirs() -> None:
    for d in (APP_BASE, RELEASES_DIR, UPDATES_DIR, INCOMING_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


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


def _read_symlink_target(link: Path) -> Optional[str]:
    try:
        if link.is_symlink():
            return os.readlink(str(link))
    except OSError:
        return None
    return None


def _safe_extract_tar(tar_path: Path, dest: Path) -> None:
    """Tar extraction that rejects absolute paths, '..' traversal, and non-files/dirs."""
    dest.mkdir(parents=True, exist_ok=True)
    dest_abs = dest.resolve()
    with tarfile.open(tar_path, mode="r:gz") as tf:
        members = []
        for m in tf.getmembers():
            if m.name.startswith("/") or ".." in Path(m.name).parts:
                raise RuntimeError(f"unsafe tar member rejected: {m.name}")
            if not (m.isreg() or m.isdir() or m.issym() or m.islnk()):
                raise RuntimeError(f"unsupported tar member type: {m.name}")
            # ensure resolved target is inside dest
            target_abs = (dest_abs / m.name).resolve()
            try:
                target_abs.relative_to(dest_abs)
            except ValueError:
                raise RuntimeError(f"tar member escapes dest: {m.name}")
            members.append(m)
        tf.extractall(path=str(dest), members=members)


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
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")
    tmp.replace(STATE_FILE)


# ----------------------------------------------------------------------------
# Manifest validation
# ----------------------------------------------------------------------------

REQUIRED_MANIFEST_FIELDS = (
    "schema", "component", "version", "payload",
    "payload_sha256", "entrypoint", "requires",
)


def _validate_manifest(m: Dict[str, Any]) -> None:
    missing = [k for k in REQUIRED_MANIFEST_FIELDS if k not in m]
    if missing:
        raise RuntimeError(f"manifest missing fields: {missing}")
    if m["schema"] != SCHEMA_MANIFEST:
        raise RuntimeError(f"unsupported manifest schema: {m['schema']!r}")
    if m["component"] != COMPONENT:
        raise RuntimeError(f"manifest component mismatch: {m['component']!r} != {COMPONENT!r}")
    req = m.get("requires") or {}
    dev = req.get("device")
    if dev and dev != DEVICE_REQUIRED:
        raise RuntimeError(f"manifest device requirement not met: {dev!r} != {DEVICE_REQUIRED!r}")
    ver = m["version"]
    if not isinstance(ver, str) or not ver or "/" in ver or ".." in ver or "\x00" in ver:
        raise RuntimeError(f"unsafe version string: {ver!r}")
    sha = m["payload_sha256"]
    if not isinstance(sha, str) or len(sha) != 64 or not all(c in "0123456789abcdefABCDEF" for c in sha):
        raise RuntimeError("payload_sha256 must be a 64-char hex digest")
    if m["entrypoint"] != "kiosk.py":
        raise RuntimeError(f"unsupported entrypoint: {m['entrypoint']!r}")


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

def _gh_get_latest_release(repo: str) -> Dict[str, Any]:
    # /releases/latest returns the latest non-draft, non-prerelease.
    # We want prereleases (homologation), so list /releases and pick the most recent
    # whose name/tag matches our app convention or whose manifest matches the component.
    url = f"{GITHUB_API}/repos/{repo}/releases"
    data = _http_get_json(url)
    if not isinstance(data, list):
        raise RuntimeError("unexpected /releases response shape")
    # Sort by published_at descending (GitHub already returns newest first, but be explicit)
    def _sort_key(r: Dict[str, Any]) -> str:
        return r.get("published_at") or r.get("created_at") or ""
    data.sort(key=_sort_key, reverse=True)
    for rel in data:
        if rel.get("draft"):
            continue
        assets = rel.get("assets") or []
        manifest_asset = next(
            (a for a in assets
             if isinstance(a, dict) and isinstance(a.get("name"), str)
             and a["name"].startswith(f"dadooh-{COMPONENT}-")
             and a["name"].endswith(".manifest.json")),
            None,
        )
        if manifest_asset:
            return rel
    raise RuntimeError(
        f"no release on {repo} has a dadooh-{COMPONENT}-*.manifest.json asset"
    )


def _gh_pick_assets(rel: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    assets = rel.get("assets") or []
    manifest = next(
        (a for a in assets
         if a.get("name", "").startswith(f"dadooh-{COMPONENT}-")
         and a.get("name", "").endswith(".manifest.json")),
        None,
    )
    payload = next(
        (a for a in assets
         if a.get("name", "").startswith(f"dadooh-{COMPONENT}-")
         and a.get("name", "").endswith(".tar.gz")),
        None,
    )
    if manifest is None or payload is None:
        raise RuntimeError(f"release {rel.get('tag_name')} missing manifest or payload asset")
    return manifest, payload


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


# ----------------------------------------------------------------------------
# Apply flow
# ----------------------------------------------------------------------------

def _apply_from_manifest_path(manifest_path: Path, payload_url: Optional[str],
                              source: str) -> int:
    """
    Common apply logic.
    `manifest_path` must already exist on disk (validated JSON).
    `payload_url` is required (used to download the payload).
    `source` is a sanitised string for log/state (e.g. "github:owner/repo:tag").
    """
    started_at = _utcnow_iso()
    log("INFO", "apply_start", source=source, manifest=str(manifest_path))

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        log("ERROR", "manifest_read_failed", err=str(e))
        return 4
    _validate_manifest(manifest)

    version = manifest["version"]
    sha = manifest["payload_sha256"].lower()
    payload_name = manifest["payload"]

    # Stage payload
    stage = INCOMING_DIR / version
    stage.mkdir(parents=True, exist_ok=True)
    payload_local = stage / payload_name

    if payload_url is None:
        log("ERROR", "apply_failed_no_payload_url")
        return 5

    log("INFO", "downloading_payload", version=version, dest=str(payload_local))
    try:
        n, actual_sha = _http_download(payload_url, payload_local, expected_sha256=sha)
    except HttpError as e:
        log("ERROR", "payload_download_http_error", code=e.code, reason=e.reason)
        return 6
    except Exception as e:
        log("ERROR", "payload_download_failed", err=str(e))
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
        return 7

    # Entrypoint must exist post-extract
    entry = release_dir / manifest["entrypoint"]
    if not entry.is_file():
        log("ERROR", "entrypoint_missing", entry=str(entry))
        try:
            shutil.rmtree(release_dir)
        except OSError:
            pass
        return 8

    # requirements compat
    ok, reason = _check_requirements_compat(release_dir)
    if not ok:
        log("ERROR", "requirements_incompatible", reason=reason)
        try:
            shutil.rmtree(release_dir)
        except OSError:
            pass
        return 9

    # Remember the existing current as "previous_before_apply" for rollback
    prev_target_before_apply = _read_symlink_target(CURRENT_LINK)

    # Move the previous "previous" out of the way (keep one back-step)
    # current -> new ; previous -> (old current)
    _atomic_symlink(f"releases/{version}", CURRENT_LINK)
    if prev_target_before_apply and prev_target_before_apply != f"releases/{version}":
        _atomic_symlink(prev_target_before_apply, PREVIOUS_LINK)

    # Record state (preliminary)
    state = _read_state()
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
        "payload_sha256": sha,
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

    # Restart service
    log("INFO", "restarting_service", service=SERVICE_NAME)
    ok, info = _service_restart()
    if not ok:
        log("ERROR", "service_restart_failed", err=info)
        return _rollback_with_reason(state, started_at, "service_restart_failed")

    # Health check
    log("INFO", "health_check_starting")
    ok, info = _service_health_check()
    if not ok:
        log("ERROR", "health_check_failed", reason=info)
        return _rollback_with_reason(state, started_at, info)

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
    return 0


def _rollback_with_reason(state: Dict[str, Any], started_at: str, reason: str) -> int:
    log("WARN", "auto_rollback_starting", reason=reason)
    prev_link = _read_symlink_target(PREVIOUS_LINK)
    if not prev_link:
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

    ok, info = _service_restart()
    if not ok:
        log("ERROR", "rollback_restart_failed", err=info)
    else:
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


# ----------------------------------------------------------------------------
# Subcommands
# ----------------------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> int:
    _ensure_dirs()
    state = _read_state()
    cur_link = _read_symlink_target(CURRENT_LINK)
    prev_link = _read_symlink_target(PREVIOUS_LINK)
    out = {
        "schema": SCHEMA_STATE,
        "component": COMPONENT,
        "data_root": str(DATA_ROOT),
        "current_symlink_target": cur_link,
        "previous_symlink_target": prev_link,
        "state": state,
        "service_active": _service_is_active(),
        "token_file_present": TOKEN_FILE.is_file(),
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


def cmd_self_test(args: argparse.Namespace) -> int:
    _ensure_dirs()
    checks = {
        "data_root_writable": os.access(str(DATA_ROOT), os.W_OK),
        "app_base_exists": APP_BASE.is_dir(),
        "updates_dir_exists": UPDATES_DIR.is_dir(),
        "log_dir_writable": os.access(str(LOG_DIR), os.W_OK),
        "systemctl_present": Path("/bin/systemctl").exists(),
        "python_stdlib_only": True,
        "service_unit_known": False,
    }
    r = _systemctl("show", SERVICE_NAME, "-p", "LoadState", "--value")
    checks["service_unit_known"] = (r.stdout.strip() == "loaded")
    out = {
        "self_test": all(checks.values()),
        "checks": checks,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    log("INFO", "self_test", passed=out["self_test"])
    return 0 if out["self_test"] else 1


def cmd_check_github_latest(args: argparse.Namespace) -> int:
    _ensure_dirs()
    try:
        rel = _gh_get_latest_release(args.repo)
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

    try:
        m_asset, p_asset = _gh_pick_assets(rel)
    except Exception as e:
        log("ERROR", "github_latest_pick_assets_failed", err=str(e))
        return 22

    out = {
        "repo": args.repo,
        "tag_name": rel.get("tag_name"),
        "name": rel.get("name"),
        "prerelease": rel.get("prerelease"),
        "published_at": rel.get("published_at"),
        "manifest_asset": m_asset.get("name"),
        "manifest_url": m_asset.get("browser_download_url"),
        "payload_asset": p_asset.get("name"),
        "payload_url": p_asset.get("browser_download_url"),
        "payload_size": p_asset.get("size"),
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    log("INFO", "github_latest_check_ok", tag=rel.get("tag_name"))
    return 0


def cmd_apply_github_latest(args: argparse.Namespace) -> int:
    _ensure_dirs()
    try:
        rel = _gh_get_latest_release(args.repo)
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

    m_asset, p_asset = _gh_pick_assets(rel)
    m_url = m_asset["browser_download_url"]
    p_url = p_asset["browser_download_url"]
    tag = rel.get("tag_name") or "unknown"

    # Stage incoming dir using tag (or filename without ext for safety)
    safe_tag = "".join(c for c in tag if c.isalnum() or c in "._-") or "unknown"
    stage = INCOMING_DIR / safe_tag
    stage.mkdir(parents=True, exist_ok=True)
    manifest_dest = stage / m_asset["name"]

    log("INFO", "downloading_manifest", url=_safe_url(m_url), dest=str(manifest_dest))
    try:
        _http_download(m_url, manifest_dest, expected_sha256=None)
    except HttpError as e:
        log("ERROR", "manifest_download_http_error", code=e.code, reason=e.reason)
        return 23
    except Exception as e:
        log("ERROR", "manifest_download_failed", err=str(e))
        return 23

    source = f"github:{args.repo}:{tag}"
    return _apply_from_manifest_path(manifest_dest, p_url, source)


def cmd_apply_manifest_url(args: argparse.Namespace) -> int:
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


def cmd_rollback(args: argparse.Namespace) -> int:
    _ensure_dirs()
    prev_link = _read_symlink_target(PREVIOUS_LINK)
    if not prev_link:
        print("rollback_not_available_no_previous", file=sys.stderr)
        log("WARN", "rollback_no_previous")
        return 30

    started_at = _utcnow_iso()
    cur_link = _read_symlink_target(CURRENT_LINK)
    _atomic_symlink(prev_link, CURRENT_LINK)
    if cur_link:
        _atomic_symlink(cur_link, PREVIOUS_LINK)  # swap

    ok, info = _service_restart()
    if not ok:
        log("ERROR", "manual_rollback_restart_failed", err=info)
        return 31
    ok, info = _service_health_check()
    if not ok:
        log("ERROR", "manual_rollback_health_failed", reason=info)
        return 32

    state = _read_state()
    state["previous"] = state.get("current")
    # The "previous" entry in state should reflect the prior current; reconstruct lazily
    state["current"] = {
        "version": prev_link.split("/")[-1] if "/" in prev_link else prev_link,
        "applied_at_utc": _utcnow_iso(),
        "via": "manual_rollback",
    }
    state["last_operation"] = {
        "type": "rollback",
        "status": "success",
        "started_at_utc": started_at,
        "finished_at_utc": _utcnow_iso(),
        "rolled_back_to": state["current"]["version"],
    }
    _write_state(state)
    log("INFO", "manual_rollback_ok", rolled_to=state["current"]["version"])
    print(json.dumps({"rollback": "ok", "rolled_to": state["current"]["version"]},
                     indent=2, sort_keys=True))
    return 0


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="totem-updatectl",
        description="Pull-based app updater for kiosky-player (C14.1.1).",
    )
    sub = parser.add_subparsers(dest="cmd")
    sub.required = True

    sub.add_parser("status", help="Show updater state and current/previous links")
    sub.add_parser("self-test", help="Sanity check that updater can run on this device")

    p_check = sub.add_parser("check-github-latest",
                             help="Inspect the latest release on a GitHub repo")
    p_check.add_argument("--repo", required=True,
                         help="owner/repo, e.g. dadoohai/kiosky-player")

    p_apply = sub.add_parser("apply-github-latest",
                             help="Apply the latest release from a GitHub repo")
    p_apply.add_argument("--repo", required=True)

    p_url = sub.add_parser("apply-manifest-url",
                           help="Apply from an explicit manifest URL")
    p_url.add_argument("url")

    sub.add_parser("rollback", help="Roll back current -> previous")

    args = parser.parse_args(argv)
    handlers = {
        "status": cmd_status,
        "self-test": cmd_self_test,
        "check-github-latest": cmd_check_github_latest,
        "apply-github-latest": cmd_apply_github_latest,
        "apply-manifest-url": cmd_apply_manifest_url,
        "rollback": cmd_rollback,
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
