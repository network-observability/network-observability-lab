import json
import re
import requests
import socket
from prefect import flow, task, tags, get_run_logger
from prefect.artifacts import create_markdown_artifact
from prefect.blocks.system import Secret
from netmiko import ConnectHandler

NAUTOBOT_URL = "http://localhost:8080"
PROM_URL = "http://localhost:9090"
ALERTMANAGER_URL = "http://localhost:9093"
LOKI_URL = "http://localhost:3001"


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


# ---------- SoT helpers ----------


@task(
    retries=3,
    log_prints=True,
    task_run_name="nautobot_status[{interface_id}->{status}]",
)
def update_interface_status(interface_id: str, status: str, reason: str | None = None):
    print(
        f"🧩 [Nautobot] → Updating interface {interface_id} to '{status}' ({reason or 'no reason'})"
    )
    token = Secret.load("nautobot-token").get()  # type: ignore
    body = {"status": status}
    # if reason:
    #     body["custom_fields"] = {"quarantine_reason": reason}
    r = requests.patch(
        f"{NAUTOBOT_URL}/api/dcim/interfaces/{interface_id}/",
        headers={"Authorization": f"Token {token}"},
        json=body,
        timeout=10,
    )
    if not r.ok:
        print(f"❌ [Nautobot] PATCH failed ({r.status_code}): {r.text}")
        r.raise_for_status()

    print(f"✅ [Nautobot] Interface {interface_id} successfully set to '{status}'")


