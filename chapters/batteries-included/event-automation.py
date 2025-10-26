import datetime
import json
import re
import socket
import time

import requests
from netmiko import ConnectHandler
<<<<<<< HEAD
from rca import generate_rca
=======
from prefect import flow, tags, task
from prefect.blocks.system import Secret
>>>>>>> origin/df/cisco-devnet

NAUTOBOT_URL = "http://localhost:8080"
PROM_URL = "http://localhost:9090"
ALERTMANAGER_URL = "http://localhost:9093"
LOKI_URL = "http://localhost:3001"
IFACE_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9/-]+")
SLACK_API = "https://slack.com/api/chat.postMessage"


def canon_iface(s: str) -> str:
    """
    Return a clean interface token suitable for CLI:
    - take the first continuous token like 'Ethernet2', 'Gi1/0/1', 'Port-Channel1'
    - strip anything after spaces, parentheses, commas, etc.
    - keep case as-is (EOS is case-insensitive, but your names are fine)
    """
    s = (s or "").strip()
    m = IFACE_TOKEN_RE.match(s)
    return m.group(0) if m else s


def _limit_name(device: str, interface: str) -> str:
    return f"link:{device}:{interface}".replace("/", "-").lower()


def link_key(device: str, interface: str) -> str:
    return f"{device}:{interface}".lower().replace("/", "-")


def artifact_key(*parts: str) -> str:
    """
    Build a Prefect artifact key:
    - join parts with '-'
    - lowercase
    - keep only [a-z0-9-]
    - collapse multiple dashes
    """
    s = "-".join(p for p in parts if p)
    s = s.lower()
    s = re.sub(r"[^a-z0-9-]+", "-", s)  # replace /, _, spaces, etc.
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "artifact"


def pause(seconds: int, reason: str = "demo"):
    # print(f"⏸️  [Pause] {reason} for {seconds}s...")
    time.sleep(seconds)
    # print("▶️  [Pause] Resuming.")


@task(retries=3, log_prints=True, task_run_name="resolve_host[{device}]")
def resolve_device_host(device: str) -> str:
    """
    Prefer Nautobot primary_ip4; fallback to DNS on the device name.
    Returns a connectable host string for Netmiko.
    """
    print(f"🧠 [Resolver] Starting host resolution for {device}")
    try:
        socket.getaddrinfo(device, 22)
        print(f"✅ [Resolver] Using DNS for {device}: {device}")
        return device
    except OSError:
        msg = f"❌ [Resolver] Could not resolve host for {device} via DNS"
        print(msg)
        raise RuntimeError(msg) from None


@task(log_prints=True)
def slack_post(channel: str, text: str, thread_ts: str | None = None) -> str | None:
    token = Secret.load("slack-bot-token").get()  # type: ignore
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-type": "application/json; charset=utf-8",
    }
    body = {"channel": channel, "text": text}
    if thread_ts:
        body["thread_ts"] = thread_ts

    r = requests.post(SLACK_API, headers=headers, json=body, timeout=10)
    data = r.json()
    if not data.get("ok"):
        print(f"❌ [Slack] {data}")
        return None
    ts = data.get("ts")
    print(f"✅ [Slack] posted {'thread reply' if thread_ts else 'message'} ts={ts}")
    return ts


# ---------- SoT helpers ----------


# ---------- Netmiko helpers (neutral commands) ----------


def _netmiko_connect(host: str):
    user = Secret.load("net-user").get()  # type: ignore
    pwd = Secret.load("net-pass").get()  # type: ignore
    resolved_host = resolve_device_host(host)
    return ConnectHandler(
        device_type=Secret.load("net-device-type").get(),  # type: ignore
        host=resolved_host,
        username=user,
        password=pwd,
        fast_cli=True,
    )


