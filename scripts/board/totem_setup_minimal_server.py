#!/usr/bin/env python3
"""C8.1 minimal local setup server without real Wi-Fi.

This tool is intentionally narrow. It serves a local HTTP UI, validates the
operator input, and writes a mock/local config candidate under /tmp only. It
does not access external network, does not call shell commands, does not read
the real config, and does not write /data or /opt.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import json
import os
import pathlib
import re
import shutil
import stat
import sys
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs


sys.dont_write_bytecode = True

SCHEMA_VERSION = "dadooh-c8.1-setup-minimal-no-wifi.v1"
DEFAULT_BIND = "127.0.0.1"
DEFAULT_PORT = 8766
DEFAULT_OUT_DIR = "/tmp/dadooh-c8-1-setup-minimo"

CANDIDATE_FILENAME = "candidate-config.json"
STATUS_FILENAME = "status.json"
SUMMARY_FILENAME = "summary.txt"

TMP_ROOT = pathlib.Path("/tmp").resolve()
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
MAX_REQUEST_BYTES = 16 * 1024

SAFE_PLACEHOLDER_API_URL = "https://api.example.invalid/search"
SAFE_PLACEHOLDER_API_KEY = "API_KEY_PLACEHOLDER_C8_1_NOT_FOR_PRODUCTION"
SAFE_PLACEHOLDER_STATION_ID = "STATION_ID_PLACEHOLDER_C8_1"

ENVIRONMENT_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
URL_PATTERN_RE = re.compile(r"(?:https?://|www\.)", re.IGNORECASE)
PROHIBITED_ENVIRONMENT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url", URL_PATTERN_RE),
    ("api_key", re.compile(r"api[_-]?key", re.IGNORECASE)),
    ("token", re.compile(r"token", re.IGNORECASE)),
    ("secret", re.compile(r"secret", re.IGNORECASE)),
    ("password", re.compile(r"password", re.IGNORECASE)),
    ("senha", re.compile(r"senha", re.IGNORECASE)),
    ("slash", re.compile(r"[\\/]")),
)
ALLOWED_ROTATIONS = {0, 90, 180, 270}


class SetupError(ValueError):
    """Raised for expected C8.1 setup failures."""


def utc_timestamp() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def path_is_under(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def require_tmp_dir(raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path).expanduser()
    resolved = path.resolve(strict=False)

    if not path_is_under(resolved, TMP_ROOT):
        raise SetupError("out-dir must be under /tmp")
    if resolved == TMP_ROOT:
        raise SetupError("out-dir must be a dedicated directory under /tmp")
    if resolved.exists() and not resolved.is_dir():
        raise SetupError("out-dir exists and is not a directory")
    return resolved


def prepare_out_dir(path: pathlib.Path) -> None:
    path.mkdir(mode=PRIVATE_DIR_MODE, parents=True, exist_ok=True)
    if stat.S_IMODE(path.stat().st_mode) != PRIVATE_DIR_MODE:
        path.chmod(PRIVATE_DIR_MODE)


def ensure_output_target(path: pathlib.Path, out_dir: pathlib.Path) -> None:
    resolved_out = out_dir.resolve(strict=True)
    resolved_target = path.resolve(strict=False)
    if not path_is_under(resolved_target, resolved_out):
        raise SetupError("output target escaped out-dir")
    if resolved_target == resolved_out:
        raise SetupError("output target must be a file")

    for forbidden in (pathlib.Path("/data"), pathlib.Path("/opt")):
        if path_is_under(resolved_target, forbidden):
            raise SetupError("refusing to write outside /tmp")


def fsync_directory(path: pathlib.Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        fd = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_private_text(path: pathlib.Path, content: str, out_dir: pathlib.Path) -> None:
    ensure_output_target(path, out_dir)
    payload = content if content.endswith("\n") else content + "\n"
    tmp_name: str | None = None
    fd: int | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
            text=True,
        )
        os.fchmod(fd, PRIVATE_FILE_MODE)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        tmp_name = None
        path.chmod(PRIVATE_FILE_MODE)
        fsync_directory(path.parent)
    finally:
        if fd is not None:
            os.close(fd)
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass


def atomic_write_private_json(path: pathlib.Path, value: dict[str, Any], out_dir: pathlib.Path) -> None:
    atomic_write_private_text(path, json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True), out_dir)


def validate_environment_id(raw_value: Any) -> str:
    if not isinstance(raw_value, str):
        raise SetupError("environment_id must be a string")
    if raw_value != raw_value.strip():
        raise SetupError("environment_id must not contain whitespace")

    value = raw_value.strip()
    if not value:
        raise SetupError("environment_id must not be empty")
    if len(value) < 3:
        raise SetupError("environment_id must have at least 3 characters")
    if len(value) > 128:
        raise SetupError("environment_id must have at most 128 characters")
    if re.search(r"\s", value):
        raise SetupError("environment_id must not contain whitespace")

    for label, pattern in PROHIBITED_ENVIRONMENT_PATTERNS:
        if pattern.search(value):
            raise SetupError(f"environment_id must not contain {label}")

    if not ENVIRONMENT_ID_RE.fullmatch(value):
        raise SetupError("environment_id contains characters outside the allowlist")
    return value


def validate_rotation(raw_value: Any) -> int:
    if isinstance(raw_value, bool):
        raise SetupError("rotation must be one of 0, 90, 180 or 270")
    try:
        text = str(raw_value).strip()
    except Exception as exc:  # pragma: no cover - defensive only
        raise SetupError("rotation must be one of 0, 90, 180 or 270") from exc
    if not re.fullmatch(r"\d{1,3}", text):
        raise SetupError("rotation must be one of 0, 90, 180 or 270")
    value = int(text, 10)
    if value not in ALLOWED_ROTATIONS:
        raise SetupError("rotation must be one of 0, 90, 180 or 270")
    return value


def build_candidate_config(environment_id: str, rotation: int) -> dict[str, Any]:
    return {
        "api_key": SAFE_PLACEHOLDER_API_KEY,
        "api_url": SAFE_PLACEHOLDER_API_URL,
        "cache_dir": "/data/media/kiosky-player",
        "display_rotation_degrees": rotation,
        "environment_id": environment_id,
        "ipc_path": "/tmp/kiosky/mpv.sock",
        "low_resource_mode": False,
        "mpv_ao": "null",
        "mpv_gpu_context": "drm",
        "mpv_query_uses_fresh_ipc": True,
        "mpv_vo": "gpu",
        "runtime_dir": "/tmp/kiosky",
        "setup_source": "c8.1-minimal-local-no-wifi",
        "state_dir": "/data/state/kiosky-player",
        "station_id": SAFE_PLACEHOLDER_STATION_ID,
        "status_file": "/tmp/kiosky-status.json",
        "strict_paths_enabled": True,
    }


def build_status(generated_at: str, rotation: int) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "state": "candidate_ready",
        "flow": "setup_minimal_no_wifi_real",
        "files": {
            "candidate_config": CANDIDATE_FILENAME,
            "summary": SUMMARY_FILENAME,
            "status": STATUS_FILENAME,
        },
        "validation": {
            "environment_id": "format_validated_only",
            "rotation": "validated",
            "rotation_degrees": rotation,
            "backend_validation": "not_checked",
            "wifi_validation": "not_configured",
        },
        "guardrails": {
            "bind_default": DEFAULT_BIND,
            "writes_only_under_tmp": True,
            "real_config_read": False,
            "real_config_written": False,
            "data_written": False,
            "opt_written": False,
            "network_external_access": False,
            "commands_executed": False,
            "systemctl_called": False,
            "nmcli_called": False,
            "mpv_called": False,
            "backend_called": False,
            "wifi_changed": False,
        },
        "privacy": {
            "environment_id_raw_written_to_status": False,
            "environment_id_raw_written_to_summary": False,
            "credential_value_written_to_status": False,
            "credential_value_written_to_summary": False,
            "private_url_written_to_status": False,
            "private_url_written_to_summary": False,
            "status_contains_raw_payload": False,
            "summary_contains_raw_payload": False,
        },
    }


def build_summary(status: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Dadooh C8.1 setup minimo sem Wi-Fi real",
            "",
            f"schema_version: {status['schema_version']}",
            f"generated_at_utc: {status['generated_at_utc']}",
            f"state: {status['state']}",
            f"flow: {status['flow']}",
            "environment_id: format_validated_only",
            f"rotation_degrees: {status['validation']['rotation_degrees']}",
            "candidate_config: candidate-config.json",
            "summary: summary.txt",
            "status: status.json",
            "",
            "Guardrails:",
            "writes_only_under_tmp: true",
            "real_config_read: false",
            "real_config_written: false",
            "data_written: false",
            "opt_written: false",
            "network_external_access: false",
            "commands_executed: false",
            "systemctl_called: false",
            "nmcli_called: false",
            "mpv_called: false",
            "backend_called: false",
            "wifi_changed: false",
            "",
            "Privacy:",
            "environment_id_raw_written_to_summary: false",
            "credential_value_written_to_summary: false",
            "private_url_written_to_summary: false",
            "raw_payload_written_to_summary: false",
        ]
    )


def output_text(out_dir: pathlib.Path) -> str:
    parts = []
    for name in (STATUS_FILENAME, SUMMARY_FILENAME):
        path = out_dir / name
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def assert_sanitized_outputs(out_dir: pathlib.Path, environment_id: str) -> None:
    text = output_text(out_dir)
    if environment_id and environment_id in text:
        raise SetupError("privacy scan blocked raw environment_id in status/summary")
    for value in (SAFE_PLACEHOLDER_API_KEY, SAFE_PLACEHOLDER_API_URL):
        if value in text:
            raise SetupError("privacy scan blocked credential or URL in status/summary")


def write_setup_artifacts(out_dir: pathlib.Path, environment_id: str, rotation: int) -> dict[str, Any]:
    prepare_out_dir(out_dir)
    generated_at = utc_timestamp()
    candidate = build_candidate_config(environment_id, rotation)
    status = build_status(generated_at, rotation)

    atomic_write_private_json(out_dir / CANDIDATE_FILENAME, candidate, out_dir)
    atomic_write_private_json(out_dir / STATUS_FILENAME, status, out_dir)
    atomic_write_private_text(out_dir / SUMMARY_FILENAME, build_summary(status), out_dir)
    assert_sanitized_outputs(out_dir, environment_id)
    return status


def file_mode(path: pathlib.Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def parse_payload(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    raw_length = handler.headers.get("Content-Length", "0")
    try:
        length = int(raw_length)
    except ValueError as exc:
        raise SetupError("invalid content length") from exc
    if length < 0 or length > MAX_REQUEST_BYTES:
        raise SetupError("request too large")

    body = handler.rfile.read(length)
    content_type = handler.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            value = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SetupError("request body is not valid JSON") from exc
        if not isinstance(value, dict):
            raise SetupError("request body must be a JSON object")
        return value

    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def json_response(handler: BaseHTTPRequestHandler, code: int, value: dict[str, Any]) -> None:
    payload = json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def text_response(handler: BaseHTTPRequestHandler, code: int, content_type: str, value: str) -> None:
    payload = value.encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


HTML_PAGE = """<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Dadooh - Setup minimo</title>
    <style>
      :root {
        color-scheme: light;
        --ink: #17212f;
        --muted: #59677a;
        --line: #d9e1ec;
        --paper: #f7f8fb;
        --panel: #ffffff;
        --brand: #e8324a;
        --brand-dark: #68172f;
        --green: #1f7a5a;
        --blue: #0e5f8e;
        --amber: #b45e12;
        --radius: 8px;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        min-height: 100vh;
        color: var(--ink);
        background: var(--paper);
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        line-height: 1.45;
      }
      main {
        min-height: 100vh;
        display: grid;
        grid-template-columns: minmax(260px, 360px) minmax(0, 1fr);
      }
      aside {
        padding: 32px;
        color: #fff;
        background: linear-gradient(160deg, var(--brand), var(--brand-dark));
      }
      .brand {
        font-size: 34px;
        font-weight: 900;
        letter-spacing: 0;
      }
      .aside-text {
        max-width: 280px;
        margin-top: 18px;
        color: #fff5f6;
      }
      .steps {
        display: grid;
        gap: 8px;
        margin-top: 32px;
      }
      .steps span {
        padding: 10px 12px;
        border-radius: var(--radius);
        background: rgba(255, 255, 255, 0.14);
        font-size: 13px;
        font-weight: 750;
      }
      .workspace {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 28px;
      }
      .panel {
        width: min(100%, 760px);
        min-height: 520px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        border: 1px solid var(--line);
        border-radius: var(--radius);
        padding: clamp(22px, 4vw, 42px);
        background: var(--panel);
        box-shadow: 0 18px 45px rgba(23, 33, 47, 0.12);
      }
      .tag {
        display: inline-flex;
        width: fit-content;
        margin-bottom: 20px;
        padding: 6px 9px;
        border-radius: 999px;
        color: var(--muted);
        background: #edf2f7;
        font-size: 11px;
        font-weight: 850;
        text-transform: uppercase;
      }
      h1 {
        margin: 0 0 12px;
        font-size: clamp(30px, 6vw, 56px);
        line-height: 1.03;
        letter-spacing: 0;
      }
      p {
        margin: 0;
        color: var(--muted);
        font-size: 18px;
      }
      label {
        display: block;
        margin-bottom: 10px;
        color: var(--ink);
        font-weight: 800;
      }
      input {
        width: 100%;
        min-height: 56px;
        border: 1px solid var(--line);
        border-radius: var(--radius);
        padding: 13px 14px;
        color: var(--ink);
        font: inherit;
        font-size: 18px;
      }
      .actions, .rotation-row {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 28px;
      }
      button {
        min-height: 48px;
        border: 1px solid var(--line);
        border-radius: var(--radius);
        padding: 12px 16px;
        background: #fff;
        color: var(--ink);
        font: inherit;
        font-weight: 800;
      }
      button.primary {
        border-color: var(--brand);
        background: var(--brand);
        color: #fff;
      }
      button.secondary {
        color: var(--muted);
      }
      button.choice {
        min-width: 86px;
      }
      button.choice[aria-pressed="true"] {
        border-color: var(--blue);
        background: #eaf5fb;
        color: var(--blue);
      }
      .review {
        display: grid;
        gap: 10px;
        margin-top: 24px;
      }
      .review div {
        display: grid;
        grid-template-columns: 160px minmax(0, 1fr);
        gap: 12px;
        padding: 14px;
        border: 1px solid var(--line);
        border-radius: var(--radius);
      }
      .review span {
        color: var(--muted);
      }
      .review strong {
        overflow-wrap: anywhere;
      }
      .ok {
        color: var(--green);
        font-weight: 900;
      }
      .error {
        min-height: 24px;
        margin-top: 14px;
        color: #a8282f;
        font-size: 15px;
        font-weight: 750;
      }
      .hidden { display: none; }
      @media (max-width: 780px) {
        main { grid-template-columns: 1fr; }
        aside { padding: 22px; }
        .workspace { padding: 18px; }
        .panel { min-height: 500px; }
        .review div { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body>
    <main>
      <aside>
        <div class="brand">Dadooh</div>
        <p class="aside-text">Setup local minimo para liberar uma candidata de configuracao. Sem Wi-Fi real, sem backend e sem comandos operacionais.</p>
        <div class="steps" aria-label="Etapas">
          <span>Configuracao pendente</span>
          <span>Ambiente</span>
          <span>Rotacao</span>
          <span>Revisao</span>
          <span>Candidata pronta</span>
        </div>
      </aside>
      <section class="workspace">
        <div class="panel">
          <div id="screen"></div>
          <p id="error" class="error" role="status"></p>
        </div>
      </section>
    </main>
    <script>
      const state = { step: "pending", environmentId: "", rotation: 0 };
      const screen = document.querySelector("#screen");
      const errorBox = document.querySelector("#error");

      function setError(message) {
        errorBox.textContent = message || "";
      }

      function escapeText(value) {
        return String(value).replace(/[&<>"']/g, (char) => ({
          "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
        })[char]);
      }

      function render() {
        setError("");
        if (state.step === "pending") {
          screen.innerHTML = `
            <span class="tag">config_missing</span>
            <h1>Configuracao pendente</h1>
            <p>O totem precisa de uma configuracao antes de iniciar a exibicao.</p>
            <div class="actions"><button class="primary" data-action="start">Iniciar configuracao</button></div>
          `;
        } else if (state.step === "start") {
          screen.innerHTML = `
            <span class="tag">setup_start</span>
            <h1>Iniciar configuracao</h1>
            <p>Esta etapa cria apenas uma candidata local em /tmp. Wi-Fi, backend e escrita real ficam fora deste teste.</p>
            <div class="actions">
              <button class="primary" data-action="environment">Continuar</button>
              <button class="secondary" data-action="pending">Voltar</button>
            </div>
          `;
        } else if (state.step === "environment") {
          screen.innerHTML = `
            <span class="tag">environment_input</span>
            <h1>Informe o ambiente</h1>
            <p>Use um identificador de teste. Nao use dado real neste prototipo.</p>
            <div class="actions" style="display:block">
              <label for="environment">environment_id</label>
              <input id="environment" autocomplete="off" autocapitalize="off" spellcheck="false" value="${escapeText(state.environmentId)}" />
            </div>
            <div class="actions">
              <button class="primary" data-action="rotation">Continuar</button>
              <button class="secondary" data-action="start">Voltar</button>
            </div>
          `;
        } else if (state.step === "rotation") {
          screen.innerHTML = `
            <span class="tag">rotation_select</span>
            <h1>Orientacao da tela</h1>
            <p>Escolha a rotacao que combina com a instalacao fisica do display.</p>
            <div class="rotation-row">
              ${[0, 90, 180, 270].map((value) => `<button class="choice" data-rotation="${value}" aria-pressed="${state.rotation === value}">${value}</button>`).join("")}
            </div>
            <div class="actions">
              <button class="primary" data-action="review">Revisar</button>
              <button class="secondary" data-action="environment">Voltar</button>
            </div>
          `;
        } else if (state.step === "review") {
          screen.innerHTML = `
            <span class="tag">review</span>
            <h1>Revisar configuracao</h1>
            <p>Confira os dados digitados nesta sessao antes de gerar a candidata local.</p>
            <div class="review">
              <div><span>Ambiente</span><strong>${escapeText(state.environmentId)}</strong></div>
              <div><span>Rotacao</span><strong>${state.rotation} graus</strong></div>
              <div><span>Conexao</span><strong>Fora do escopo C8.1</strong></div>
            </div>
            <div class="actions">
              <button class="primary" data-action="save">Salvar simulado</button>
              <button class="secondary" data-action="rotation">Voltar</button>
            </div>
          `;
        } else {
          screen.innerHTML = `
            <span class="tag">candidate_ready</span>
            <h1>Configuracao candidata pronta</h1>
            <p class="ok">A candidata local foi gerada em /tmp com status e resumo sanitizados.</p>
            <div class="review">
              <div><span>Ambiente nesta sessao</span><strong>${escapeText(state.environmentId)}</strong></div>
              <div><span>Rotacao</span><strong>${state.rotation} graus</strong></div>
              <div><span>Arquivos</span><strong>candidate-config.json, status.json, summary.txt</strong></div>
            </div>
            <div class="actions"><button class="secondary" data-action="pending">Novo teste</button></div>
          `;
        }
      }

      async function saveCandidate() {
        const response = await fetch("/api/candidate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ environment_id: state.environmentId, rotation: state.rotation })
        });
        const data = await response.json();
        if (!response.ok || !data.ok) {
          throw new Error(data.error || "Nao foi possivel salvar a candidata.");
        }
        state.step = "ready";
        render();
      }

      document.addEventListener("click", async (event) => {
        const rotation = event.target.closest("[data-rotation]");
        if (rotation) {
          state.rotation = Number(rotation.dataset.rotation);
          render();
          return;
        }
        const button = event.target.closest("[data-action]");
        if (!button) return;
        const action = button.dataset.action;
        if (action === "rotation") {
          const input = document.querySelector("#environment");
          if (input) state.environmentId = input.value;
        }
        if (action === "save") {
          try {
            await saveCandidate();
          } catch (err) {
            setError(err.message);
          }
          return;
        }
        state.step = action;
        render();
      });

      render();
    </script>
  </body>
