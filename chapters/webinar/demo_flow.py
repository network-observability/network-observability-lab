# demo_flow.py

from __future__ import annotations

import json
from prefect import flow, task

from netobs_workshop_sdk import WorkshopSDK, DecisionPolicy, llm_rca_openai

ENABLE_LLM_RCA = True
WORKFLOW_NAME = "demo_quarantine_bgp"


@task(log_prints=True, retries=2)
def collect_evidence_task(sdk: WorkshopSDK, device: str, peer_address: str, afi_safi: str, instance_name: str):
    ev = sdk.collect_bgp_evidence(
        device=device,
        peer_address=peer_address,
        afi_safi=afi_safi,
        instance_name=instance_name,
        log_minutes=10,
        log_limit=200,
    )
    print("🧾 Evidence summary:")
    print(json.dumps(ev.summary(), indent=2))
    return ev


@task(log_prints=True, retries=2)
def decide_task(policy: DecisionPolicy, ev):
    # policy evaluates SoT only by default; you can optionally pass metrics
    decision = policy.evaluate(sot_gate=ev.sot, metrics=ev.metrics)
    print(f"🧠 Decision: {decision.decision} | {decision.reason} | details={decision.details}")
    return decision


@task(log_prints=True, retries=2)
def quarantine_task(sdk: WorkshopSDK, ev):
    silence_id = sdk.quarantine_bgp(device=ev.device, peer_address=ev.peer_address, minutes=20)
    sdk.annotate(
        labels={"source": "prefect", "workflow": WORKFLOW_NAME, "device": ev.device, "peer_address": ev.peer_address, "afi_safi": ev.afi_safi},
        message=f"QUARANTINE applied: silenced BgpSessionNotUp for {ev.device} peer={ev.peer_address} (silence_id={silence_id})",
    )
    print(f"🔕 Quarantine done. silence_id={silence_id}")
    return silence_id


@task(log_prints=True, retries=2)
def annotate_skip_task(sdk: WorkshopSDK, ev, reason: str):
    sdk.annotate_decision(
        workflow=WORKFLOW_NAME,
        device=ev.device,
        peer_address=ev.peer_address,
        decision="skip",
        message=f"SKIP quarantine: {reason} (device={ev.device}, peer={ev.peer_address})",
    )


@task(log_prints=True, retries=0)
def rca_task(device: str, peer_address: str, ev):
    rca = llm_rca_openai(device=device, peer_address=peer_address, evidence=ev.to_rca_payload())
    print("\n===== RCA (LLM) =====\n")
    print(rca)
    print("\n=====================\n")
    return rca


@task(log_prints=True, retries=2)
def post_rca_task(sdk: WorkshopSDK, ev, rca: str):
    sdk.annotate(
        labels={"source": "prefect", "workflow": WORKFLOW_NAME, "device": ev.device, "peer_address": ev.peer_address, "type": "rca"},
        message=f"RCA: {rca}",
    )


@flow(log_prints=True)
def demo_quarantine_bgp_flow(device: str, peer_address: str, afi_safi: str = "evpn", instance_name: str = "default"):
    sdk = WorkshopSDK()

    # Default policy is SoT-only. Flip this to True if you want the "metrics gate" demo.
    policy = DecisionPolicy(require_admin_up_for_quarantine=False)

    print(f"🚨 Starting demo flow: device={device} peer={peer_address} afi_safi={afi_safi} name={instance_name}")

    ev = collect_evidence_task(sdk, device=device, peer_address=peer_address, afi_safi=afi_safi, instance_name=instance_name)
    decision = decide_task(policy, ev)

    if decision.decision == "stop":
        print(f"🔴 Stop: {decision.reason}")
        return

    if decision.decision == "skip":
        annotate_skip_task(sdk, ev, decision.reason)
        print(f"🟡 Skip: {decision.reason}")
        return

    _silence_id = quarantine_task(sdk, ev)

    if ENABLE_LLM_RCA:
        rca = rca_task(device=device, peer_address=peer_address, ev=ev)
        post_rca_task(sdk, ev, rca)

    print("✅ Demo flow complete")


if __name__ == "__main__":
    demo_quarantine_bgp_flow(device="leaf1", peer_address="192.0.2.1", afi_safi="evpn", instance_name="default")