@task(retries=3, log_prints=True, task_run_name="resolve_host[{device}]")
def resolve_device_host(device: str) -> str:
    """
    Prefer Nautobot primary_ip4; fallback to DNS on the device name.
    Returns a connectable host string for Netmiko.
    """
    print(f"🧠 [Resolver] Starting host resolution for {device}")
    token = Secret.load("nautobot-token").get()  # type: ignore

    # Try Nautobot REST: /api/dcim/devices/?name=<device>&include=primary_ip4
    # (works on Nautobot 2.x; primary_ip4 -> {"address": "A.B.C.D/len"})
    r = requests.get(
        f"{NAUTOBOT_URL}/api/dcim/devices/",
        params={"name": device},
        headers={"Authorization": f"Token {token}"},
        timeout=10,
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    if results:
        dev = results[0]
        # If your API isn’t embedding primary_ip4 by default, you can do a second GET to dev["primary_ip4"]["url"]
        pip4 = dev.get("primary_ip4")
        if isinstance(pip4, dict):
            addr = pip4.get("address")
            if addr:
                # strip CIDR if present (e.g. "192.0.2.11/32" -> "192.0.2.11")
                host = addr.split("/")[0]
                print(f"✅ [Resolver] Found Nautobot primary_ip4 for {device}: {host}")
                return host

    # Fallback to DNS on the device name
    try:
        socket.getaddrinfo(device, 22)
        print(f"✅ [Resolver] Using DNS fallback for {device}: {device}")
        return device
    except OSError:
        msg = f"❌ [Resolver] Could not resolve host for {device} via Nautobot or DNS"
        print(msg)
        raise RuntimeError(msg)


# ---------- Netmiko helpers (vendor-neutral commands) ----------


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


def _aliases_for_iface(ifname: str) -> list[str]:
    """
    Return likely short/long aliases for common platforms.
    Examples:
      Ethernet1 -> [Ethernet1, Et1]
      GigabitEthernet1/0/1 -> [GigabitEthernet1/0/1, Gi1/0/1]
      TenGigabitEthernet1/1 -> [TenGigabitEthernet1/1, Te1/1]
      Management0 -> [Management0, Ma0]
    """
    al = {ifname}
    m = (
        ("Ethernet", "Et"),
        ("GigabitEthernet", "Gi"),
        ("TenGigabitEthernet", "Te"),
        ("FortyGigabitEthernet", "Fo"),
        ("HundredGigE", "Hu"),
        ("Management", "Ma"),
        ("Vlan", "Vlan"),
        ("Port-Channel", "Po"),
        ("Loopback", "Lo"),
    )
    for long, short in m:
        if ifname.startswith(long):
            tail = ifname[len(long) :]
            al.add(f"{short}{tail}")
    return list(al)


@task(retries=2, log_prints=True, task_run_name="is_quarantined[{device}:{interface}]")
def is_already_quarantined(device: str, interface: str) -> bool:
    """
    Returns True if the interface looks quarantined: admin down and/or our tag in description.
    Works for EOS/IOS-XE style outputs.
    """
    print(f"🧰 [Check] Checking quarantine state for {device}/{interface}")
    with _netmiko_connect(device) as conn:
        conn.enable()

        # Try "show running-config interface" first (most reliable)
        cfg = conn.send_command(
            f"show running-config interface {interface}", use_textfsm=False
        )
        if "shutdown" in cfg.lower() and "quarantined_by_prefect".lower() in cfg.lower():  # type: ignore
            print(f"🔒 [Check] {device}/{interface} already quarantined (config match)")
            return True

        # Fallback: parse "show interface <X>" for admin state + description
        out = conn.send_command(f"show interface {interface}", use_textfsm=False)
        text = out.lower()  # type: ignore
        if (
            "admin state is down" in text
            or "administratively down" in text
            or "is administratively down" in text
        ) and "quarantined_by_prefect" in text:
            print(
                f"🔒 [Check] {device}/{interface} already quarantined (show interface)"
            )
            return True

    print(f"✅ [Check] {device}/{interface} not quarantined")
    return False


@task(retries=0, log_prints=True, task_run_name="lldp_peer[{device}:{interface}]")
def lldp_peer(device: str, interface: str, wait_s: int = 10) -> tuple[str, str] | None:
    """
    Returns (peer_device, peer_interface) for `device/interface`.
    Tries JSON first, then table, retrying for up to `wait_s` seconds.
    """
    print(f"🛰️ [LLDP] Discovering peer for {device}/{interface}")
    aliases = _aliases_for_iface(interface)  # keep your alias helper

    def _json_attempt(conn) -> tuple[str, str] | None:
        out = conn.send_command("show lldp neighbors | json", use_textfsm=False)
        try:
            data = json.loads(out)
        except Exception:
            return None
        items = (
            data.get("lldpNeighbors")
            or data.get("neighbors")
            or data.get("lldpNeighborsBriefTable")
            or []
        )
        for it in items:
            local = (
                it.get("port")
                or it.get("interface")
                or it.get("localPort")
                or it.get("localInterface")
            )
            ndev = (
                it.get("neighborDevice")
                or it.get("neighborDeviceId")
                or it.get("systemName")
            )
            nport = (
                it.get("neighborPort")
                or it.get("neighborInterface")
                or it.get("portId")
            )
            if local and ndev and nport and local in aliases:
                print(f"✅ [LLDP-JSON] {device}/{local} ↔ {ndev}/{nport}")
                return ndev, nport
        return None

    def _table_attempt(conn) -> tuple[str, str] | None:
        out = conn.send_command("show lldp neighbors", use_textfsm=False)
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        row_re = re.compile(r"^(\S+)\s+(\S+)\s+(\S+)\s+\d+$")

        def parse_fallback(line: str):
            parts = re.split(r"\s{2,}", line)
            if len(parts) >= 4 and parts[-1].isdigit():
                return parts[0], parts[1], parts[2]
            return None

        rows = []
        for ln in lines:
            m = row_re.match(ln)
            if m:
                rows.append((m.group(1), m.group(2), m.group(3)))
                continue
            fb = parse_fallback(ln)
            if fb:
                rows.append(fb)
        for local, ndev, nport in rows:
            if local in aliases:
                print(f"✅ [LLDP-TBL] {device}/{local} ↔ {ndev}/{nport}")
                return ndev, nport
        return None

    with _netmiko_connect(device) as conn:  # your Netmiko connector
        import time

        conn.enable()
        try:
            conn.send_command("terminal length 0")
        except Exception:
            pass

        deadline = time.time() + max(0, wait_s)
        attempt = 1
        while True:
            res = _json_attempt(conn) or _table_attempt(conn)
            if res:
                return res
            if time.time() >= deadline:
                print(
                    f"⚠️ [LLDP] No neighbor for {device}/{interface} after {attempt - 1} tries."
                )
                return None
            print(f"🕐 [LLDP] No result (attempt {attempt}) — retrying...")
            attempt += 1
            time.sleep(2)


@task(retries=2, log_prints=True, task_run_name="quarantine_side[{device}:{interface}]")
def quarantine_side(device: str, interface: str):
    print(f"🚨 [Netmiko] Quarantining {device}/{interface}")
    with _netmiko_connect(device) as conn:
        conn.enable()
        conn.send_config_set(
            [
                f"interface {interface}",
                "shutdown",
                "description QUARANTINED_BY_PREFECT",
            ]
        )
        try:
            conn.save_config()
        except Exception:
            pass
    print(f"✅ [Netmiko] Interface {device}/{interface} quarantined successfully")
    return True


@task(retries=2, log_prints=True, task_run_name="restore_side[{device}:{interface}]")
def restore_side(device: str, iface: str):
    print(f"🧹 [Netmiko] Restoring {device}/{iface}")
    with _netmiko_connect(device) as conn:
        conn.enable()
        conn.send_config_set(
            [
                f"interface {iface}",
                "no shutdown",
                "description Restored_by_Prefect",
            ]
        )
        try:
            conn.save_config()
        except Exception:
            pass
    print(f"✅ [Netmiko] Interface {device}/{iface} restored successfully")
    return True


# ---------- Observability helpers ----------


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


@task(retries=2, log_prints=True)
def condition_true_in_loki(device: str, interface: str, threshold: int = 3) -> bool:
    # Re-evaluate the alert’s expression at 'now'
    logql = (
        f"sum by(device, interface) ("
        f'count_over_time({{vendor_facility_process="UPDOWN", device="{device}", interface="{interface}"}}[2m])'
        f") > {threshold}"
    )
    r = requests.get(
        f"{LOKI_URL}/loki/api/v1/query", params={"query": logql}, timeout=5
    )
    r.raise_for_status()
    data = r.json().get("data", {}).get("result", [])
    return len(data) > 0


@task(
    retries=2,
    log_prints=True,
    task_run_name="create_quarantine_silence[{device}:{interface}]",
)
def create_quarantine_silence(
    device: str, interface: str, duration_minutes: int = 20, author: str = "prefect"
):
    print(
        f"🔕 [Silence] Creating Alertmanager silence for {device}/{interface} ({duration_minutes} min)"
    )
    import datetime as dt

    starts = dt.datetime.utcnow()
    ends = starts + dt.timedelta(minutes=duration_minutes)
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
    """
    For 'firing': shuts both ends and marks SoT 'quarantined'.
    """
    from datetime import datetime

    with tags(
        _link_tag(device, interface),
        f"alert:{alertname}",
        f"status:{status}",
        "action:quarantine",
    ):
        start_ts = datetime.utcnow().isoformat(timespec="seconds")
        print(
            f"⚙️ [quarantine] Starting for {device}/{interface} ({alertname}:{status})"
        )
        # Fast idempotency guard
        if is_already_quarantined(device, interface):
            # Optional: ensure SoT reflects the state
            if local_interface_id:
                update_interface_status(
                    local_interface_id, "quarantined", reason="flapping"
                )
            print("⏭️ Already quarantined → no-op.")

            create_markdown_artifact(
                key=artifact_key("quarantine-skip", device, interface),
                markdown=f"""
                ### ⚙️ Quarantine Skipped
                - **Device:** `{device}`
                - **Interface:** `{interface}`
                - **Reason:** Already quarantined
                - **Alert:** `{alertname}` (`{status}`)
                - **Timestamp:** {start_ts} UTC
                """,
                description=f"Skipped quarantine for {device}/{interface} (already quarantined)",
            )
            return

        # Freshness gate — pick ONE (Alertmanager or Loki)
        if not alert_active_in_am("PeerInterfaceFlapping", device, interface):
            print("🧊 Alert no longer active → skipping quarantine.")
            create_markdown_artifact(
                key=artifact_key("quarantine-stale", device, interface),
                markdown=f"""
                ### 🧊 Quarantine Skipped (Stale Alert)
                - **Device:** `{device}`
                - **Interface:** `{interface}`
                - **Alert:** `{alertname}` (`{status}`)
                - **Reason:** Alert no longer active in Alertmanager
                - **Timestamp:** {start_ts} UTC
                """,
                description=f"Stale alert for {device}/{interface}",
            )
            return
        # OR:
        # if not condition_true_in_loki(device, interface, threshold=3):
        #     print("Condition no longer true in Loki → skipping.")
        #     return

        # Only try LLDP when the local link is up (otherwise it will be empty)
        peer = lldp_peer(device, interface, wait_s=10)
        if not peer:
            print(
                "⚠️ No LLDP neighbor (link likely down) → skip to avoid stale actions."
            )
            create_markdown_artifact(
                key=artifact_key("quarantine-nollpd", device, interface),
                markdown=f"""
                ### ⚠️ Quarantine Aborted (No LLDP)
                - **Device:** `{device}`
                - **Interface:** `{interface}`
                - **Alert:** `{alertname}` (`{status}`)
                - **Reason:** No LLDP neighbor detected — interface likely down
                - **Timestamp:** {start_ts} UTC
                """,
                description=f"No LLDP neighbor for {device}/{interface}",
            )
            return

        peer_device, peer_interface = peer
        print(f"🔗 LLDP discovered peer {peer_device}/{peer_interface}")

        # Quarantine both ends
        quarantine_side(device, interface)
        quarantine_side(peer_device, peer_interface)

        # SoT
        if local_interface_id:
            update_interface_status(
                local_interface_id, "quarantined", reason="flapping"
            )

        silence_id = create_quarantine_silence(device, interface, duration_minutes=20)
        print("✅ Quarantined and silenced.")

        # ✅ Final summary artifact
        create_markdown_artifact(
            key=artifact_key("quarantine", device, interface),
            markdown=f"""
            ## 🚨 Quarantine Summary

            - **Device:** `{device}`
            - **Interface:** `{interface}`
            - **Peer Device:** `{peer_device}`
            - **Peer Interface:** `{peer_interface}`
            - **Alert:** `{alertname}` (`{status}`)
            - **Silence ID:** `{silence_id}`
            - **Status in SoT:** `quarantined`
            - **Timestamp:** {datetime.utcnow().isoformat(timespec="seconds")} UTC
            """,
            description=f"Quarantine summary for {device}/{interface}",
        )


@flow(log_prints=True, flow_run_name="restore | {device}:{interface}")
def restore_link_flow(
    device: str,
    interface: str,
    local_interface_id: str | None = None,
    alertname: str = "PeerInterfaceFlapping",
    status: str = "resolved",
):
    """
    For 'resolved': restores both ends and sets SoT 'active'.
    """
    from datetime import datetime

    with tags(
        _link_tag(device, interface),
        f"alert:{alertname}",
        f"status:{status}",
        "action:restore",
    ):
        start_ts = datetime.utcnow().isoformat(timespec="seconds")
        print(f"🛠️ [restore] Starting for {device}/{interface} ({alertname}:{status})")

        if not is_already_quarantined(device, interface):
            print(f"⏭️ {device}/{interface} not quarantined by us → skipping restore.")
            create_markdown_artifact(
                key=artifact_key("restore-skip", device, interface),
                markdown=f"""
                ### 🧩 Restore Skipped
                - **Device:** `{device}`
                - **Interface:** `{interface}`
                - **Reason:** Not quarantined
                - **Alert:** `{alertname}` (`{status}`)
                - **Timestamp:** {start_ts} UTC
                """,
                description=f"Skipped restore for {device}/{interface} (not quarantined)",
            )
            return

        # Bring both ends back
        restore_side(device, interface)

        # SoT
        if local_interface_id:
            update_interface_status(local_interface_id, "active")

        print("✅ Link restored.")

        create_markdown_artifact(
            key=artifact_key("restore", device, interface),
            markdown=f"""
            ## 🔄 Restore Summary

            - **Device:** `{device}`
            - **Interface:** `{interface}`
            - **Action:** Restored link
            - **Alert:** `{alertname}` (`{status}`)
            - **Status in SoT:** `active`
            - **Timestamp:** {datetime.utcnow().isoformat(timespec="seconds")} UTC
            """,
            description=f"Restore summary for {device}/{interface}",
        )


# ---------- Alert Receiver Flow ----------


@task(retries=3, log_prints=True)
def get_nautobot_intf_id(device: str, interface: str) -> str | None:
    """Retrieve the Nautobot Interface ID."""

    # GraphQL query to retrieve the device interfaces information
    gql = """
    query($device: [String]) {
        devices(name: $device) {
            name
            interfaces {
                name
                id
            }
        }
    }
    """

    # Retrieve the Nautobot API token from Prefect Block Secret
    secret_block = Secret.load("nautobot-token")
    nautobot_token = secret_block.get()  # type: ignore

    # Get the device information from Nautobot using GraphQL
    response = requests.post(
        url="http://localhost:8080/api/graphql/",
        headers={"Authorization": f"Token {nautobot_token}"},
        json={"query": gql, "variables": {"device": device}},
    )
    response.raise_for_status()

    # Parse the response and return the interface ID
    result = response.json()["data"]["devices"][0]
    for intf in result["interfaces"]:
        if intf["name"] == interface:
            return intf["id"]


@task(retries=3, log_prints=True)
def update_nautobot_intf_state(interface_id: str, status: str) -> bool:
    """Update the device interface status."""

    # Retrieve the Nautobot API token from Prefect Block Secret
    secret_block = Secret.load("nautobot-token")
    nautobot_token = secret_block.get()  # type: ignore

    # Mapping Alertmanager status to Nautobot status
    status = "lab-active" if status == "resolved" else "Alerted"

    # Update the interface status
    result = requests.patch(
        url=f"http://localhost:8080/api/dcim/interfaces/{interface_id}/",
        headers={"Authorization": f"Token {nautobot_token}"},
        json={"status": status},
    )
    result.raise_for_status()

    # Print the result to console
    print(f"Interface ID {interface_id} status updated to {status}")

    return True


@flow(log_prints=True)
def interface_flapping_processor(device: str, interface: str, status: str) -> bool:
    """Interface Flapping Event Processor."""

    # Retrieve Nautobot Interface ID
    intf_id = get_nautobot_intf_id(device=device, interface=interface)
    if intf_id is None:
        raise ValueError("Interface not found in Nautobot")

    # Print the interface ID
    print(f"Interface: {interface} == ID: {intf_id}")

    # Update the device interface status in Nautobot
    is_good = update_nautobot_intf_state(interface_id=intf_id, status=status)
    return is_good


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
            interface = a["labels"]["interface"]

            if status == "firing":
                quarantine_link_flow(
                    device=device,
                    interface=interface,
                    alertname=alertname,
                    status=status,
                )
            else:
                # status == "resolved" (or anything not "firing")
                restore_link_flow(
                    device=device,
                    interface=interface,
                    alertname=alertname,
                    status=status,
                )
        # for alert in alerts:

        #     # Run the interface flapping processor
        #     result = interface_flapping_processor(
        #         device=alert["labels"]["device"],
        #         interface=alert["labels"]["interface"],
        #         status=alert_group["status"],
        #     )

        #     # Print the result to console
        #     print(f"Interface Flapping Processor Result: {result}")

    print("Alertmanager Alert Group status processed, exiting")


if __name__ == "__main__":
    _ = alert_receiver.serve(name="alert-receiver")
    # alert_receiver.deploy(
    #     name="alert-receiver-deployment",
    #     work_pool_name="netobs-work-pool",
    #     image="my-registry.com/my-docker-image:my-tag",
    #     push=False # switch to True to push to your image registry
    # )
