import time
import json
import datetime as dt
import requests

from prefect import flow, task
from prefect.blocks.system import Secret

NAUTOBOT_URL = "http://localhost:8080"
PROM_URL = "http://localhost:9090"
ALERTMANAGER_URL = "http://localhost:9093"
LOKI_URL = "http://localhost:3001"
ENABLE_LLM_RCA = True


# ------------------------
# Utilities
# ------------------------

def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)

def to_rfc3339(ts: dt.datetime) -> str:
    return ts.isoformat(timespec="seconds").replace("+00:00", "Z")


# ------------------------
# Evidence collectors
# ------------------------

@task(log_prints=True, retries=2)
def prom_instant(query: str) -> list[dict]:
    """Run a Prom instant query and return result vector."""
    r = requests.get(f"{PROM_URL}/api/v1/query", params={"query": query}, timeout=10)
    r.raise_for_status()
    return r.json()["data"]["result"]

def _first_value(result: list[dict], default=0.0) -> float:
    if not result:
        return float(default)
    # Prom result: [{"value":[ts, "123"] ...}]
    try:
        return float(result[0]["value"][1])
    except Exception:
        return float(default)

@task(log_prints=True, retries=2)
def loki_query_range(query: str, minutes: int = 10, limit: int = 200) -> list[str]:
    """
    Query Loki and return a list of rendered log lines (strings).
    Keeps it simple for workshop: return last N lines as text.
    """
    end = now_utc()
    start = end - dt.timedelta(minutes=minutes)

    params = {
        "query": query,
        "start": int(start.timestamp() * 1e9),  # Loki expects ns
        "end": int(end.timestamp() * 1e9),
        "limit": limit,
        "direction": "BACKWARD",
    }
    r = requests.get(f"{LOKI_URL}/loki/api/v1/query_range", params=params, timeout=10)
    r.raise_for_status()

    # Loki response: streams -> values [[ts, line], ...]
    lines: list[str] = []
    for stream in r.json().get("data", {}).get("result", []):
        for _, line in stream.get("values", []):
            lines.append(line)

    return lines[:limit]

# ------------------------
# SoT Context Enricher
# ------------------------
def is_device_in_maintenance(device_obj: dict) -> bool:
    return bool((device_obj.get("custom_fields") or {}).get("maintenance", False))


def get_intended_bgp_peers(device_obj: dict, afi_safi: str) -> list[str]:
    ctx = device_obj.get("config_context") or {}
    intent = (ctx.get("observability_intent") or {}).get("bgp") or {}
    peers = (
        ((intent.get("intended_peers") or {}).get(device_obj["name"]) or {})
        .get(afi_safi)
        or []
    )
    return peers


@task(log_prints=True, retries=2)
def nautobot_get_device(device: str) -> dict | None:
    token = Secret.load("nautobot-token").get()  # type: ignore
    headers = {"Authorization": f"Token {token}", "Accept": "application/json"}
    r = requests.get(f"{NAUTOBOT_URL}/api/dcim/devices/", headers=headers, params={"name": device}, timeout=10)
    r.raise_for_status()
    results = r.json().get("results", [])
    return results[0] if results else None


@task(log_prints=True, retries=2)
def get_device_intent(device: str, peer_address: str, afi_safi: str,) -> dict:
    dev = nautobot_get_device(device)
    if not dev:
        return {"found": False, "reason": "device not found in Nautobot"}

    intended_peers = get_intended_bgp_peers(dev, afi_safi)
    maintenance = is_device_in_maintenance(dev)

    return {
        "maintenance": maintenance,
        "intended_peer": peer_address in intended_peers,
        "intended_peers": intended_peers,
        "device": dev["name"],
        "site": (dev.get("site") or {}).get("name"),
        "role": (dev.get("device_role") or {}).get("name"),
    }

# ------------------------
# Actions (Quarantine = silence + annotation)
# ------------------------