@task(retries=2, log_prints=True, task_run_name="bgp_asn[{device}]")
def get_local_bgp_asn(device: str) -> str:
    """Parse local BGP ASN from running-config."""
    pause(5, "pre-BGP ASN fetch pause for demo")
    with _netmiko_connect(device) as conn:
        conn.enable()
        cfg = conn.send_command(
            "show running-config section router bgp", use_textfsm=False
        )
    cfg = str(cfg)  # Ensure cfg is a string
    m = re.search(r"^router\s+bgp\s+(\d+)", cfg, flags=re.MULTILINE)
    if not m:
        raise RuntimeError(f"Could not find local BGP ASN on {device}")
    asn = m.group(1)
    print(f"🔎 [BGP] Local ASN on {device} = {asn}")
    return asn


@task(
    retries=2, log_prints=True, task_run_name="neighbor_on_iface[{device}:{interface}]"
)
def get_neighbor_on_interface(device: str, interface: str) -> str | None:
    """
    Returns the BGP neighbor IP that is on the same subnet as <device>/<interface>.
    EOS JSON paths handled:
      interfaces[IFACE].interfaceAddress.primaryIp.{address,maskLen}
      interfaces[IFACE].interfaceAddressBrief.ipAddr.{address,maskLen}
    """
    import ipaddress as ip

    pause(5, "pre-neighbor lookup pause for demo")
    iface = canon_iface(interface)
    with _netmiko_connect(device) as conn:
        conn.enable()

        # --- 1) Get interface primary IP (address/maskLen) via JSON
        out = conn.send_command(f"show ip interface {iface} | json", use_textfsm=False)
        try:
            data = json.loads(str(out))
        except Exception as e:
            print(f"⚠️ [BGP] JSON parse failed for 'show ip interface {iface}': {e}")
            return None

        intf = (data.get("interfaces") or {}).get(iface, {})
        primary = (
            ((intf.get("interfaceAddress") or {}).get("primaryIp"))
            or ((intf.get("interfaceAddressBrief") or {}).get("ipAddr"))
            or {}
        )
        addr = primary.get("address")
        mlen = primary.get("maskLen")
        if not addr or mlen is None:
            print(f"⚠️ [BGP] No primary IP found on {device}/{iface}")
            return None

        pfx = f"{addr}/{mlen}"
        net = ip.ip_network(pfx, strict=False)
        lip = ip.ip_address(addr)
        print(f"✅ [BGP] {device}/{iface} has IP {pfx}")

        # --- 2) List configured neighbors from BGP running-config
        bgp = conn.send_command(
            "show running-config section router bgp", use_textfsm=False
        )
        bgp = str(bgp)  # Ensure bgp is a string
        neigh_ips = re.findall(
            r"^\s*neighbor\s+(\d+\.\d+\.\d+\.\d+)\s+remote-as\s+\d+",
            bgp,
            flags=re.MULTILINE,
        )
        if not neigh_ips:
            print(f"⚠️ [BGP] No neighbors found in BGP config on {device}")
            return None

        # --- 3) Pick the neighbor that shares the subnet with the interface IP
        candidates = []
        for nip in neigh_ips:
            ipn = ip.ip_address(nip)
            if ipn != lip and ipn in net:
                candidates.append(nip)

        if not candidates:
            print(
                f"⚠️ [BGP] No neighbor IP in {net} found on {device} for {iface}. "
                f"Neighbors seen: {', '.join(neigh_ips)}"
            )
            return None

        if len(candidates) > 1:
            print(
                f"ℹ️ [BGP] Multiple neighbors on {net}: {candidates} — choosing {candidates[0]}"
            )

        neighbor_ip = candidates[0]
        print(f"✅ [BGP] {device}/{iface} → neighbor {neighbor_ip} (subnet {net})")
        return neighbor_ip


