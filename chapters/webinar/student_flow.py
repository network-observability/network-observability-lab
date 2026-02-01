from __future__ import annotations

from typing import Any

from netobs_workshop_sdk import Decision, DecisionPolicy, EvidenceBundle, WorkshopSDK
from prefect import flow, tags, task
from prefect.logging import get_run_logger


# -------------------------------------------------------------------
# Tasks (small + readable; use SDK objects directly)
# -------------------------------------------------------------------
@task(
    retries=2,
    retry_delay_seconds=3,
    log_prints=True,
    task_run_name="collect_evidence[{device}:{peer_address}]",
)
def collect_bgp_evidence_task(
    device: str,
    peer_address: str,
    afi_safi: str,
    instance_name: str,
    log_minutes: int,
    log_limit: int,
) -> EvidenceBundle:
    logger = get_run_logger()
    print("🔎 [collect] Starting evidence collection")
    print(f"   - device={device}")
    print(f"   - peer_address={peer_address}")
    print(f"   - afi_safi={afi_safi}")
    print(f"   - instance_name={instance_name}")
    print(f"   - log_minutes={log_minutes} log_limit={log_limit}")

    sdk = WorkshopSDK()

    ev = sdk.collect_bgp_evidence(
        device=device,
        peer_address=peer_address,
        afi_safi=afi_safi,
        instance_name=instance_name,
        log_minutes=log_minutes,
        log_limit=log_limit,
    )

    sot = ev.sot or {}
    decoded = sot.get("decoded") or {}
    metrics = ev.metrics or {}

    print("✅ [collect] Evidence collected")
    print(
        "   - SoT gate:"
        f" found={sot.get('found')}"
        f" maintenance={sot.get('maintenance')}"
        f" intended_peer={sot.get('intended_peer')}"
        f" expected_state={sot.get('expected_state')}"
    )
    print(f"   - Decoded states: admin={decoded.get('admin_state')} oper={decoded.get('oper_state')}")
    print(
        "   - Raw states:"
        f" admin_state={metrics.get('admin_state')}"
        f" oper_state={metrics.get('oper_state')}"
        f" rx={metrics.get('received_routes')}"
        f" tx={metrics.get('sent_routes')}"
        f" act={metrics.get('active_routes')}"
        f" sup={metrics.get('suppressed_routes')}"
    )
    print(f"   - Logs: {len(ev.logs)} lines")

    # A short hint is great for narration
    hint = ev.summary().get("bgp_metrics_hint")
    logger.info("BGP hint: %s", hint)

    # Optional: show a couple of log samples (kept small)
    if ev.logs:
        sample = ev.logs[:2]
        print("   - Log sample:")
        for line in sample:
            print(f"     • {line}")

    return ev


@task(log_prints=True, task_run_name="evaluate_policy[{device}:{peer_address}]")
def evaluate_policy_task(device: str, peer_address: str, ev: EvidenceBundle) -> Decision:
    """
    Uses your DecisionPolicy exactly:
      - SoT only => stop/skip/proceed
      - SoT + metrics => skip/proceed
    """
    logger = get_run_logger()

    print("🧠 [policy] Evaluating decision policy (two-stage)")
    print(f"   - device={device} peer_address={peer_address}")
    print("   - Stage 1: SoT-only gate (maintenance / intended / expected_state)")

    policy = DecisionPolicy()

    sot_decision = policy.evaluate(ev.sot, metrics=None)
    print(f"   - SoT decision: decision={sot_decision.decision} ok={sot_decision.ok} reason={sot_decision.reason}")
    if sot_decision.details:
        logger.info("SoT decision details: %s", sot_decision.details)

    if sot_decision.decision in {"stop", "skip"}:
        print("🛑 [policy] Exiting early due to SoT gate")
        return sot_decision

    print("   - Stage 2: SoT + metrics check (intent vs reality)")
    metrics_decision = policy.evaluate(ev.sot, metrics=ev.metrics)
    print(
        "   - Metrics decision:"
        f" decision={metrics_decision.decision}"
        f" ok={metrics_decision.ok}"
        f" reason={metrics_decision.reason}"
    )
    if metrics_decision.details:
        logger.info("Metrics decision details: %s", metrics_decision.details)

    return metrics_decision


