# 📘 Modern Network Observability – Workshop Catalog

This catalog documents the **Python SDK** used in the workshop and shows how to **explore and test it interactively with IPython** before building Prefect workflows.

The recommended learning path is:

> IPython → SDK exploration → decisions → Prefect flow

## 0) IMPORTANT: Point your shell to the existing Prefect server

Before starting IPython or running any Prefect flows, make sure your shell is configured to talk to the already running Prefect server (for the workshop lab). Run this command in your shell:

```bash
prefect config set PREFECT_API_URL=http://localhost:4200/api
```

Verify it is set correctly:

```bash
prefect config view
```

You should see `PREFECT_API_URL: http://localhost:4200/api` in the output.

⚠️ If `PREFECT_API_URL` is not set, Prefect may:

* fall back to an ephemeral/local server,
* or start background services unexpectedly.

Always export this before running ipython.

## 1) Start IPython

This workshop intentionally starts **outside Prefect** flows so you can:

* inspect real telemetry,
* iterate quickly,
* understand what each function returns.

```bash
ipython
```

## 2) Import the SDK

```python
from netobs_workshop_sdk import (
    WorkshopSDK,
    EvidenceBundle,
    DecisionPolicy,
    Decision,
)
sdk = WorkshopSDK()
```

The SDK gives you:

* `WorkshopSDK` → access to Prometheus, Loki, Alertmanager, Nautobot
* `EvidenceBundle` → structured container for metrics, logs, and SoT
* `DecisionPolicy` → explains why we act (or don’t)
* `Decision` → represents an action taken based on policies

## 3) Explore the SDK interactively

You can now explore the SDK interactively. For example, to fetch BGP peer evidence from Prometheus and Loki for a specific device and peer:

```python
ev = sdk.collect_bgp_evidence(
    device="srl1",
    peer_address="10.1.2.2",
    afi_safi="ipv4-unicast",
    instance_name="default",
    log_minutes=30,
    log_limit=50,
)
```

See a summary of the evidence collected:

```python
ev.summary()
```

Example output would be:

```python
{
    'device': 'srl1',
    'peer_address': '10.1.2.2',
    'afi_safi': 'ipv4-unicast',
    'instance_name': 'default',
    'bgp_metrics_hint': 'Routes received but none active → import policy/validation rejecting routes.',

    'metrics': {
        'admin_state': 1.0,
        'oper_state': 1.0,
        'received_routes': 10.0,
        'sent_routes': 10.0,
        'suppressed_routes': 0.0,
        'active_routes': 0.0
    },

    'log_lines': 4,

    'sot': {'found': True, 'maintenance': False, 'intended_peer': True, 'site': None, 'role': None},

    'decoded': {'admin_state': 'enable', 'oper_state': 'up'}
}
```

## 4) Explore the raw signals

You are encouraged to inspect the raw evidence directly:

```python
ev.metrics    # Prometheus-derived signals
ev.logs       # Raw log lines from Loki
ev.sot        # Source-of-Truth (Nautobot intent + maintenance)
```

This is where you learn:

* what disappears during a flap,
* what goes to zero,
* what intent actually says.

## 5) Make decisions based on evidence

You can also make decisions based on the evidence collected.

### SoT-only Policy

```python
policy = DecisionPolicy()
decision = policy.evaluate(ev.sot)
decision
```

The example output would be:

```python
Decision(ok=True, decision='proceed', reason='policy satisfied', details={})
```

### Metrics + SoT Policy

```python
policy = DecisionPolicy(require_admin_up_for_quarantine=True)
decision = policy.evaluate(ev.sot, ev.metrics)
decision
```

An example output would be:

```python
Decision(
  ok=False,
  decision="skip",
  reason="metrics gate not met (expected admin_state=1 and oper_state=0)",
  details={"admin_state": 1, "oper_state": 1}
)
```

## 6) Apply actions (Alertmanager quarantine)

```python
silence_id = sdk.quarantine_bgp(
    device=ev.device,
    peer_address=ev.peer_address,
    minutes=20,
)
silence_id
```
An example output would be:

```python
'c1f3b2e4-5d6a-4f7b-8c9d-0e1f2a3b4c5d'
```

You can verify the silence in Alertmanager UI http://<your-alertmanager-host>:9093/#/silences

## 7) Annotate what happened (Loki)

For a general annotation of the action taken, you can use:
```python
sdk.annotate(
    labels={
        "source": "prefect",
        "workflow": "demo_quarantine_bgp",
        "device": ev.device,
        "peer_address": ev.peer_address,
    },
    message=f"QUARANTINE applied (silence_id={silence_id})",
)
```

But for a decision-specific annotation, you can use:
```python
sdk.annotate_decision(
    workflow="demo_quarantine_bgp",
    device=ev.device,
    peer_address=ev.peer_address,
    decision="skip",
    message="SKIP quarantine: peer not intended in SoT",
)
```

## 7) RCA - Optional (LLM-ready)

```python
payload = ev.to_rca_payload()
payload.keys()
```

This payload is what a Prefect flow (or an LLM-based RCA step) would consume later.
