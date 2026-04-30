#!/usr/bin/env bash
set -eu

umask 077

BASE_DIR="${TOTEM_DIAG_BASE:-/root/totem-diag}"
TIMESTAMP="${TOTEM_DIAG_TIMESTAMP:-$(date +%Y%m%d-%H%M%S%z)}"
RUN_NAME="playlist-media-classification-$TIMESTAMP"
OUT_DIR="$BASE_DIR/$RUN_NAME"
ARCHIVE="$BASE_DIR/$RUN_NAME.tar.gz"

STATE_DIR="${KIOSKY_STATE_DIR:-/data/state/kiosky-player}"
CACHE_DIR="${KIOSKY_CACHE_DIR:-/data/media/kiosky-player}"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root." >&2
  exit 1
fi

command -v python3 >/dev/null 2>&1 || {
  echo "ERROR: python3 not found." >&2
  exit 127
}

mkdir -p "$OUT_DIR"

stamp() {
  date '+%Y-%m-%dT%H:%M:%S%z'
}

{
  echo "playlist_media_classification_version=1"
  echo "timestamp=$TIMESTAMP"
  echo "created_at=$(stamp)"
  echo "output_dir=$OUT_DIR"
  echo "archive=$ARCHIVE"
  echo "state_source=playlist_last.json/cache_index.json when present"
  echo "cache_source=local cache scan fallback"
} >"$OUT_DIR/manifest.txt"

python3 - "$STATE_DIR" "$CACHE_DIR" "$OUT_DIR" <<'PY'
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
from urllib.parse import urlparse

state_dir, cache_dir, out_dir = sys.argv[1:]
playlist_path = os.path.join(state_dir, "playlist_last.json")
cache_index_path = os.path.join(state_dir, "cache_index.json")

IMAGE_EXTENSIONS = {
    ".apng",
    ".avif",
    ".bmp",
    ".gif",
    ".heic",
    ".heif",
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
IMAGE_CODECS = {
    "apng",
    "bmp",
    "gif",
    "jpeg2000",
    "jpegls",
    "mjpeg",
    "png",
    "tiff",
    "webp",
}


def sha1_short(value):
    return hashlib.sha1(str(value).encode("utf-8"), usedforsecurity=False).hexdigest()[:10]


def safe_path_alias(value):
    if not isinstance(value, str) or not value:
        return ""
    if "://" in value:
        return f"<redacted-url:{sha1_short(value)}>"
    if value.startswith("/data/media/") or value.startswith("/tmp/"):
        return f"<media-path:{sha1_short(value)}>"
    if value.startswith("/data/"):
        return f"<data-path:{sha1_short(value)}>"
    if value.startswith("/"):
        return f"<local-path:{sha1_short(value)}>"
    return f"<filename:{sha1_short(value)}>"


def media_alias(path="", url=""):
    source = url or path or ""
    return f"media-{sha1_short(source)}" if source else ""


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh), ""
    except FileNotFoundError:
        return None, "missing"
    except Exception as exc:
        return None, type(exc).__name__


def safe_int(value):
    if value in (None, ""):
        return ""
    try:
        return str(int(float(value)))
    except Exception:
        return ""


def safe_float(value):
    if value in (None, ""):
        return ""
    try:
        parsed = float(value)
    except Exception:
        return ""
    if not math.isfinite(parsed):
        return ""
    return f"{parsed:.6f}".rstrip("0").rstrip(".")


def parse_fraction(value):
    if not isinstance(value, str) or not value or value == "0/0":
        return ""
    if "/" in value:
        left, right = value.split("/", 1)
        try:
            den = float(right)
            if den == 0:
                return ""
            return safe_float(float(left) / den)
        except Exception:
            return ""
    return safe_float(value)


def command_exists(name):
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return True
    return False


def ffprobe_media(path):
    if not command_exists("ffprobe"):
        return {"ok": False, "note": "ffprobe_not_found"}
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate",
                "-of",
                "json",
                path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        return {"ok": False, "note": type(exc).__name__}
    if proc.returncode != 0:
        return {"ok": False, "note": f"ffprobe_rc_{proc.returncode}"}
    try:
        data = json.loads(proc.stdout or "{}")
    except Exception:
        return {"ok": False, "note": "ffprobe_json_parse_error"}
    return {"ok": True, "data": data, "note": ""}