@task(retries=2, log_prints=True, task_run_name="bgp_shutdown[{device}:{neighbor}]")
def bgp_neighbor_shutdown(device: str, neighbor: str):
    """Shut the BGP neighbor (local side only)."""
    pause(5, "pre-shutdown pause for demo")
    asn = get_local_bgp_asn(device)
    print(f"🚧 [BGP] Shutting neighbor {neighbor} on {device} (ASN {asn})")
    with _netmiko_connect(device) as conn:
        conn.enable()
        conn.send_config_set(
            [
                f"router bgp {asn}",
                f"neighbor {neighbor} shutdown",
                f"neighbor {neighbor} description QUARANTINED_BY_PREFECT",
            ]
        )
        try:
            conn.save_config()
        except Exception:
            pass
    print(f"✅ [BGP] Neighbor {neighbor} on {device} is shutdown")
    return True


@task(retries=2, log_prints=True, task_run_name="bgp_noshut[{device}:{neighbor}]")
def bgp_neighbor_no_shutdown(device: str, neighbor: str):
    """Re-enable the BGP neighbor (local side only)."""
    pause(5, "pre-restore pause for demo")
    asn = get_local_bgp_asn(device)
    print(f"🧹 [BGP] Enabling neighbor {neighbor} on {device} (ASN {asn})")
    with _netmiko_connect(device) as conn:
        conn.enable()
        conn.send_config_set(
            [
                f"router bgp {asn}",
                f"no neighbor {neighbor} shutdown",
                # clear quarantine tag
                f"no neighbor {neighbor} description",
            ]
        )
        try:
            conn.save_config()
        except Exception:
            pass
    print(f"✅ [BGP] Neighbor {neighbor} on {device} enabled")
    return True


# ---------- Observability helpers ----------


def _loki_push(labels: dict[str, str], message: str):
    """
    Push a single event to Loki using /loki/api/v1/push.
    'labels' become the Loki stream labels.
    """
    ts = str(time.time_ns())  # RFC3339 not required; Loki wants ns epoch
    payload = {
        "streams": [
            {
                "stream": labels,
                "values": [[ts, message]],
            }
        ]
    }
    r = requests.post(f"{LOKI_URL}/loki/api/v1/push", json=payload, timeout=5)
    if not r.ok:
        raise RuntimeError(f"Loki push failed: {r.status_code} {r.text}")


@task(log_prints=True, retries=0)
def annotate_to_loki(
    workflow: str,
    phase: str,
    device: str,
    interface: str,
    alertname: str,
    status: str,
    note: str = "",
):
    """
    Writes a single annotation event into Loki.
    Choose your own label set, but keep it stable & low-cardinality.
    """
    labels = {
        "source": "prefect",
        "workflow": workflow,  # quarantine | restore
        "phase": phase,  # start | end | skip | error
        "device": device,
        "interface": interface,
        "alertname": alertname,
        "status": status,
    }
    msg = f"{workflow.upper()} [{phase}] {device}/{interface} {alertname}:{status} {note}".strip()
    print(f"📝 [Loki] {msg}")
    _loki_push(labels, msg)


@task(retries=2, log_prints=True, task_run_name="expire_silence[{device}:{interface}]")
def expire_silences_for_link(device: str, interface: str) -> int:
    """
    Find ACTIVE silences in Alertmanager that match this link and delete them.
    Returns number of deleted silences.
    """
    print(f"🔕 [Silence] Searching active silences for {device}/{interface}")
    r = requests.get(f"{ALERTMANAGER_URL}/api/v2/silences", timeout=10)
    r.raise_for_status()
    silences = r.json()
    to_del = []
    for s in silences:
        if s.get("status", {}).get("state") != "active":
            continue
        matchers = {m["name"]: m["value"] for m in s.get("matchers", [])}
        if (
            matchers.get("alertname") == "PeerInterfaceFlapping"
            and matchers.get("device") == device
            and matchers.get("interface") == interface
        ):
            to_del.append(s.get("id"))

    count = 0
    for sid in to_del:
        try:
            dr = requests.delete(f"{ALERTMANAGER_URL}/api/v2/silence/{sid}", timeout=10)
            if dr.ok:
                count += 1
                print(f"✅ [Silence] Deleted silence {sid} for {device}/{interface}")
            else:
                print(
                    f"❌ [Silence] Failed to delete {sid}: {dr.status_code} {dr.text}"
                )
        except Exception as e:
            print(f"❌ [Silence] Exception deleting {sid}: {e}")
    print(f"🔕 [Silence] Deleted {count} silence(s) for {device}/{interface}")
    return count


