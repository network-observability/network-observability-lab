# netobs_workshop_sdk.py
"""
Workshop SDK for Modern Network Observability (Prefect flows)

Goals:
- Hide HTTP/JSON plumbing behind small, readable helpers
- Keep functions simple + deterministic for a workshop
- Avoid Prefect anti-patterns: no task-within-task in the SDK

Usage:
    from netobs_workshop_sdk import (
        PromClient, LokiClient, AlertmanagerClient, NautobotClient,
        now_utc, to_rfc3339
    )
"""

from __future__ import annotations

import time
import json
import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

try:
    # Prefect is only needed for Secrets; SDK still works without it
    from prefect.blocks.system import Secret
except Exception:  # pragma: no cover
    Secret = None  # type: ignore


# ------------------------
# Utilities
# ------------------------


ADMIN_MAP = {1: "enable", 2: "disable"}
OPER_MAP = {1: "up", 2: "down", 3: "idle", 4: "connect", 5: "active"}


def decode_bgp_states(metrics: dict[str, float]) -> dict[str, str]:
    def _as_int(v: float | int | None) -> int | None:
        if v is None:
            return None
        try:
            return int(v)
        except Exception:
            return None

    admin_i = _as_int(metrics.get("admin_state"))
    oper_i = _as_int(metrics.get("oper_state"))

    decoded: dict[str, str] = {}
    if admin_i is not None:
        decoded["admin_state"] = ADMIN_MAP.get(admin_i, str(admin_i))
    if oper_i is not None:
        decoded["oper_state"] = OPER_MAP.get(oper_i, str(oper_i))
    return decoded


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def to_rfc3339(ts: dt.datetime) -> str:
    return ts.isoformat(timespec="seconds").replace("+00:00", "Z")


def first_prom_value(result: list[dict], default: float = 0.0) -> float:
    """
    Prom instant query result format:
      [{"metric": {...}, "value": [<ts>, "<string-number>"]}, ...]
    """
    if not result:
        return float(default)
    try:
        return float(result[0]["value"][1])
    except Exception:
        return float(default)


def _load_secret(name: str) -> str:
    """
    Load a Prefect Secret block by name.
    Raises a helpful error if Prefect isn't available.
    """
    if Secret is None:
        raise RuntimeError(
            f"Prefect Secret blocks not available. Install/enable Prefect or pass tokens explicitly. Missing: {name}"
        )
    print(f"🔐 Loading Prefect Secret block: {name}")
    return Secret.load(name).get()  # type: ignore


def _decode_admin_state(v: float) -> str:
    # telegraf enum mapping:
    # enable=1, disable=2
    if v == 1:
        return "enable"
    if v == 2:
        return "disable"
    if v == -1:
        return "unknown"
    return f"unknown({v})"


def _decode_oper_state(v: float) -> str:
    # telegraf enum mapping:
    # up=1, down=2, idle=3, connect=4, active=5
    try:
        key = int(v)
    except (ValueError, OverflowError):
        return f"unknown({v})"

    return {
        1: "up",
        2: "down",
        3: "idle",
        4: "connect",
        5: "active",
        -1: "unknown",
    }.get(key, f"unknown({v})")


def bgp_metrics_hint(metrics: dict[str, float], decoded: dict[str, str] | None = None) -> str:
    """
    Uses Telegraf enum mapping:
      admin_state: enable=1, disable=2
      oper_state:  up=1, down=2, idle=3, connect=4, active=5
    """
    admin = metrics.get("admin_state", -1)
    oper = metrics.get("oper_state", -1)

    rx = metrics.get("received_routes", 0)
    tx = metrics.get("sent_routes", 0)
    sup = metrics.get("suppressed_routes", 0)
    act = metrics.get("active_routes", 0)

    # If these are unknown/missing, *then* it’s insufficient.
    if admin in (-1, None) or oper in (-1, None):
        return "Insufficient metrics to infer a hint (missing admin_state/oper_state)."

    # Admin disabled
    if admin == 2:
        return "Admin DISABLED → likely intentionally shut (maintenance / config intent)."

    # Oper not UP
    if oper != 1:
        oper_txt = (decoded or {}).get("oper_state") or str(int(oper))
        return f"Oper not UP ({oper_txt}) → likely session not established (reachability/auth/timers)."

    # Oper UP from here down
    if rx == 0 and tx == 0 and act == 0:
        return "Session UP but no routes → possible policy/filtering/AFI mismatch or peer not advertising."
    if sup > 0:
        return "Routes are being suppressed → likely policy/validation suppressing candidates."
    if rx > 0 and act == 0:
        return "Routes received but none active → import policy/validation rejecting routes."
    if act > 0:
        return "Session UP with active routes → looks healthy; check logs for intermittent flaps."

    return "Metrics present but inconclusive (need more context)."