def normalize_item(index, raw, cache_by_url, cache_by_path):
    raw = raw if isinstance(raw, dict) else {}
    path = raw.get("path") if isinstance(raw.get("path"), str) else ""
    url = raw.get("url") if isinstance(raw.get("url"), str) else ""
    meta = {}
    if path and path in cache_by_path:
        meta.update(cache_by_path[path])
    if not path and url and url in cache_by_url:
        path, by_url_meta = cache_by_url[url]
        meta.update(by_url_meta)
    duration_ms = raw.get("duration_ms", meta.get("duration_ms", ""))
    return {
        "item_index": index,
        "path": path,
        "url": url,
        "duration_ms_config": safe_int(duration_ms),
        "source": raw.get("_source", ""),
    }


playlist_data, playlist_error = load_json(playlist_path)
cache_data, cache_error = load_json(cache_index_path)

cache_items = {}
if isinstance(cache_data, dict) and isinstance(cache_data.get("items"), dict):
    cache_items = {
        path: meta
        for path, meta in cache_data["items"].items()
        if isinstance(path, str) and isinstance(meta, dict)
    }

cache_by_url = {}
for path, meta in cache_items.items():
    url = meta.get("url")
    if isinstance(url, str) and url:
        cache_by_url[url] = (path, meta)

raw_items = []
source = ""
if isinstance(playlist_data, dict) and isinstance(playlist_data.get("playlist"), list):
    source = "playlist_last.json"
    for raw in playlist_data["playlist"]:
        if isinstance(raw, dict):
            item = dict(raw)
            item["_source"] = source
            raw_items.append(item)
elif cache_items:
    source = "cache_index.json"
    for path, meta in sorted(cache_items.items()):
        item = dict(meta)
        item["path"] = path
        item["_source"] = source
        raw_items.append(item)
else:
    source = "cache_dir_scan"
    try:
        names = sorted(os.listdir(cache_dir))
    except OSError:
        names = []
    for name in names:
        path = os.path.join(cache_dir, name)
        if os.path.isfile(path) and not name.endswith(".tmp"):
            raw_items.append({"path": path, "_source": source})

items = [
    normalize_item(index, raw, cache_by_url, cache_items)
    for index, raw in enumerate(raw_items, start=1)
]

rows = []
summary = {
    "total_items": len(items),
    "local_files": 0,
    "video_progress_expected": 0,
    "static_image_expected": 0,
    "unknown": 0,
    "ffprobe_available": "yes" if command_exists("ffprobe") else "no",
    "playlist_last_json": "present" if playlist_error == "" else playlist_error,
    "cache_index_json": "present" if cache_error == "" else cache_error,
    "item_source": source,
}

for item in items:
    path = item["path"]
    url = item["url"]
    alias = safe_path_alias(path) or safe_path_alias(url) or media_alias(path, url) or f"item-{item['item_index']}"
    app_alias = media_alias(path, url)
    ext = os.path.splitext(urlparse(path).path)[1].lower() if path else ""
    exists = bool(path and os.path.isfile(path))
    size_bytes = ""
    ffprobe_ok = "no"
    has_video_stream = "unknown"
    has_image_stream = "unknown"
    codec = ""
    resolution = ""
    fps = ""
    duration_sec = ""
    note = ""

    if exists:
        summary["local_files"] += 1
        try:
            size_bytes = str(os.path.getsize(path))
        except OSError:
            size_bytes = ""
        probe = ffprobe_media(path)
        ffprobe_ok = "yes" if probe.get("ok") else "no"
        note = str(probe.get("note") or "")
        if probe.get("ok"):
            data = probe.get("data") or {}
            streams = data.get("streams") if isinstance(data.get("streams"), list) else []
            video_streams = [s for s in streams if isinstance(s, dict) and s.get("codec_type") == "video"]
            codecs = []
            widths = []
            heights = []
            frame_rates = []
            for stream in video_streams:
                codec_name = stream.get("codec_name")
                if isinstance(codec_name, str) and codec_name:
                    codecs.append(codec_name)
                width = stream.get("width")
                height = stream.get("height")
                if isinstance(width, int):
                    widths.append(width)
                if isinstance(height, int):
                    heights.append(height)
                frame_rate = parse_fraction(stream.get("avg_frame_rate")) or parse_fraction(stream.get("r_frame_rate"))
                if frame_rate:
                    frame_rates.append(frame_rate)
            has_video_stream = "yes" if video_streams else "no"
            image_by_ext = ext in IMAGE_EXTENSIONS
            image_by_codec = any(c in IMAGE_CODECS for c in codecs)
            has_image_stream = "yes" if image_by_ext or image_by_codec else "no"
            codec = ",".join(sorted(set(codecs)))
            if widths and heights:
                resolution = f"{widths[0]}x{heights[0]}"
            if frame_rates:
                fps = frame_rates[0]
            fmt = data.get("format") if isinstance(data.get("format"), dict) else {}
            duration_sec = safe_float(fmt.get("duration"))
        else:
            image_by_ext = ext in IMAGE_EXTENSIONS
            has_image_stream = "yes" if image_by_ext else "unknown"
            has_video_stream = "unknown"

        if has_image_stream == "yes":
            classification = "static_image_expected"
            expected = "validate_load_or_display_presence; time-pos/frame may be unavailable"
        elif has_video_stream == "yes":
            classification = "video_progress_expected"
            expected = "validate time-pos and frame progression"
        else:
            classification = "unknown"
            expected = "manual review required"
    else:
        classification = "unknown"
        expected = "local file missing or unresolved; manual review required"
        note = "local_file_missing_or_unresolved"

    summary[classification] += 1
    rows.append(
        {
            "item_index": str(item["item_index"]),
            "alias": alias,
            "app_alias": app_alias,
            "source": item["source"],
            "local_file": "yes" if exists else "no",
            "extension": ext,
            "size_bytes": size_bytes,
            "ffprobe_ok": ffprobe_ok,
            "has_video_stream": has_video_stream,
            "has_image_stream": has_image_stream,
            "codec": codec,
            "resolution": resolution,
            "fps": fps,
            "duration_ms_config": item["duration_ms_config"],
            "duration_sec_ffprobe": duration_sec,
            "classification": classification,
            "validation_expected": expected,
            "note": note,
        }
    )

