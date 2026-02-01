from __future__ import annotations

from typing import Any, Dict

from prefect import flow, task
from prefect.logging import get_run_logger

from netobs_workshop_sdk import Decision, DecisionPolicy, EvidenceBundle, WorkshopSDK


# ============================================================
# What you're building in this file
# ============================================================
# You're wiring a small automation:
#
#   Alert arrives → extract (device, peer) → collect evidence →
#   decide (skip vs proceed) → if proceed: quarantine + annotate
#
# The SDK already knows how to talk to Prometheus, Loki, Alertmanager, Nautobot.
# Your job is to "connect the dots" with a clear workflow.


# ============================================================
# Tasks: small building blocks (Prefect runs these with logs)
# ============================================================

@task(retries=2, retry_delay_seconds=3, log_prints=True)
def collect_bgp_evidence_task(
    device: str,
    peer_address: str,
    afi_safi: str,
    instance_name: str,
    log_minutes: int = 30,
    log_limit: int = 50,
) -> EvidenceBundle:
    """
    Collects all the evidence we need to make a good decision:
      - SoT intent (Nautobot): is this peer intended? expected_state?
      - Metrics (Prometheus): admin_state / oper_state / route counters
      - Logs (Loki): recent BGP-related log lines

    In the Prefect UI, this task is where you see the raw inputs.
    """
    logger = get_run_logger()
    logger.info("🔎 Collecting evidence for %s:%s (%s/%s)", device, peer_address, afi_safi, instance_name)

    sdk = WorkshopSDK()
    ev = sdk.collect_bgp_evidence(
        device=device,
        peer_address=peer_address,
        afi_safi=afi_safi,
        instance_name=instance_name,
        log_minutes=log_minutes,
        log_limit=log_limit,
    )

    # Helpful narration for the Prefect UI logs
    s = ev.summary()
    logger.info("Evidence hint: %s", s.get("bgp_metrics_hint"))
    logger.info("SoT gate: %s", s.get("sot"))
    logger.info("Decoded states: %s", s.get("decoded"))
    logger.info("Log lines: %s", s.get("log_lines"))

    return ev


@task(log_prints=True)
def evaluate_policy_task(ev: EvidenceBundle) -> Decision:
    """
    This is the "brain" of the workflow.

    We make a decision in TWO STAGES:

    1) SoT-only gate:
       - If the device is not found → STOP (we can't trust anything else)
       - If the device is in maintenance → SKIP (expected)
       - If the peer is not intended → SKIP (don't quarantine random peers)
       - If SoT expects DOWN → SKIP (not an incident)

    2) SoT + metrics gate:
       - If SoT expects UP and metrics show enabled+up → SKIP
       - If SoT expects UP but metrics show mismatch → PROCEED (actionable)

    Your TODO here is just to call the policy twice.
    """
    logger = get_run_logger()
    logger.info("🧠 Evaluating decision policy (you should see Stage 1 then Stage 2)")

    # --- TODO START ---
    # 1) Create the policy: policy = DecisionPolicy()
    # 2) Stage 1: sot_decision = policy.evaluate(ev.sot, metrics=None)
    #    - log it (decision + reason)
    #    - if stop/skip -> return it immediately
    # 3) Stage 2: metrics_decision = policy.evaluate(ev.sot, metrics=ev.metrics)
    #    - log it (decision + reason + details)
    #    - return it
    return Decision(ok=False, decision="skip", reason="TODO: implement DecisionPolicy evaluation", details={})
    # --- TODO END ---


@task(log_prints=True)
def annotate_decision_task(workflow: str, device: str, peer_address: str, decision: Decision) -> None:
    """
    We ALWAYS write an annotation for the decision — even when we skip.
    That gives you an "audit trail" in Loki:
      - what did we decide?
      - why did we decide it?
    """
    logger = get_run_logger()
    logger.info("📝 Annotating decision=%s reason=%s", decision.decision, decision.reason)

    sdk = WorkshopSDK()
    sdk.annotate_decision(
        workflow=workflow,
        device=device,
        peer_address=peer_address,
        decision=decision.decision,
        message=decision.reason,
    )


@task(log_prints=True)
def quarantine_task(device: str, peer_address: str, minutes: int = 20) -> str:
    """
    This is the actual "action" step.

    For the workshop, "quarantine" means:
      → create a silence in Alertmanager for this device + peer

    Your TODO is just to call the one SDK method and return the silence_id.
    """
    logger = get_run_logger()
    logger.info("🔕 Creating quarantine silence for %s:%s minutes=%d", device, peer_address, minutes)

    # --- TODO START ---
    # sdk = WorkshopSDK()
    # silence_id = sdk.quarantine_bgp(device=device, peer_address=peer_address, minutes=minutes)
    # return silence_id
    return "TODO-silence-id"
    # --- TODO END ---


