# C12.3.13 Insmod And Black Screen Triage Evidence

Date: 2026-05-08

Scope:

- board category: `lab_board`
- image under test: `c12.1.10`
- initramfs diagnostic hook installed: `true`
- reboot executed: `true`
- SSH returned: `true`
- diagnostic hook removed after collection: `true`
- rollback executed: `true`
- raw logs published: `false`
- writer called: `false`
- real config written: `false`
- Wi-Fi/NetworkManager changed: `false`
- packages installed: `false`
- poweroff executed: `false`

## Read-only / Overlay

- `read_only_enabled=false`
- `overlay_active=false`
- `root_write_blocked=false`
- `/data writable=true`
- `/tmp writable=true`
- `/run writable=true`

Diagnostic categories:

- `overlay_ko_path_resolved=true`
- `overlay_ko_file_type=plain_ko`
- `overlay_ko_size_bucket=empty`
- `uname_kernel_matches_module_path=true`
- `vermagic_match=unknown`
- `dependencies_detected=none`
- `dependencies_present=unknown`
- `modules_dep_exists=true`
- `modules_dep_references_overlay=false`
- `modprobe_overlay_rc=zero`
- `modprobe_error_category=no_message`
- `overlay_in_proc_after_modprobe=false`
- `insmod_overlay_attempted=true`
- `insmod_overlay_rc=nonzero`
- `insmod_error_category=unknown`
- `dmesg_category=no_message`
- `overlay_in_proc_filesystems_after=false`

Classification:

```text
OVERLAY_MODULE_EMPTY_OR_STUB_IN_INITRAMFS
```

The runner-level fallback category was `OVERLAY_INSMOD_OTHER`, but the
actionable fields show the resolved `overlay.ko` artifact in initramfs is empty
and `modules.dep` does not reference it. This explains the nonzero `insmod`
without requiring raw stderr or dmesg publication.

Recommended read-only next step:

```text
C12.1.11_REBUILD_WITH_NONEMPTY_OVERLAY_MODULE_AND_COHERENT_MODULES_DEP
```

## Config Missing Visual

- `public_state=config_missing`
- `status.svg exists=true`
- `status.svg valid=true`
- `status.svg contains visible text=true`
- `renderer_process_count=1`
- `MPV_process_count=1`
- `mpv_vo_context_category=gpu`
- `drm_status_category=connected_present`
- `getty_visible_active=false`
- `screenshot_saved=false`

Classification:

```text
SVG_VALID_BUT_NOT_PRESENTED_BY_MPV
```

Human follow-up:

```text
HARDWARE_DISPLAY_ISSUE_RESOLVED
```

The HDMI black screen was later identified by the operator as a display
hardware issue and resolved outside the product software. No visual product
patch is required from this evidence.

## Final Status

- `ready_for_c12_4=false`
- `read_only_validated=false`
- `c12_4_blocked=true`

No secrets, real config, SSID/password, IP/MAC/DNS or raw logs are included.