@task(log_prints=True, task_run_name="annotate_decision[{device}:{peer_address}]")
def annotate_decision_task(
    workflow: str,
    device: str,
    peer_address: str,
    decision: Decision,
) -> None:
    print("📝 [annotate] Writing decision annotation to Loki")
    print(f"   - workflow={workflow}")
    print(f"   - device={device} peer_address={peer_address}")
    print(f"   - decision={decision.decision} reason={decision.reason}")

    sdk = WorkshopSDK()
    sdk.annotate_decision(
        workflow=workflow,
        device=device,
        peer_address=peer_address,
        decision=decision.decision,
        message=decision.reason,
    )
    print("✅ [annotate] Decision annotation written")


@task(log_prints=True, task_run_name="quarantine[{device}:{peer_address}]")
def quarantine_task(device: str, peer_address: str, minutes: int) -> str:
    print("🔕 [quarantine] Creating Alertmanager silence (quarantine)")
    print(f"   - device={device} peer_address={peer_address} minutes={minutes}")

    sdk = WorkshopSDK()
    silence_id = sdk.quarantine_bgp(device=device, peer_address=peer_address, minutes=minutes)

    print(f"✅ [quarantine] Silence created: {silence_id}")
    return silence_id


@task(log_prints=True, task_run_name="annotate_action[{device}:{peer_address}]")
def annotate_action_task(
    workflow: str,
    device: str,
    peer_address: str,
    silence_id: str,
) -> None:
    print("📝 [annotate] Writing action annotation to Loki")
    print(f"   - workflow={workflow}")
    print(f"   - device={device} peer_address={peer_address}")
    print(f"   - silence_id={silence_id}")

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
    print("✅ [annotate] Action annotation written")


# -------------------------------------------------------------------
# Action flows (triggered by alert_receiver)
# -------------------------------------------------------------------
@flow(log_prints=True, flow_run_name="quarantine_bgp | {device}:{peer_address}")
def quarantine_bgp_flow(
    device: str,
    peer_address: str,
    afi_safi: str = "ipv4-unicast",
    instance_name: str = "default",
    log_minutes: int = 30,
    log_limit: int = 50,
    quarantine_minutes: int = 20,
) -> dict[str, Any]:
    """
    Demo flow:
      evidence -> decision -> (maybe quarantine) -> annotations
    """
    logger = get_run_logger()

    print("⚙️  [flow] Starting quarantine_bgp_flow")
    print(f"   - device={device} peer_address={peer_address}")
    print(f"   - afi_safi={afi_safi} instance_name={instance_name}")
    print(f"   - log_minutes={log_minutes} log_limit={log_limit}")
    print(f"   - quarantine_minutes={quarantine_minutes}")

    with tags(
        f"device:{device}",
        f"peer_address:{peer_address}",
        f"afi_safi:{afi_safi}",
        f"instance:{instance_name}",
        "action:quarantine",
    ):
        ev = collect_bgp_evidence_task(
            device=device,
            peer_address=peer_address,
            afi_safi=afi_safi,
            instance_name=instance_name,
            log_minutes=log_minutes,
            log_limit=log_limit,
        )

        summary = ev.summary()
        logger.info("Evidence summary: %s", summary)

        decision = evaluate_policy_task(
            device=device,
            peer_address=peer_address,
            ev=ev,
        )

        annotate_decision_task(
            workflow="demo_quarantine_bgp",
            device=device,
            peer_address=peer_address,
            decision=decision,
        )

        if decision.decision != "proceed":
            print("✅ [flow] Decision is not actionable — no quarantine will be applied")
            print(f"   - decision={decision.decision} reason={decision.reason}")
            return {
                "device": device,
                "peer_address": peer_address,
                "action": "none",
                "decision": {
                    "ok": decision.ok,
                    "decision": decision.decision,
                    "reason": decision.reason,
                    "details": decision.details,
                },
                "evidence_summary": summary,
            }

        print("🚨 [flow] Decision is actionable — applying quarantine")
        silence_id = quarantine_task(device=device, peer_address=peer_address, minutes=quarantine_minutes)
        logger.info("Quarantine applied: silence_id=%s", silence_id)

        annotate_action_task(
            workflow="demo_quarantine_bgp",
            device=device,
            peer_address=peer_address,
            silence_id=silence_id,
        )

        print("✅ [flow] Quarantine flow completed")
        return {
            "device": device,
            "peer_address": peer_address,
            "action": "quarantine",
            "silence_id": silence_id,
            "decision": {
                "ok": decision.ok,
                "decision": decision.decision,
                "reason": decision.reason,
                "details": decision.details,
            },
            "evidence_summary": summary,
        }


