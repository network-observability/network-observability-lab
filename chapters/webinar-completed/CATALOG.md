# 📘 Modern Network Observability - Workshop Catalog

This catalog documents the **Python SDK** used in the workshop and shows how to **explore and test it interactively with IPython** before building Prefect workflows.

The recommended learning path is:

> IPython → SDK exploration → decisions → Prefect flow

## 0) IMPORTANT: Point your shell to the existing Prefect server

Before starting IPython or running any Prefect flows, make sure your shell is configured to talk to the already running Prefect server (for the workshop lab). Run this command in your shell:

```bash
# Navigate to the workshop code directory
cd ~/network-observability-lab/chapters/webinar

# Set the PREFECT_API_URL to point to the local Prefect server
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
from rich.pretty import install
install()

from netobs_workshop_sdk import (
    WorkshopSDK,
    EvidenceBundle,
    DecisionPolicy,
    Decision,
)
sdk = WorkshopSDK()
```

The SDK gives you:

* `sdk.prom` → Prometheus instant queries
* `sdk.loki` → LogQL queries + annotations
* `sdk.am` → Alertmanager silences
* `sdk.nb` → Nautobot SoT (custom fields + local context)
* `EvidenceBundle` → structured container for metrics, logs, and SoT
* `DecisionPolicy` → explains why we act (or don't)
* `Decision` → represents an action taken based on policies

## 3) Key workshop conventions (important)

### BGP metric labels

In this lab, the BGP metrics are labeled like:

* `device="srl1"`
* `peer_address="10.1.2.2"`
* `afi_safi_name="ipv4-unicast"`
* `name="default"` ✅ (instance_name)

So when using the SDK:

* use `instance_name="default"`
* use `afi_safi="ipv4-unicast"`

BGP state enum mapping (decoded meaning)

The BGP admin/oper values are produced by Telegraf enum mapping:

* `admin_state`: `enable=1`, `disable=2`
* `oper_state`: `up=1`, `down=2`, `idle=3`, `connect=4`, `active=5`

The SDK summary includes:

* `metrics_hint` → hint derived from metrics only
* `decoded` → human-friendly decode for admin/oper

## 4) Explore SoT (Nautobot): Device + Maintenance + Config Context

### Fetch a device

```python
dev = sdk.nb.get_device("srl1")
dev["name"]
```

### Read maintenance flag (custom field)

```python
sdk.nb.is_device_in_maintenance(dev)
```

### Inspect local config context

```python
ctx = dev.get("local_config_context_data") or {}
ctx
```

## 5) Check the "intent" for a BGP peer

In part of the workshop, we will check if a BGP peer is intended in Nautobot.

```python
gate = sdk.nb.build_bgp_intent_gate(device="srl1", peer_address="10.1.2.2", afi_safi="ipv4-unicast")
gate
```

You should see something similar to:

```python
{
    'found': True,
    'maintenance': False,
    'intended_peer': True,
    'expected_state': 'established',
    'session': {'peer_ip': '10.1.2.2', 'remote_as': 65102, 'expected_state': 'established', 'expected_prefixes_received': 10},
    'device': 'srl1',
    'site': None,
    'role': None
}
```

> NOTE: The `expected_state` is our intent for the BGP peer, and in this case it is "established".

## 6) Check the "reality" for a BGP peer

First let's explore the metrics for a BGP peer:

```python
qs = sdk.bgp_queries(
    device="srl1",
    peer_address="10.1.2.2",
    afi_safi="ipv4-unicast",
    instance_name="default",
)
qs
```

Then run the queries one by one:

```python
for k, q in qs.items():
    res = sdk.prom.instant(q)
    print(k, "=>", res[:1])
```

It should show the resulting metrics, for example:

```python
admin_state => [{'metric': {'__name__': 'bgp_admin_state', 'afi_safi_name': 'ipv4-unicast', 'collection_type': 'gnmi', 'device': 'srl1', 'host': 'telegraf-01', 'instance': 'telegraf-01:9004', 'job': 'telegraf', 'name': 'default', 'peer_address': '10.1.2.2'}, 'value': [1769585404.363, '1']}]
```

### Get Normalized BGP metrics snapshot

```python
m = sdk.bgp_metrics_snapshot(
    device="srl1",
    peer_address="10.1.2.2",
    afi_safi="ipv4-unicast",
    instance_name="default",
)
m
```

You should see something similar to:

```python
{
    'admin_state': 1.0,
    'oper_state': 1.0,
    'received_routes': 10.0,
    'sent_routes': 10.0,
    'suppressed_routes': 0.0,
    'active_routes': 0.0
}
```

It is basically a parsed version of the Prometheus metrics for easier consumption.

### Fetch recent BGP logs from Loki

We can also fetch recent BGP logs for the peer from , the following shows the LogQL query used:

```python
sdk.bgp_logql(device="srl1", peer_address="10.1.2.2")
```

> NOTE: If you need to generate some logs, you can flap the BGP session by disabling/enabling on the device or running the command:
> ```bash
> netobs utils device-interface-flap \
>    --device srl1 \
>    --interface ethernet-1/1 \
>    --count 2 \
>    --delay 2 \
>    --platform nokia_srl
> ```

You can fetch the logs like this:

```python
logs = sdk.bgp_logs(
    device="srl1",
    peer_address="10.1.2.2",
    minutes=30,
    limit=50,
)
len(logs)
```

## 8) Correlation: Collect an EvidenceBundle (SoT + metrics + logs)

This part is the core of the workshop. The idea is to **collect all signals related to a BGP peer into a single EvidenceBundle** that can be used for decision-making.

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

    'sot': {'found': True, 'maintenance': False, 'intended_peer': True, 'expected_state': 'established', 'site': None, 'role': None},

    'decoded': {'admin_state': 'enable', 'oper_state': 'up'}
}
```

### Explore the raw signals

You are encouraged to inspect the raw evidence directly:

```python
ev.metrics    # Prometheus-derived signals
ev.logs       # Raw log lines from Loki
ev.sot        # Source-of-Truth (Nautobot intent + maintenance)
```

This is where you learn:

* what disappears during a flap,
* what goes to zero,
* what intent says and compares to reality.

## 9) Make decisions based on evidence

The following is an example of how to use the `DecisionPolicy` to evaluate the evidence collected.

### SoT-only Policy

Use this when you just want "should we even look at this peer?"

```python
policy = DecisionPolicy()
decision = policy.evaluate(ev.sot)
decision
```

The example output would be:

```python
Decision(ok=True, decision='proceed', reason='SoT expects up; metrics not provided (collect evidence)', details={})
```

Typical outcomes:

* `stop` → device not found
* `skip` → maintenance OR peer not intended OR SoT expects down
* `proceed` → SoT expects up, now go collect metrics/logs (or continue workflow)

### Metrics + SoT Policy (validate intent vs reality)

```python
policy = DecisionPolicy()
decision = policy.evaluate(ev.sot, ev.metrics)
decision
```

An example output would be:

```python
Decision(
  ok=False,
  decision="skip",
  reason="peer matches SoT intent (enabled + up)",
  details={}
)
```

### Broken peer example

Try the process above with a broken peer (e.g., `srl2` and `10.1.11.1`).

```python
ev_broken = sdk.collect_bgp_evidence(
    device="srl2",
    peer_address="10.1.11.1",
    afi_safi="ipv4-unicast",
    instance_name="default",
    log_minutes=30,
    log_limit=50,
)
policy = DecisionPolicy()
decision_broken = policy.evaluate(ev_broken.sot, ev_broken.metrics)
decision_broken
```

## 10) Apply actions (Alertmanager quarantine)

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

## 11) Annotate what happened (Loki)

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

## 12) RCA - Optional (LLM-ready)

```python
payload = ev.to_rca_payload()
payload.keys()
```

This payload is what a Prefect flow (or an LLM-based RCA step) would consume later.