@task(
    retries=2,
    log_prints=True,
    task_run_name="alert_active_in_am[{alertname}:{device}:{interface}]",
)
def alert_active_in_am(alertname: str, device: str, interface: str) -> bool:
    # /api/v2/alerts?filter=label=value
    print(
        f"📡 [AlertManager] Checking if {alertname} is active for {device}/{interface}"
    )
    params = [
        ("filter", f'alertname="{alertname}"'),
        ("filter", f'device="{device}"'),
        ("filter", f'interface="{interface}"'),
    ]
    r = requests.get(f"{ALERTMANAGER_URL}/api/v2/alerts", params=params, timeout=5)
    r.raise_for_status()
    active = any(a.get("status", {}).get("state") == "active" for a in r.json())
    print(
        f"✅ [AlertManager] {'Active' if active else 'Inactive'} for {device}/{interface}"
    )
    return active


@task(
    retries=0,
    log_prints=True,
    task_run_name="wait_until_inactive[{device}:{interface}]",
)
def wait_until_alert_inactive(
    alertname: str, device: str, interface: str, timeout_s: int = 180, poll_s: int = 5
) -> bool:
    """
    Poll Alertmanager until alert is NOT active (or timeout). Returns True if inactive.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        params = [
            ("filter", f'alertname="{alertname}"'),
            ("filter", f'device="{device}"'),
            ("filter", f'interface="{interface}"'),
        ]
        r = requests.get(f"{ALERTMANAGER_URL}/api/v2/alerts", params=params, timeout=5)
        r.raise_for_status()
        active = any(a.get("status", {}).get("state") == "active" for a in r.json())
        print(
            f"🧪 [AM] {alertname} active={active} for {device}/{interface} @ {datetime.datetime.utcnow().isoformat(timespec='seconds')}Z"
        )
        if not active:
            return True
        time.sleep(poll_s)
    print(f"⚠️ [AM] Still active after {timeout_s}s — continuing anyway")
    return False


@task(retries=0, log_prints=True, task_run_name="delete_silence[{silence_id}]")
def delete_silence_by_id(silence_id: str) -> bool:
    pause(2, "pre-delete silence pause for demo")

    r = requests.delete(f"{ALERTMANAGER_URL}/api/v2/silence/{silence_id}", timeout=10)
    if r.ok:
        print(f"✅ [Silence] Deleted {silence_id}")
        return True
    print(f"❌ [Silence] Delete failed for {silence_id}: {r.status_code} {r.text}")
    return False


@task(
    retries=2,
    log_prints=True,
    task_run_name="create_quarantine_silence[{device}:{interface}]",
)
def create_quarantine_silence(
    device: str, interface: str, duration_minutes: int = 20, author: str = "prefect"
):
    pause(2, "pre-silence pause for demo")
    print(
        f"🔕 [Silence] Creating Alertmanager silence for {device}/{interface} ({duration_minutes} min)"
    )
    starts = datetime.datetime.utcnow()
    ends = starts + datetime.timedelta(minutes=duration_minutes)
    body = {
        "matchers": [
            {"name": "alertname", "value": "PeerInterfaceFlapping", "isRegex": False},
            {"name": "device", "value": device, "isRegex": False},
            {"name": "interface", "value": interface, "isRegex": False},
        ],
        "startsAt": starts.isoformat(timespec="seconds") + "Z",
        "endsAt": ends.isoformat(timespec="seconds") + "Z",
        "createdBy": author,
        "comment": "Quarantined by Prefect; suppress repeats.",
    }
    r = requests.post(f"{ALERTMANAGER_URL}/api/v2/silences", json=body, timeout=5)
    if not r.ok:
        print(f"❌ [Silence] Failed to create silence: {r.text}")
        r.raise_for_status()

    sid = r.json().get("silenceID")
    print(
        f"✅ [Silence] Created AM silence {sid} for {device}/{interface} until {ends}Z"
    )
    return sid


@task(retries=1, log_prints=True, task_run_name="bgp_state[{device}:{neighbor}]")
def prom_bgp_established(device: str, neighbor: str) -> bool:
    """True if Prometheus says the session is ESTABLISHED (state == 1)."""
    pause(5, "waiting for Prometheus scrape")
    q = f'bgp_neighbor_state{{device="{device}", neighbor="{neighbor}"}}'
    r = requests.get(f"{PROM_URL}/api/v1/query", params={"query": q}, timeout=10)
    r.raise_for_status()
    res = r.json().get("data", {}).get("result", [])
    est = False
    for v in res:
        try:
            est = float(v.get("value", [0, "0"])[1]) == 1.0
        except Exception:
            est = False
    print(f"📈 [Prom] {device}↔{neighbor} established={est}")
    return est


@task(retries=1, log_prints=True, task_run_name="bgp_rx_cnt[{device}:{neighbor}]")
def prom_bgp_prefixes_received(device: str, neighbor: str) -> int:
    """Prefixes received now from this neighbor (instant vector)."""
    pause(5, "waiting for Prometheus scrape")
    q = f'bgp_prefixes_received{{device="{device}", neighbor="{neighbor}"}}'
    r = requests.get(f"{PROM_URL}/api/v1/query", params={"query": q}, timeout=10)
    r.raise_for_status()
    res = r.json().get("data", {}).get("result", [])
    val = 0
    for v in res:
        try:
            val = int(float(v.get("value", [0, "0"])[1]))
        except Exception:
            val = 0
    print(f"📦 [Prom] {device}←{neighbor} prefixes_received={val}")
    return val


# ---------- Action flows ----------


def _link_tag(device: str, interface: str) -> str:
    # normalize if you like (lowercase, replace slashes)
    return f"link:{device}:{interface}"


@flow(log_prints=True, flow_run_name="quarantine | {device}:{interface}")
def quarantine_link_flow(
    device: str,
    interface: str,
    local_interface_id: str | None = None,
    alertname: str = "PeerInterfaceFlapping",
    status: str = "firing",
):
    interface = canon_iface(interface)
    with tags(
        _link_tag(device, interface),
        f"alert:{alertname}",
        f"status:{status}",
        "action:quarantine",
    ):
        print(
            f"⚙️ [quarantine] Starting for {device}/{interface} ({alertname}:{status})"
        )
        annotate_to_loki(
            workflow="quarantine",
            phase="start",
            device=device,
            interface=interface,
            alertname=alertname,
            status=status,
            note="Starting quarantine workflow",
        )
        slack_ts = slack_post(
            "#bot-test",
            f":rotating_light: QUARANTINE start — `{device}/{interface}` ({alertname}:{status})",
        )

        # Freshness gate
        print("🔎 Verifying alert freshness in Alertmanager...")
        slack_post("#bot-test", "Confirm alert active in AM…", thread_ts=slack_ts)
        pause(3, "waiting for fresh state")
        if not alert_active_in_am("PeerInterfaceFlapping", device, interface):
            print("🧊 Alert no longer active → skip.")
            annotate_to_loki(
                workflow="quarantine",
                phase="skip",
                device=device,
                interface=interface,
                alertname=alertname,
                status=status,
                note="Alert no longer active; skipping quarantine",
            )
            slack_post(
                "#bot-test",
                f":white_check_mark: QUARANTINE skipped — `{device}/{interface}` no longer active",
                thread_ts=slack_ts,
            )
            return

        # 0) create Alertmanager silence
        # Silence just for this device/interface
        silence_id = create_quarantine_silence(
            device=device, interface=interface, duration_minutes=20
        )
        slack_post(
            "#bot-test",
            f"Created quarantine silence ID `{silence_id}` for `{device}/{interface}`",
            thread_ts=slack_ts,
        )
        print(f"🔕 Created quarantine silence: {silence_id}")

        # 2) map interface → neighbor
        nbr = get_neighbor_on_interface(device, interface)
        if not nbr:
            print("⚠️ Could not map interface to neighbor; skipping.")
            annotate_to_loki(
                workflow="quarantine",
                phase="error",
                device=device,
                interface=interface,
                alertname=alertname,
                status=status,
                note="Could not map interface to neighbor; skipping quarantine",
            )
            slack_post(
                "#bot-test",
                f":warning: QUARANTINE error — could not map `{device}/{interface}` to neighbor; skipping",
                thread_ts=slack_ts,
            )
            return

        # 3) BGP quarantine (LOCAL ONLY)
        bgp_neighbor_shutdown(device=device, neighbor=nbr)
        print(f"🚧 BGP neighbor {nbr} on {device} quarantined (local side).")
        slack_post(
            "#bot-test",
            f":rotating_light: QUARANTINE applied — BGP neighbor `{nbr}` on `{device}` shutdown",
            thread_ts=slack_ts,
        )

        # 4) (demo) verify in Prom: session not established and rx prefixes drop
        pause(2, "wait metrics scrape")
        est = prom_bgp_established(device=device, neighbor=nbr)
        rx = prom_bgp_prefixes_received(device=device, neighbor=nbr)
        print(f"✅ Post-quarantine checks: established={est}, prefixes_received={rx}")
        slack_post(
            "#bot-test",
            f"Post-quarantine checks for `{device}/{interface}`: established={est}, prefixes_received={rx}",
            thread_ts=slack_ts,
        )

        # 5) Let alert go inactive, then delete silence so 'resolved' can notify
        # Let the alert window drain, then drop silence so “resolved” can emit
        pause(2, "letting the counter drain / window elapse")
        inactive = wait_until_alert_inactive(
            alertname, device, interface, timeout_s=120, poll_s=5
        )
        if inactive and silence_id:
            delete_silence_by_id(silence_id)
            print(f"✅ Deleted quarantine silence {silence_id} after alert inactive.")
            slack_post(
                "#bot-test",
                f":white_check_mark: QUARANTINE complete — deleted silence ID `{silence_id}` after alert inactive",
                thread_ts=slack_ts,
            )
        else:
            print(
                f"⚠️ Alert still active after wait; leaving silence {silence_id} in place."
            )
            slack_post(
                "#bot-test",
                f":warning: QUARANTINE alert still active; leaving silence ID `{silence_id}` in place",
                thread_ts=slack_ts,
            )

        print("✅ Quarantine workflow completed.")
        annotate_to_loki(
            workflow="quarantine",
            phase="end",
            device=device,
            interface=interface,
            alertname=alertname,
            status=status,
            note="Quarantine workflow completed",
        )
        slack_post(
            "#bot-test",
            f":white_check_mark: QUARANTINE end — `{device}/{interface}` ({alertname}:{status}) workflow completed",
            thread_ts=slack_ts,
        )


@flow(log_prints=True, flow_run_name="restore | {device}:{interface}")
def restore_link_flow(
    device: str,
    interface: str,
    local_interface_id: str | None = None,
    alertname: str = "PeerInterfaceFlapping",
    status: str = "resolved",
):
    interface = canon_iface(interface)
    pause(1, "pre-restore pause for demo")

    with tags(
        _link_tag(device, interface),
        f"alert:{alertname}",
        f"status:{status}",
        "action:restore",
    ):
        print(f"🛠️ [restore] Starting for {device}/{interface} ({alertname}:{status})")
        annotate_to_loki(
            workflow="restore",
            phase="start",
            device=device,
            interface=interface,
            alertname=alertname,
            status=status,
            note="Starting restore workflow",
        )
        slack_ts = slack_post(
            "#bot-test",
            f":traffic_light: RESTORE start — `{device}/{interface}` ({alertname}:{status})",
        )

        # 2) map interface → neighbor
        nbr = get_neighbor_on_interface(device, interface)
        if not nbr:
            print("⚠️ Could not map interface to neighbor; skipping.")
            annotate_to_loki(
                workflow="restore",
                phase="error",
                device=device,
                interface=interface,
                alertname=alertname,
                status=status,
                note="Could not map interface to neighbor; skipping restore",
            )
            slack_post(
                "#bot-test",
                f":warning: RESTORE error — could not map `{device}/{interface}` to neighbor; skipping",
                thread_ts=slack_ts,
            )
            return

        # 3) BGP restore (LOCAL ONLY)
        # re-enable local neighbor
        bgp_neighbor_no_shutdown(device=device, neighbor=nbr)
        print(f"🧹 BGP neighbor {nbr} on {device} restored (local side).")
        slack_post(
            "#bot-test",
            f":traffic_light: RESTORE applied — BGP neighbor `{nbr}` on `{device}` enabled",
            thread_ts=slack_ts,
        )

        # 4) (demo) verify in Prom: session established and rx prefixes return
        pause(2, "wait metrics scrape")
        est = prom_bgp_established(device=device, neighbor=nbr)
        rx = prom_bgp_prefixes_received(device=device, neighbor=nbr)
        print(f"✅ Post-restore checks: established={est}, prefixes_received={rx}")
        slack_post(
            "#bot-test",
            f"Post-restore checks for `{device}/{interface}`: established={est}, prefixes_received={rx}",
            thread_ts=slack_ts,
        )

        # Best-effort: remove any leftover silences for this local endpoint
        deleted = expire_silences_for_link(device, interface)
        if deleted:
            print(f"✅ Silences expired for {device}/{interface}: {deleted}")
            slack_post(
                "#bot-test",
                f"Expired {deleted} leftover silence(s) for `{device}/{interface}`",
                thread_ts=slack_ts,
            )

        print("✅ Restore workflow completed.")
        annotate_to_loki(
            workflow="restore",
            phase="end",
            device=device,
            interface=interface,
            alertname=alertname,
            status=status,
            note="Restore workflow completed",
        )
        slack_post(
            "#bot-test",
            f":white_check_mark: RESTORE end — `{device}/{interface}` ({alertname}:{status}) workflow completed",
            thread_ts=slack_ts,
        )


@flow(
    log_prints=True,
    # flow_run_name="alert | {alertname}:{status} | {device}:{interface}",
)
def alert_receiver(alert_group: dict):
    """Process the alert."""

    # Status of the alert group
    status = alert_group["status"]

    # Name of the alert group
    alertname = alert_group["groupLabels"]["alertname"]

    # Alerts in the alert group
    alerts = alert_group["alerts"]

    print(f"Received alert group: {alertname} - {status}")
    print(f"Number of alerts in group: {len(alerts)}")

    # NOTE: Add your alert workflow logic here
    # Check the subject of the alert and forward to respective workflow
    if alertname == "PeerInterfaceFlapping":
        for a in alerts:
            # labels come from your Loki rule
            device = a["labels"]["device"]
            interface = canon_iface(a["labels"]["interface"])

            if status == "firing":
                quarantine_link_flow(
                    device=device,
                    interface=interface,
                    alertname=alertname,
                    status=status,
                )
                generate_rca(device=device, interface=interface)
            else:
                # status == "resolved" (or anything not "firing")
                restore_link_flow(
                    device=device,
                    interface=interface,
                    alertname=alertname,
                    status=status,
                )

    print("Alertmanager Alert Group status processed, exiting")


if __name__ == "__main__":
    _ = alert_receiver.serve(name="alert-receiver")
    # alert_receiver.deploy(
    #     name="alert-receiver-deployment",
    #     work_pool_name="netobs-work-pool",
    #     image="my-registry.com/my-docker-image:my-tag",
    #     push=False # switch to True to push to your image registry
    # )