@task(log_prints=True, retries=2)
def create_am_silence(device: str, peer_address: str, minutes: int = 20) -> str:
    starts = now_utc()
    ends = starts + dt.timedelta(minutes=minutes)

    body = {
        "matchers": [
            {"name": "alertname", "value": "BgpSessionNotUp", "isRegex": False},
            {"name": "device", "value": device, "isRegex": False},
            {"name": "peer_address", "value": peer_address, "isRegex": False},
        ],
        "startsAt": to_rfc3339(starts),
        "endsAt": to_rfc3339(ends),
        "createdBy": "prefect-workshop",
        "comment": "Workshop quarantine: suppress repeat notifications while investigating.",
    }
    r = requests.post(f"{ALERTMANAGER_URL}/api/v2/silences", json=body, timeout=10)
    r.raise_for_status()
    return r.json().get("silenceID", "")

@task(log_prints=True, retries=2)
def loki_push_annotation(labels: dict[str, str], message: str) -> None:
    ts = str(time.time_ns())
    payload = {"streams": [{"stream": labels, "values": [[ts, message]]}]}
    r = requests.post(f"{LOKI_URL}/loki/api/v1/push", json=payload, timeout=10)
    r.raise_for_status()


# ------------------------
# LLM RCA
# ------------------------

@task(log_prints=True, retries=0)
def llm_rca(device: str, peer_address: str, evidence: dict) -> str:
    """
    Workshop-friendly RCA prompt. Keep it short and directive.
    Uses OpenAI-compatible client if we have it in the environment.
    """
    from openai import OpenAI

    token = Secret.load("openai-token").get()  # type: ignore
    client = OpenAI(api_key=token)

    prompt = f"""
we are a network ops assistant.
We detected a BGP session issue.

ALERT:
- device: {device}
- peer: {peer_address}

EVIDENCE (Prom metrics snapshot):
{json.dumps(evidence.get("metrics", {}), indent=2)}

EVIDENCE (Relevant log lines):
{json.dumps(evidence.get("logs", [])[:40], indent=2)}

TASK:
Write a short RCA for a workshop demo.
- Max 1200 characters
- Use headings:
  * Most likely cause
  * Immediate actions
  * What to verify next
- Be specific: mention device + peer IP.
- If evidence is insufficient, say what is missing.
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content or ""


# ------------------------
# Main flow
# ------------------------

@flow(log_prints=True)
def quarantine_bgp_peer_flow(device: str, peer_address: str, afi_safi: str = "evpn", instance_name: str = "default"):
    """
    This is the “guided tour” flow:
    - collect evidence
    - quarantine (silence + annotation)
    - generate RCA
    """
    print(f"🚨 Starting quarantine flow for device={device} peer={peer_address} afi_safi={afi_safi} name={instance_name}")

    # 0) SoT intent gate - enrich and decide
    gate = get_device_intent(device=device, peer_address=peer_address, afi_safi=afi_safi)
    print(f"🧭 SoT gate: {gate}")

    # Decide
    if gate.get("maintenance"):
        loki_push_annotation(
            labels={"source": "prefect", "workflow": "quarantine_bgp", "device": device, "peer_address": peer_address, "decision": "skip"},
            message=f"SKIP quarantine: device under maintenance in SoT (device={device})",
        )
        print("🟡 Skipping quarantine: maintenance")
        return

    if not gate.get("intended"):
        loki_push_annotation(
            labels={"source": "prefect", "workflow": "quarantine_bgp", "device": device, "peer_address": peer_address, "decision": "skip"},
            message=f"SKIP quarantine: peer not intended in SoT (device={device}, peer={peer_address})",
        )
        print("🟡 Skipping quarantine: not intended")
        # Still generate RCA if we want, but framed as “configuration drift / SoT mismatch”
        # return if we want to keep it simple:
        return

    # 1) Evidence from Prom
    q_admin = f'bgp_admin_state{{device="{device}",peer_address="{peer_address}",afi_safi_name="{afi_safi}",name="{instance_name}"}}'
    q_oper  = f'bgp_oper_state{{device="{device}",peer_address="{peer_address}",afi_safi_name="{afi_safi}",name="{instance_name}"}}'
    q_rx    = f'bgp_received_routes{{device="{device}",peer_address="{peer_address}",afi_safi_name="{afi_safi}",name="{instance_name}"}}'
    q_act   = f'bgp_active_routes{{device="{device}",peer_address="{peer_address}",afi_safi_name="{afi_safi}",name="{instance_name}"}}'

    admin_res = prom_instant(q_admin)
    oper_res  = prom_instant(q_oper)
    rx_res    = prom_instant(q_rx)
    act_res   = prom_instant(q_act)

    metrics = {
        "admin_state": _first_value(admin_res, default=-1),
        "oper_state": _first_value(oper_res, default=-1),
        "received_routes": _first_value(rx_res, default=0),
        "active_routes": _first_value(act_res, default=0),
    }
    print(f"📌 Metrics snapshot: {metrics}")

    # 2) Evidence from Loki (filter noise, keep it human)
    # Adjust filters to SRL logs shape; this is a good starter:
    logql = (
        f'{{device="{device}"}} != "license" '
        f'|~ "(bgp|BGP|neighbor|session|route|evpn|{peer_address})"'
    )
    logs = loki_query_range(logql, minutes=10, limit=200)
    print(f"📜 Collected {len(logs)} log lines")

    evidence = {"metrics": metrics, "logs": logs, "sot": gate}

    # 3) Quarantine action (workshop version)
    silence_id = create_am_silence(device=device, peer_address=peer_address, minutes=20)
    print(f"🔕 Created silence: {silence_id}")

    loki_push_annotation(
        labels={
            "source": "prefect",
            "workflow": "quarantine_bgp",
            "device": device,
            "peer_address": peer_address,
            "afi_safi": afi_safi,
        },
        message=f"QUARANTINE applied: silenced BgpSessionNotUp for {device} peer={peer_address} (silence_id={silence_id})",
    )

    # 4) RCA
    if ENABLE_LLM_RCA:
        rca = llm_rca(device=device, peer_address=peer_address, evidence=evidence)
        print("\n===== RCA (LLM) =====\n")
        print(rca)
        print("\n=====================\n")

        loki_push_annotation(
            labels={
                "source": "prefect",
                "workflow": "quarantine_bgp",
                "device": device,
                "peer_address": peer_address,
                "type": "rca",
            },
            message=f"RCA: {rca}",
        )

    print("✅ Flow complete")


@flow(log_prints=True)
def alert_receiver(alert_group: dict):
    """
    Alertmanager webhook entrypoint.
    This keeps the parsing simple and workshop-friendly.
    """
    status = alert_group.get("status")
    alerts = alert_group.get("alerts", [])
    group_labels = alert_group.get("groupLabels", {})
    alertname = group_labels.get("alertname", "")

    print(f"📥 Received alert group alertname={alertname} status={status} alerts={len(alerts)}")

    if alertname != "BgpSessionNotUp":
        print("Skipping: not our workshop alert")
        return

    # In a workshop, handle just the first alert for clarity.
    a = alerts[0]
    labels = a.get("labels", {})

    device = labels.get("device")
    peer_address = labels.get("peer_address")
    afi_safi = labels.get("afi_safi_name", "evpn")
    name = labels.get("name", "default")

    if not device or not peer_address:
        print("Missing required labels device/peer_address; cannot continue.")
        return

    if status == "firing":
        quarantine_bgp_peer_flow(device=device, peer_address=peer_address, afi_safi=afi_safi, instance_name=name)
    else:
        # For the workshop, we can just annotate "resolved" instead of doing a restore.
        loki_push_annotation(
            labels={"source": "prefect", "workflow": "quarantine_bgp", "device": device, "peer_address": peer_address, "status": status or "unknown"},
            message=f"Alert resolved: {alertname} device={device} peer={peer_address}",
        )
        print("✅ Resolved annotation posted")


if __name__ == "__main__":
    _ = alert_receiver.serve(name="bgp-alert-receiver")