@flow(log_prints=True, flow_run_name="resolved_bgp | {device}:{peer_address}")
def resolved_bgp_flow(
    device: str,
    peer_address: str,
    afi_safi: str = "ipv4-unicast",
    instance_name: str = "default",
) -> None:
    """
    Minimal resolved handler: keep the audit trail.
    """
    print("🧊 [flow] Starting resolved_bgp_flow")
    print(f"   - device={device} peer_address={peer_address}")
    print(f"   - afi_safi={afi_safi} instance_name={instance_name}")

    with tags(
        f"device:{device}",
        f"peer_address:{peer_address}",
        f"afi_safi:{afi_safi}",
        f"instance:{instance_name}",
        "status:resolved",
    ):
        decision = Decision(ok=False, decision="resolved", reason="Alert resolved", details={})
        annotate_decision_task(
            workflow="demo_quarantine_bgp",
            device=device,
            peer_address=peer_address,
            decision=decision,
        )
    print("✅ [flow] Resolved flow completed")


# -------------------------------------------------------------------
# Alert receiver (Alertmanager webhook payload -> flow fan-out)
# -------------------------------------------------------------------
def _extract_bgp_fields(labels: dict[str, str]) -> dict[str, str]:
    device = labels.get("device") or labels.get("hostname") or ""
    peer_address = labels.get("peer_address") or labels.get("peer") or labels.get("neighbor") or ""
    afi_safi = labels.get("afi_safi_name") or labels.get("afi_safi") or "ipv4-unicast"
    instance_name = labels.get("name") or labels.get("instance_name") or "default"
    return {
        "device": device,
        "peer_address": peer_address,
        "afi_safi": afi_safi,
        "instance_name": instance_name,
    }


@flow(log_prints=True, flow_run_name="alert_receiver | {alertname}:{status}")
# @flow(log_prints=True, flow_run_name="alert_receiver")
# def alert_receiver(alert_group: dict[str, Any]) -> None:
def alert_receiver(alertname: str, status: str, alert_group: dict[str, Any]) -> None:
    logger = get_run_logger()
    print(f"🏁 [receiver] Starting alert_receiver flow: alertname={alertname} status={status}")

    status = alert_group.get("status", "unknown")
    group_labels = alert_group.get("groupLabels") or {}
    alertname = group_labels.get("alertname") or "unknown"
    alerts = alert_group.get("alerts") or []

    print("📩 [receiver] Alertmanager webhook received")
    print(f"   - group alertname={alertname} status={status}")
    print(f"   - group_labels={group_labels}")
    print(f"   - alerts_in_group={len(alerts)}")

    # Keep this tight for the workshop demo
    if alertname not in {"BgpSessionNotUp"}:
        print(f"🙈 [receiver] Ignoring alertname={alertname} (not part of Workshop 4 demo)")
        return

    for idx, a in enumerate(alerts, start=1):
        labels = a.get("labels") or {}
        annotations = a.get("annotations") or {}
        starts_at = a.get("startsAt")
        ends_at = a.get("endsAt")

        print(f"➡️  [receiver] Processing alert {idx}/{len(alerts)}")
        print(f"   - labels={labels}")
        if annotations:
            print(f"   - annotations={annotations}")
        if starts_at:
            print(f"   - startsAt={starts_at}")
        if ends_at:
            print(f"   - endsAt={ends_at}")

        fields = _extract_bgp_fields(labels)
        device = fields["device"]
        peer_address = fields["peer_address"]

        print("   - extracted fields:")
        print(f"     device={device}")
        print(f"     peer_address={peer_address}")
        print(f"     afi_safi={fields['afi_safi']}")
        print(f"     instance_name={fields['instance_name']}")

        if not device or not peer_address:
            logger.warning("Skipping alert instance: missing device/peer_address. labels=%s", labels)
            continue

        if status == "firing":
            print("🔥 [receiver] Status=firing → launching quarantine flow")
            quarantine_bgp_flow(
                device=device,
                peer_address=peer_address,
                afi_safi=fields["afi_safi"],
                instance_name=fields["instance_name"],
            )
        else:
            print("✅ [receiver] Status!=firing → launching resolved flow")
            resolved_bgp_flow(
                device=device,
                peer_address=peer_address,
                afi_safi=fields["afi_safi"],
                instance_name=fields["instance_name"],
            )

    print("🏁 [receiver] Alert group processed, exiting")


# -------------------------------------------------------------------
# Serve entrypoint (Prefect will create a served deployment)
# -------------------------------------------------------------------
if __name__ == "__main__":
    _ = alert_receiver.serve(name="alert-receiver")