@task(log_prints=True)
def annotate_action_task(workflow: str, device: str, peer_address: str, silence_id: str) -> None:
    """
    If we took an action, we also write an annotation about the action.
    This makes the demo super clear in Loki:
      "QUARANTINE applied (silence_id=...)"
    """
    logger = get_run_logger()
    logger.info("📝 Annotating action silence_id=%s", silence_id)

    sdk = WorkshopSDK()
    sdk.annotate(
        labels={
            "source": "prefect",
            "workflow": workflow,
            "device": device,
            "peer_address": peer_address,
        },
        message=f"QUARANTINE applied (silence_id={silence_id})",
    )


# ============================================================
# Main action flow (this is what gets launched per alert instance)
# ============================================================

@flow(log_prints=True)
def quarantine_bgp_flow(
    device: str,
    peer_address: str,
    afi_safi: str = "ipv4-unicast",
    instance_name: str = "default",
) -> Dict[str, Any]:
    """
    End-to-end "action flow" for ONE (device, peer):

      1) Collect evidence
      2) Evaluate policy (skip/stop/proceed)
      3) Always annotate the decision
      4) If proceed → quarantine + annotate the action

    In the Prefect UI you'll see:
      - collect_bgp_evidence_task
      - evaluate_policy_task
      - annotate_decision_task
      - (maybe) quarantine_task + annotate_action_task
    """
    logger = get_run_logger()
    workflow = "demo_quarantine_bgp"

    logger.info("⚙️ quarantine_bgp_flow: device=%s peer=%s", device, peer_address)

    ev = collect_bgp_evidence_task(
        device=device,
        peer_address=peer_address,
        afi_safi=afi_safi,
        instance_name=instance_name,
    )

    decision = evaluate_policy_task(ev)

    # Always annotate the decision (even skip/stop)
    annotate_decision_task(workflow, device, peer_address, decision)

    if decision.decision != "proceed":
        logger.info("✅ No action taken: decision=%s reason=%s", decision.decision, decision.reason)
        return {"action": "none", "decision": decision.__dict__, "evidence": ev.summary()}

    logger.info("🚨 Actionable mismatch -> applying quarantine")
    silence_id = quarantine_task(device, peer_address, minutes=20)
    annotate_action_task(workflow, device, peer_address, silence_id)

    return {"action": "quarantine", "silence_id": silence_id, "decision": decision.__dict__, "evidence": ev.summary()}


# ============================================================
# Alert receiver: turns a webhook payload into per-peer flow runs
# ============================================================

def _extract_bgp_fields(labels: Dict[str, str]) -> Dict[str, str]:
    """
    Alertmanager labels can vary a bit depending on how the alert rule was written.
    This function normalizes those labels into the names our SDK expects.

    Your TODO is to map common label keys into these four fields:
      - device
      - peer_address
      - afi_safi
      - instance_name

    Once this is correct, the same Prefect workflow can handle alerts
    coming from different labs / different naming conventions.
    """
    # --- TODO START ---
    # device = labels.get("device") or labels.get("hostname") or ""
    # peer_address = labels.get("peer_address") or labels.get("peer") or labels.get("neighbor") or ""
    # afi_safi = labels.get("afi_safi_name") or labels.get("afi_safi") or "ipv4-unicast"
    # instance_name = labels.get("name") or labels.get("instance_name") or "default"
    # return {...}
    return {
        "device": "",
        "peer_address": "",
        "afi_safi": "ipv4-unicast",
        "instance_name": "default",
    }
    # --- TODO END ---


@flow(log_prints=True, flow_run_name="alert_receiver | {alertname}:{status}")
def alert_receiver(alertname: str, status: str, alert_group: Dict[str, Any]) -> None:
    """
    This flow is the entry point called by your webhook service.

    What it does:
      - receives one Alertmanager "group" payload (can contain multiple alerts)
      - filters to only the alert we care about (BgpSessionNotUp)
      - for each alert instance:
          extract fields (device/peer/afi_safi/instance)
          launch quarantine_bgp_flow(device, peer, ...)

    Most attendees won't need to change this function.
    The "attendee work" is in:
      - _extract_bgp_fields()
      - evaluate_policy_task()
      - quarantine_task()
    """
    logger = get_run_logger()
    logger.info("📩 alert_receiver: alertname=%s status=%s", alertname, status)

    # Keep the demo focused: only react to the BGP alert used in the workshop
    if alertname != "BgpSessionNotUp":
        logger.info("🙈 Ignoring alertname=%s", alertname)
        return

    alerts = alert_group.get("alerts") or []
    logger.info("alerts_in_group=%d", len(alerts))

    for a in alerts:
        labels = a.get("labels") or {}
        fields = _extract_bgp_fields(labels)

        device = fields["device"]
        peer = fields["peer_address"]
        afi_safi = fields["afi_safi"]
        instance_name = fields["instance_name"]

        logger.info("➡️ instance device=%s peer=%s afi_safi=%s instance=%s", device, peer, afi_safi, instance_name)

        if not device or not peer:
            logger.warning("Skipping: missing device/peer labels=%s", labels)
            continue

        if status == "firing":
            quarantine_bgp_flow(device=device, peer_address=peer, afi_safi=afi_safi, instance_name=instance_name)
        else:
            logger.info("Resolved -> no action (optional extension exercise)")


if __name__ == "__main__":
    _ = alert_receiver.serve(name="alert-receiver")