@dataclass(frozen=True)
class Endpoints:
    nautobot_url: str = "http://localhost:8080"
    prom_url: str = "http://localhost:9090"
    alertmanager_url: str = "http://localhost:9093"
    loki_url: str = "http://localhost:3001"


@dataclass
class EvidenceBundle:
    """
    A small, workshop-friendly container for evidence.
    Keeps printing + posting consistent and reduces "dict soup".
    """

    device: str
    peer_address: str
    afi_safi: str
    instance_name: str

    metrics: dict[str, float] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)
    sot: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        decoded = self.sot.get("decoded") or {}
        hint = bgp_metrics_hint(self.metrics or {}, decoded=decoded)
        return {
            "device": self.device,
            "peer_address": self.peer_address,
            "afi_safi": self.afi_safi,
            "instance_name": self.instance_name,
            "bgp_metrics_hint": hint,
            "metrics": self.metrics,
            "log_lines": len(self.logs),
            "sot": {
                "found": self.sot.get("found"),
                "maintenance": self.sot.get("maintenance"),
                "intended_peer": self.sot.get("intended_peer"),
                "expected_state": self.sot.get("expected_state"),
                "site": self.sot.get("site"),
                "role": self.sot.get("role"),
            },
            "decoded": decoded,
        }

    def to_rca_payload(self, max_log_lines: int = 40) -> dict[str, Any]:
        """
        What we send into the RCA prompt.
        """
        return {
            "metrics": self.metrics,
            "logs": self.logs[:max_log_lines],
            "sot": self.sot,
        }


@dataclass(frozen=True)
class Decision:
    ok: bool
    decision: str  # "proceed" | "skip" | "stop"
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


