#!/usr/bin/env python3
# C18.RUNTIME.B9 soak driver: hammer mpv loadfile-replace via IPC, measure the metrics
# that define the original media_load_failed (loadfile ACK > 2s) + hwdec/zero-copy stability.
import socket, json, sys, time, os, select

sock_path, mpvpid, dur = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
clips = ["/tmp/dadooh_assets/a_1080p30.mp4",
         "/tmp/dadooh_assets/b_720p30.mp4",
         "/tmp/dadooh_assets/c_1080p25.mp4"]
HZ = os.sysconf("SC_CLK_TCK")

s = None
for _ in range(60):
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.connect(sock_path); break
    except Exception:
        time.sleep(0.25); s = None
if not s:
    print("RESULT=FAIL reasons=IPC_CONNECT_FAIL"); sys.exit(2)
s.setblocking(False)
buf = b""; rid = 0

def pump(deadline, want_rid=None, want_event=None):
    global buf
    evs = []
    while time.time() < deadline:
        to = max(0, deadline - time.time())
        r, _, _ = select.select([s], [], [], to)
        if not r: break
        try: data = s.recv(65536)
        except BlockingIOError: continue
        except OSError: return (None, evs, True)   # socket error -> mpv gone
        if not data: return (None, evs, True)       # closed -> mpv gone
        buf += data
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            if not line.strip(): continue
            try: msg = json.loads(line.decode("utf-8", "replace"))
            except Exception: continue
            if "event" in msg:
                evs.append(msg["event"])
                if want_event and msg["event"] == want_event: return (None, evs, False)
            elif "request_id" in msg:
                if want_rid is not None and msg["request_id"] == want_rid: return (msg, evs, False)
    return (None, evs, False)

def command(cmd, timeout=5.0):
    global rid
    rid += 1; myid = rid
    t0 = time.time()
    try: s.sendall((json.dumps({"command": cmd, "request_id": myid}) + "\n").encode())
    except OSError: return (False, (time.time()-t0)*1000, None, True)
    reply, _, dead = pump(t0 + timeout, want_rid=myid)
    el = (time.time() - t0) * 1000
    ok = reply is not None and reply.get("error") == "success"
    return ok, el, (reply.get("data") if reply else None), dead

def cpu_ticks(pid):
    try:
        with open(f"/proc/{pid}/stat") as f: p = f.read().rsplit(")", 1)[1].split()
        return int(p[11]) + int(p[12])  # utime+stime (fields 14,15; index after ')')
    except Exception: return None

c0 = cpu_ticks(mpvpid); t_start = time.time()
n = 0; ack_max = 0.0; ack_sum = 0.0; ack_to = 0; load_max = 0.0; load_to = 0
stalls = 0; errors = 0; hwdec_lost = 0; crashed = False
acks = []; hwdec_samples = {}
deadline = t_start + dur; i = 0
while time.time() < deadline:
    if not os.path.exists(f"/proc/{mpvpid}"):
        crashed = True; break
    clip = clips[i % len(clips)]; i += 1
    ok, ack, _, dead = command(["loadfile", clip, "replace"], timeout=5.0)
    if dead: crashed = True; break
    n += 1; ack_sum += ack; acks.append(ack)
    if ack > ack_max: ack_max = ack
    if ack > 2000: ack_to += 1
    if not ok: errors += 1
    t0 = time.time(); _, evs, dead = pump(t0 + 10.0, want_event="file-loaded"); load = (time.time()-t0)*1000
    if dead: crashed = True; break
    if "file-loaded" not in evs:
        stalls += 1
    else:
        if load > load_max: load_max = load
        if load > 2000: load_to += 1
    okh, _, hw, dead = command(["get_property", "hwdec-current"], timeout=3.0)
    if dead: crashed = True; break
    hw = str(hw); hwdec_samples[hw] = hwdec_samples.get(hw, 0) + 1
    if "v4l2request" not in hw: hwdec_lost += 1
    time.sleep(2.0)
    if n % 25 == 0:
        ct = cpu_ticks(mpvpid)
        cpu_pct = ((ct - c0) / HZ) / (time.time() - t_start) * 100 if ct else -1
        print(f"progress n={n} ack_max={ack_max:.0f}ms ack_to={ack_to} load_max={load_max:.0f}ms "
              f"stalls={stalls} hwdec_lost={hwdec_lost} cpu_avg%={cpu_pct:.1f}", flush=True)

c1 = cpu_ticks(mpvpid); total_t = time.time() - t_start
cpu_s = (c1 - c0) / HZ if (c1 and c0) else -1
acks.sort(); p95 = acks[int(len(acks) * 0.95)] if acks else 0
print("=== SOAK SUMMARY ===")
print(f"duration_s={total_t:.0f} transitions={n}")
print(f"ack_ms avg={ack_sum/max(1,n):.1f} p95={p95:.0f} max={ack_max:.0f}")
print(f"ack_timeouts_gt2s={ack_to} load_timeouts_gt2s={load_to} stalls_no_fileloaded={stalls} ipc_errors={errors}")
print(f"hwdec_samples={hwdec_samples} hwdec_lost_not_v4l2request={hwdec_lost}")
print(f"mpv_cpu_s={cpu_s:.1f} cpu_pct_of_one_core={cpu_s/total_t*100:.1f}" if cpu_s>=0 else "mpv_cpu=unknown")
fail = []
if crashed: fail.append("MPV_CRASH")
if ack_to > 0 or load_to > 0: fail.append("IPC_TIMEOUT_STILL_PRESENT")
if hwdec_lost > 0: fail.append("HWDEC_LOST_ON_TRANSITION")
if stalls > 0: fail.append("STALLS_PRESENT")
if errors > 0: fail.append("IPC_ERRORS")
if cpu_s >= 0 and cpu_s/total_t*100 > 80: fail.append("CPU_TOO_HIGH")
print("RESULT=FAIL reasons=" + ",".join(fail) if fail else "RESULT=ZERO_COPY_LOADFILE_SOAK_PASSED")
