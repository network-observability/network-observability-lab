# student_flow.py
"""
Workshop exercise: BGP quarantine flow

RULES:
- Do NOT edit the SDK
- Only edit TODO sections
- If unsure: test in IPython first using the Catalog
"""

from __future__ import annotations

from prefect import flow, task

from netobs_workshop_sdk import (
    WorkshopSDK,
    DecisionPolicy,
    EvidenceBundle,
    llm_rca_openai,
)

ENABLE_LLM_RCA = True
WORKFLOW_NAME = "student_quarantine_bgp"


# ------------------------
# Tasks
# ------------------------

@task(log_prints=True, retries=2)
def collect_evidence(
    sdk: WorkshopSDK,
    device: str,
    peer_address: str,
    afi_safi: str,
    instance_name: str,
) -> EvidenceBundle:
    """
    TODO 1:
    - Collect BGP evidence using the SDK
    - Return an EvidenceBundle
    """
    ev = sdk.collect_bgp_evidence(
        device=device,
        peer_address=peer_address,
        afi_safi=afi_safi,
        instance_name=instance_name,
    )

    print(ev.summary())
    return ev


@task(log_prints=True, retries=2)
def decide(policy: DecisionPolicy, ev: EvidenceBundle):
    """
    TODO 2:
    - Evaluate the decision policy
    - Use metrics if the policy requires them
    """
    decision = policy.evaluate(ev.sot, ev.metrics)
    print(f"Decision: {decision.decision} | {decision.reason}")
    return decision


@task(log_prints=True, retries=2)
def quarantine(sdk: WorkshopSDK, ev: EvidenceBundle):
    """
    TODO 3:
    - Apply a quarantine (Alertmanager silence)
    - Annotate the action in Loki
    """
    silence_id = sdk.quarantine_bgp(
        device=ev.device,
        peer_address=ev.peer_address,
        minutes=20,
    )

    sdk.annotate(
        labels={
            "source": "prefect",
            "workflow": WORKFLOW_NAME,
            "device": ev.device,
            "peer_address": ev.peer_address,
            "afi_safi": ev.afi_safi,
        },
        message=f"QUARANTINE applied (silence_id={silence_id})",
    )

    return silence_id


@task(log_prints=True, retries=0)
def rca(ev: EvidenceBundle):
    """
    TODO 4 (optional):
    - Generate an RCA using the evidence bundle
    """
    rca_text = llm_rca_openai(
        device=ev.device,
        peer_address=ev.peer_address,
        evidence=ev.to_rca_payload(),
    )

    print("\n===== RCA =====\n")
    print(rca_text)
    print("\n==============\n")
    return rca_text


@task(log_prints=True, retries=2)
def annotate_skip(sdk: WorkshopSDK, ev: EvidenceBundle, reason: str):
    sdk.annotate_decision(
        workflow=WORKFLOW_NAME,
        device=ev.device,
        peer_address=ev.peer_address,
        decision="skip",
        message=f"SKIP quarantine: {reason}",
    )


# ------------------------
# Flow
# ------------------------

@flow(log_prints=True)
def student_quarantine_bgp_flow(
    device: str,
    peer_address: str,
    afi_safi: str = "evpn",
    instance_name: str = "default",
):
    sdk = WorkshopSDK()

    # TODO 5:
    # - Change this policy to include metric-based gating
    policy = DecisionPolicy(require_admin_up_for_quarantine=False)

    ev = collect_evidence(
        sdk,
        device=device,
        peer_address=peer_address,
        afi_safi=afi_safi,
        instance_name=instance_name,
    )

    decision = decide(policy, ev)

    if decision.decision == "stop":
        print(f"STOP: {decision.reason}")
        return

    if decision.decision == "skip":
        annotate_skip(sdk, ev, decision.reason)
        return

    _ = quarantine(sdk, ev)

    if ENABLE_LLM_RCA:
        rca_text = rca(ev)
        sdk.annotate(
            labels={
                "source": "prefect",
                "workflow": WORKFLOW_NAME,
                "device": ev.device,
                "peer_address": ev.peer_address,
                "type": "rca",
            },
            message=f"RCA: {rca_text}",
        )


if __name__ == "__main__":
    student_quarantine_bgp_flow(
        device="leaf1",
        peer_address="192.0.2.1",
        afi_safi="evpn",
        instance_name="default",
    )