class DecisionPolicy:
    """
    Workshop policy (intent vs reality):

    1) stop if SoT can't find device
    2) skip if maintenance
    3) skip if peer not intended
    4) if SoT expects peer DOWN -> skip (not an incident)
    5) if SoT expects peer UP:
        - if metrics missing -> proceed (collect evidence)
        - if metrics say admin+oper are good -> skip (healthy)
        - else -> proceed (mismatch: investigate/quarantine)

    Optional flag:
      require_admin_up_for_quarantine=True
        -> only proceed when admin_state is ENABLE (1) but oper_state is NOT UP (!= 1)
        (prevents “quarantine” when peer is intentionally disabled)
    """

    def __init__(self, require_admin_up_for_quarantine: bool = False):
        self.require_admin_up_for_quarantine = require_admin_up_for_quarantine

    @staticmethod
    def _as_int(x: object, default: int = -1) -> int:
        try:
            # handle 1.0 cleanly
            return int(float(x))  # type: ignore[arg-type]
        except Exception:
            return default

    def evaluate(self, sot_gate: dict[str, Any], metrics: Optional[dict[str, float]] = None) -> Decision:
        if not sot_gate.get("found", True):
            return Decision(ok=False, decision="stop", reason=sot_gate.get("reason", "device not found"))

        if sot_gate.get("maintenance"):
            return Decision(ok=False, decision="skip", reason="device under maintenance")

        if not sot_gate.get("intended_peer"):
            return Decision(ok=False, decision="skip", reason="peer not intended in SoT")

        expected = (sot_gate.get("expected_state") or "established").lower()

        # If SoT expects DOWN, treat DOWN as expected behavior
        if expected in {"down", "disabled"}:
            return Decision(ok=False, decision="skip", reason="SoT expects this peer to be down/disabled")

        # Expected UP (established)
        if metrics is None:
            return Decision(ok=True, decision="proceed", reason="SoT expects up; metrics not provided (collect evidence)")

        admin = self._as_int(metrics.get("admin_state", -1))
        oper = self._as_int(metrics.get("oper_state", -1))

        # Telegraf enum mapping:
        # admin_state: enable=1, disable=2
        # oper_state: up=1, down=2, idle=3, connect=4, active=5
        admin_ok = (admin == 1)
        oper_ok = (oper == 1)

        # If everything matches intent, no action needed
        if admin_ok and oper_ok:
            return Decision(ok=False, decision="skip", reason="peer matches SoT intent (enabled + up)")

        # Optional stricter gating:
        # only proceed if admin is enabled but oper isn't up
        if self.require_admin_up_for_quarantine:
            if not (admin_ok and not oper_ok):
                return Decision(
                    ok=False,
                    decision="skip",
                    reason="metrics gate not met (expected admin_state=enable and oper_state!=up)",
                    details={"admin_state": admin, "oper_state": oper, "expected_state": expected},
                )

        # Otherwise mismatch is actionable
        return Decision(
            ok=True,
            decision="proceed",
            reason="SoT expects peer up, but metrics show mismatch",
            details={"expected_state": expected, "admin_state": admin, "oper_state": oper},
        )


# ------------------------
# Clients
# ------------------------


class PromClient:
    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def instant(self, query: str) -> list[dict]:
        r = requests.get(
            f"{self.base_url}/api/v1/query",
            params={"query": query},
            timeout=self.timeout,
        )
        r.raise_for_status()
        payload = r.json()
        return payload.get("data", {}).get("result", [])