</html>
"""


class SetupRequestHandler(BaseHTTPRequestHandler):
    server_version = "DadoohC81Setup/1.0"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    @property
    def out_dir(self) -> pathlib.Path:
        return self.server.out_dir  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            text_response(self, HTTPStatus.OK, "text/html; charset=utf-8", HTML_PAGE)
            return
        if self.path == "/api/status":
            status_path = self.out_dir / STATUS_FILENAME
            if not status_path.exists():
                json_response(self, HTTPStatus.OK, {"ok": True, "state": "not_generated"})
                return
            try:
                with status_path.open("r", encoding="utf-8") as handle:
                    status = json.load(handle)
            except (OSError, json.JSONDecodeError):
                json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "status unavailable"})
                return
            json_response(self, HTTPStatus.OK, {"ok": True, "status": status})
            return
        json_response(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/api/candidate":
            json_response(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        try:
            payload = parse_payload(self)
            environment_id = validate_environment_id(payload.get("environment_id"))
            rotation = validate_rotation(payload.get("rotation"))
            status = write_setup_artifacts(self.out_dir, environment_id, rotation)
        except SetupError as exc:
            json_response(self, HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return
        except OSError:
            json_response(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "failed to write artifacts"})
            return

        json_response(
            self,
            HTTPStatus.OK,
            {
                "ok": True,
                "state": status["state"],
                "rotation_degrees": rotation,
                "files": {
                    "candidate_config": CANDIDATE_FILENAME,
                    "status": STATUS_FILENAME,
                    "summary": SUMMARY_FILENAME,
                },
            },
        )


def run_server(bind: str, port: int, out_dir: pathlib.Path) -> int:
    prepare_out_dir(out_dir)
    server = ThreadingHTTPServer((bind, port), SetupRequestHandler)
    server.out_dir = out_dir  # type: ignore[attr-defined]
    print(f"C8.1 setup minimal server listening on http://{bind}:{port}", flush=True)
    print(f"artifacts directory: {out_dir}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


def assert_raises(fn: Any, message: str) -> None:
    try:
        fn()
    except SetupError:
        return
    raise AssertionError(message)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_self_test() -> None:
    assert_true(validate_environment_id("ENV-C8_1.LOCAL:MOCK") == "ENV-C8_1.LOCAL:MOCK", "valid id rejected")
    assert_raises(lambda: validate_environment_id(""), "empty environment_id should fail")
    assert_raises(lambda: validate_environment_id("ENV C8"), "environment_id with space should fail")
    assert_raises(lambda: validate_environment_id("https://example.invalid/env"), "environment_id URL should fail")
    assert_raises(lambda: validate_environment_id("ENV/C8"), "environment_id with slash should fail")
    assert_raises(lambda: validate_environment_id("token-C8"), "environment_id with token should fail")
    assert_raises(lambda: validate_environment_id("secret-C8"), "environment_id with secret should fail")
    assert_true(validate_rotation("0") == 0, "rotation 0 rejected")
    assert_true(validate_rotation(90) == 90, "rotation 90 rejected")
    assert_true(validate_rotation("180") == 180, "rotation 180 rejected")
    assert_true(validate_rotation("270") == 270, "rotation 270 rejected")
    assert_raises(lambda: validate_rotation("45"), "invalid rotation should fail")
    assert_raises(lambda: require_tmp_dir("/var/tmp/dadooh-c8-1"), "out-dir outside /tmp should fail")

    root = pathlib.Path(tempfile.mkdtemp(prefix="dadooh-c8-1-self-test-", dir="/tmp"))
    environment_id = "ENV-C8-1-SELFTEST:LOCAL.MOCK"
    try:
        out_dir = require_tmp_dir(str(root / "out"))
        status = write_setup_artifacts(out_dir, environment_id, 90)
        assert_true(status["state"] == "candidate_ready", "status should be candidate_ready")
        assert_true(file_mode(out_dir) == PRIVATE_DIR_MODE, "out-dir mode should be 700")
        generated_paths = [
            out_dir / CANDIDATE_FILENAME,
            out_dir / STATUS_FILENAME,
            out_dir / SUMMARY_FILENAME,
        ]
        for path in generated_paths:
            assert_true(path.exists(), f"{path.name} should exist")
            assert_true(file_mode(path) == PRIVATE_FILE_MODE, f"{path.name} mode should be 600")
            resolved = path.resolve(strict=True)
            assert_true(path_is_under(resolved, TMP_ROOT), f"{path.name} should be under /tmp")
            assert_true(not path_is_under(resolved, pathlib.Path("/data")), f"{path.name} wrote under /data")
            assert_true(not path_is_under(resolved, pathlib.Path("/opt")), f"{path.name} wrote under /opt")

        with (out_dir / CANDIDATE_FILENAME).open("r", encoding="utf-8") as handle:
            candidate = json.load(handle)
        assert_true(candidate["environment_id"] == environment_id, "candidate should include environment_id")
        assert_true(candidate["display_rotation_degrees"] == 90, "candidate should include rotation")
        assert_true(candidate["api_key"] == SAFE_PLACEHOLDER_API_KEY, "candidate should use safe placeholder")

        text = output_text(out_dir)
        assert_true(environment_id not in text, "summary/status leaked raw environment_id")
        assert_true(SAFE_PLACEHOLDER_API_KEY not in text, "summary/status leaked credential placeholder")
        assert_true(SAFE_PLACEHOLDER_API_URL not in text, "summary/status leaked URL placeholder")
        assert_true("api_key" not in text.lower(), "summary/status should not include api_key label")
        assert_true("token" not in text.lower(), "summary/status should not include token label")
        assert_true(status["guardrails"]["data_written"] is False, "status should mark data_written false")
        assert_true(status["guardrails"]["opt_written"] is False, "status should mark opt_written false")
        assert_true(status["guardrails"]["systemctl_called"] is False, "status should mark systemctl false")
        assert_true(status["guardrails"]["nmcli_called"] is False, "status should mark nmcli false")
        assert_true(status["guardrails"]["mpv_called"] is False, "status should mark mpv false")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve the C8.1 minimal local setup UI without real Wi-Fi.",
        allow_abbrev=False,
    )
    parser.add_argument("--bind", default=DEFAULT_BIND, help=f"Bind address. Default: {DEFAULT_BIND}")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"TCP port. Default: {DEFAULT_PORT}")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help=f"Output directory under /tmp. Default: {DEFAULT_OUT_DIR}")
    parser.add_argument("--self-test", action="store_true", help="Run local C8.1 self-tests under /tmp and exit.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.self_test:
            run_self_test()
            print("self-test: ok")
            return 0

        out_dir = require_tmp_dir(args.out_dir)
        if not (1 <= args.port <= 65535):
            raise SetupError("port must be between 1 and 65535")
        return run_server(args.bind, args.port, out_dir)
    except SetupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except AssertionError:
        print("error: self-test failed", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