classification_path = os.path.join(out_dir, "playlist-media-classification.tsv")
fieldnames = [
    "item_index",
    "alias",
    "app_alias",
    "source",
    "local_file",
    "extension",
    "size_bytes",
    "ffprobe_ok",
    "has_video_stream",
    "has_image_stream",
    "codec",
    "resolution",
    "fps",
    "duration_ms_config",
    "duration_sec_ffprobe",
    "classification",
    "validation_expected",
    "note",
]
with open(classification_path, "w", encoding="utf-8", newline="") as fh:
    writer = csv.DictWriter(fh, delimiter="\t", fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)

with open(os.path.join(out_dir, "playlist-media-summary.tsv"), "w", encoding="utf-8", newline="") as fh:
    writer = csv.writer(fh, delimiter="\t")
    writer.writerow(["metric", "value"])
    for key in [
        "total_items",
        "local_files",
        "video_progress_expected",
        "static_image_expected",
        "unknown",
        "ffprobe_available",
        "playlist_last_json",
        "cache_index_json",
        "item_source",
    ]:
        writer.writerow([key, summary.get(key, "")])

with open(os.path.join(out_dir, "playlist-media-classification.json"), "w", encoding="utf-8") as fh:
    json.dump({"summary": summary, "items": rows}, fh, indent=2, sort_keys=True)

print("metric\tvalue")
for key in [
    "total_items",
    "local_files",
    "video_progress_expected",
    "static_image_expected",
    "unknown",
    "ffprobe_available",
    "playlist_last_json",
    "cache_index_json",
    "item_source",
]:
    print(f"{key}\t{summary.get(key, '')}")
print("")
print("item_index\talias\tclassification\textension\tsize_bytes\tcodec\tresolution\tfps\tduration_ms_config\tduration_sec_ffprobe")
for row in rows:
    print(
        "\t".join(
            [
                row["item_index"],
                row["alias"],
                row["classification"],
                row["extension"],
                row["size_bytes"],
                row["codec"],
                row["resolution"],
                row["fps"],
                row["duration_ms_config"],
                row["duration_sec_ffprobe"],
            ]
        )
    )
PY

if command -v tar >/dev/null 2>&1; then
  tar -C "$BASE_DIR" -czf "$ARCHIVE" "$RUN_NAME"
  tar_rc=$?
  if [ "$tar_rc" -eq 0 ]; then
    echo "Playlist media classification directory: $OUT_DIR"
    echo "Archive: $ARCHIVE"
  else
    echo "ERROR: failed to create archive $ARCHIVE" >&2
    exit "$tar_rc"
  fi
else
  echo "ERROR: tar not found; classification directory kept at $OUT_DIR" >&2
  exit 127
fi