class LokiClient:
    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def query_range(self, query: str, minutes: int = 10, limit: int = 200) -> list[str]:
        end = now_utc()
        start = end - dt.timedelta(minutes=minutes)

        params = {
            "query": query,
            "start": int(start.timestamp() * 1e9),  # ns
            "end": int(end.timestamp() * 1e9),
            "limit": limit,
            "direction": "BACKWARD",
        }
        r = requests.get(
            f"{self.base_url}/loki/api/v1/query_range",
            params=params,
            timeout=self.timeout,
        )
        r.raise_for_status()
        payload = r.json()

        lines: list[str] = []
        for stream in payload.get("data", {}).get("result", []):
            for _, line in stream.get("values", []):
                lines.append(line)

        return lines[:limit]

    def annotate(self, labels: dict[str, str], message: str) -> None:
        ts = str(time.time_ns())
        payload = {"streams": [{"stream": labels, "values": [[ts, message]]}]}
        r = requests.post(
            f"{self.base_url}/loki/api/v1/push",
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()


class AlertmanagerClient:
    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def create_silence(
        self,
        matchers: list[dict[str, Any]],
        minutes: int = 20,
        created_by: str = "prefect-workshop",
        comment: str = "Workshop quarantine: suppress repeat notifications while investigating.",
    ) -> str:
        starts = now_utc()
        ends = starts + dt.timedelta(minutes=minutes)

        body = {
            "matchers": matchers,
            "startsAt": to_rfc3339(starts),
            "endsAt": to_rfc3339(ends),
            "createdBy": created_by,
            "comment": comment,
        }
        r = requests.post(
            f"{self.base_url}/api/v2/silences",
            json=body,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json().get("silenceID", "")


class NautobotClient:
    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        token_secret_block: str = "nautobot-token",
        timeout: int = 10,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._token = token
        self._token_secret_block = token_secret_block

    @property
    def token(self) -> str:
        if self._token:
            return self._token
        return _load_secret(self._token_secret_block)

    def get_device(self, device_name: str) -> dict | None:
        headers = {"Authorization": f"Token {self.token}", "Accept": "application/json"}
        r = requests.get(
            f"{self.base_url}/api/dcim/devices/",
            headers=headers,
            params={"name": device_name},
            timeout=self.timeout,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        return results[0] if results else None

    # ---- SoT helpers (pure functions over device dict) ----

    @staticmethod
    def is_device_in_maintenance(device_obj: dict) -> bool:
        cf = device_obj.get("custom_fields") or device_obj.get("_custom_field_data") or {}
        return bool(cf.get("maintenance", False))

    @staticmethod
    def get_intended_bgp_sessions(device_obj: dict, afi_safi: str) -> list[dict]:
        ctx = device_obj.get("local_config_context_data") or {}
        bgp = ((ctx.get("observability_intent") or {}).get("bgp") or {})

        bgp_afi = bgp.get("afi_safi")
        if bgp_afi and bgp_afi != afi_safi:
            return []

        sessions = bgp.get("intended_peers") or []  # list[dict]
        return [s for s in sessions if isinstance(s, dict)]

    @staticmethod
    def get_intended_bgp_session(device_obj: dict, afi_safi: str, peer_address: str) -> dict | None:
        for s in NautobotClient.get_intended_bgp_sessions(device_obj, afi_safi):
            if (s.get("peer_ip") or "") == peer_address:
                return s
        return None

    def build_bgp_intent_gate(self, device: str, peer_address: str, afi_safi: str) -> dict[str, Any]:
        dev = self.get_device(device)
        if not dev:
            return {"found": False, "reason": "device not found in Nautobot"}

        maintenance = self.is_device_in_maintenance(dev)

        session = self.get_intended_bgp_session(dev, afi_safi=afi_safi, peer_address=peer_address)
        intended = session is not None
        expected_state = (session or {}).get("expected_state")  # "established" or "down" in your YAML

        return {
            "found": True,
            "maintenance": maintenance,
            "intended_peer": intended,
            "expected_state": expected_state,     # <-- NEW (critical)
            "session": session,                   # <-- NEW (optional but super useful for RCA)
            "device": dev.get("name", device),
            "site": (dev.get("site") or {}).get("name"),
            "role": (dev.get("device_role") or {}).get("name"),
        }


# ------------------------
# Optional LLM RCA (kept standalone)
# ------------------------


def llm_rca_openai(device: str, peer_address: str, evidence: dict, model: str = "gpt-4o-mini") -> str:
    """
    OpenAI-compatible RCA helper.
    Uses Prefect Secret block "openai-token" by default.
    """
    token = _load_secret("openai-token")
    from openai import OpenAI  # local import to keep sdk import-friendly

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
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content or ""


@dataclass
class WorkshopSDK:
    """
    Convenience wrapper:
    - holds configured clients
    - provides 'workshop-level' operations to keep flows readable
    """

    endpoints: Endpoints = Endpoints()

    # Optional overrides (useful for local dev without Prefect Secrets)
    nautobot_token: str | None = None
    nautobot_secret_block: str = "nautobot-token"

    timeout: int = 10

    def __post_init__(self) -> None:
        # Clients
        self.prom = PromClient(self.endpoints.prom_url, timeout=self.timeout)
        self.loki = LokiClient(self.endpoints.loki_url, timeout=self.timeout)
        self.am = AlertmanagerClient(self.endpoints.alertmanager_url, timeout=self.timeout)
        self.nb = NautobotClient(
            self.endpoints.nautobot_url,
            token=self.nautobot_token,
            token_secret_block=self.nautobot_secret_block,
            timeout=self.timeout,
        )

    # ------------------------
    # High-level "workshop ops"
    # ------------------------

    def bgp_gate(self, device: str, peer_address: str, afi_safi: str) -> dict[str, Any]:
        """SoT gate (FIXED: uses intended_peer consistently)."""
        return self.nb.build_bgp_intent_gate(device=device, peer_address=peer_address, afi_safi=afi_safi)

    def annotate(self, labels: dict[str, str], message: str) -> None:
        self.loki.annotate(labels=labels, message=message)

    def annotate_decision(self, workflow: str, device: str, peer_address: str, decision: str, message: str) -> None:
        self.annotate(
            labels={
                "source": "prefect",
                "workflow": workflow,
                "device": device,
                "peer_address": peer_address,
                "decision": decision,
            },
            message=message,
        )

    # ---- BGP helpers ----

    def bgp_queries(self, device: str, peer_address: str, afi_safi: str, instance_name: str) -> dict[str, str]:
        """
        Centralize query construction so students don't fight string formatting.
        """
        base = f'device="{device}",peer_address="{peer_address}",afi_safi_name="{afi_safi}",name="{instance_name}"'
        return {
            "admin_state": f"bgp_admin_state{{{base}}}",
            "oper_state": f"bgp_oper_state{{{base}}}",
            "received_routes": f"bgp_received_routes{{{base}}}",
            "sent_routes": f"bgp_sent_routes{{{base}}}",
            "suppressed_routes": f"bgp_suppressed_routes{{{base}}}",
            "active_routes": f"bgp_active_routes{{{base}}}",
        }

    def bgp_metrics_snapshot(
        self, device: str, peer_address: str, afi_safi: str, instance_name: str
    ) -> dict[str, float]:
        qs = self.bgp_queries(device=device, peer_address=peer_address, afi_safi=afi_safi, instance_name=instance_name)
        return {
            "admin_state": first_prom_value(self.prom.instant(qs["admin_state"]), default=-1),
            "oper_state": first_prom_value(self.prom.instant(qs["oper_state"]), default=-1),
            "received_routes": first_prom_value(self.prom.instant(qs["received_routes"]), default=0),
            "sent_routes": first_prom_value(self.prom.instant(qs["sent_routes"]), default=0),
            "suppressed_routes": first_prom_value(self.prom.instant(qs["suppressed_routes"]), default=0),
            "active_routes": first_prom_value(self.prom.instant(qs["active_routes"]), default=0),
        }

    def bgp_logql(self, device: str, peer_address: str) -> str:
        """
        Centralize the "reasonable starter" LogQL:
        - filters license noise
        - looks for common BGP terms + peer ip
        """
        return f'{{device="{device}"}} != "license" |~ "(bgp|BGP|neighbor|session|route|ipv4-unicast|{peer_address})"'

    def bgp_logs(self, device: str, peer_address: str, minutes: int = 10, limit: int = 200) -> list[str]:
        return self.loki.query_range(
            self.bgp_logql(device=device, peer_address=peer_address), minutes=minutes, limit=limit
        )

    def quarantine_bgp(self, device: str, peer_address: str, minutes: int = 20) -> str:
        """
        One-liner for the quarantine action: silence in Alertmanager.
        """
        silence_id = self.am.create_silence(
            matchers=[
                {"name": "alertname", "value": "BgpSessionNotUp", "isRegex": False},
                {"name": "device", "value": device, "isRegex": False},
                {"name": "peer_address", "value": peer_address, "isRegex": False},
            ],
            minutes=minutes,
        )
        return silence_id

    def collect_bgp_evidence(
        self,
        device: str,
        peer_address: str,
        afi_safi: str,
        instance_name: str,
        log_minutes: int = 10,
        log_limit: int = 200,
    ) -> EvidenceBundle:
        ev = EvidenceBundle(
            device=device,
            peer_address=peer_address,
            afi_safi=afi_safi,
            instance_name=instance_name,
        )

        ev.sot = self.bgp_gate(device=device, peer_address=peer_address, afi_safi=afi_safi)
        ev.metrics = self.bgp_metrics_snapshot(
            device=device, peer_address=peer_address, afi_safi=afi_safi, instance_name=instance_name
        )
        ev.sot["decoded"] = decode_bgp_states(ev.metrics)
        ev.logs = self.bgp_logs(device=device, peer_address=peer_address, minutes=log_minutes, limit=log_limit)

        return ev
