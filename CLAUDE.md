# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A network observability laboratory accompanying the "Modern Network Observability" book. It combines containerized Arista cEOS routers (via Containerlab) with a full observability stack (Telegraf, Prometheus, Loki, Grafana, Alertmanager, Nautobot, Prefect). Chapter-based scenarios (`chapters/`) build progressively from Ch3 through Ch13.

## Common Commands

```bash
# Install the netobs CLI (primary interface for everything)
pip install .

# Deploy the full lab stack
netobs lab deploy --scenario batteries-included

# Manage observability stack
netobs docker {start,stop,restart,logs,ps,exec,build,destroy}
netobs docker logs telegraf-01 --tail 20 --follow

# Rebuild specific services after config changes
netobs lab update telegraf-01 telegraf-02

# Manage network topology (containerlab)
netobs containerlab {deploy,destroy,inspect}

# Utility commands
netobs utils load-nautobot          # Populate Nautobot from topology (run after first deploy)
netobs utils device-interface-flap --device ceos-02 --interface Ethernet2

# Check full stack health
netobs lab show
```

## Linting

```bash
ruff check .          # Lint (120 char line length, see pyproject.toml)
ruff check . --fix    # Auto-fix
```

No test suite exists — scenarios are validated by deploying and exercising them manually.

## Architecture

### Three-Layer Design

1. **Network Layer** (`containerlab/lab.yml`): Two Arista cEOS routers on Docker bridge `198.51.100.0/24`
2. **Data Collection**: Telegraf (SNMP/gNMI/SSH metrics) + Logstash (syslog) → Prometheus + Loki
3. **Observability Stack**: Grafana (dashboards) + Nautobot (source of truth enrichment) + Alertmanager → Keep/Slack/Prefect webhooks

### Chapter Scenario Pattern

Each chapter in `chapters/` has two variants:
- `ch<N>/` — skeleton for hands-on exercises
- `ch<N>-completed/` — reference implementation

Each scenario directory contains its own `docker-compose.yml` plus configs for each component (telegraf, prometheus, loki, grafana, logstash, alertmanager, nautobot, webhook).

### Alerting Chain

Prometheus/Loki rules → Alertmanager routes (matched by labels) → webhook receiver (FastAPI `webhook/app/main.py`) → Prefect deployment trigger

### CLI Tool (`netobs/main.py`)

Typer-based CLI. `setup` commands provision remote DigitalOcean infrastructure; all other commands interact with the local lab. Target a specific scenario via `--scenario <name>` or the `LAB_SCENARIO` env var.

## Project-Specific Conventions

### Custom Telegraf Collectors
- Location: `chapters/*/telegraf/routing_collector.py`
- Output **Influx Line Protocol** to stdout; consumed by Telegraf's `[[inputs.execd]]` plugin
- Use Netmiko to SSH into devices, parse with TextFSM/TTP, return `InfluxMetric` dataclasses

### Docker Naming
- All stacks connect to external bridge network `network-observability`
- Project name: `netobs` (passed via `--project-name`)
- Service naming: `<tool>-<instance>` (e.g., `telegraf-01`, `grafana`)

### Environment Variables
Loaded from `.env` + `.setup.env` + `os.environ` (all merged). Copy `example.env` → `.env` to start. Key vars:
- `NETWORK_AGENT_USER` / `NETWORK_AGENT_PASSWORD` — device SSH credentials
- `NAUTOBOT_SUPERUSER_API_TOKEN` — for topology loading
- `LAB_SUDO=true` — required if containerlab needs sudo

### Python in Scenarios (Ch12+)
- `webhook/app/main.py` — FastAPI service receiving Alertmanager alerts, triggering Prefect
- `event-automation.py`, `rca.py` — Prefect flows for event-driven automation
- Secrets stored in Prefect Blocks (`Secret.load()`)

### Logging Style
Rich console with themed output: `console.log(..., style="info|warning|error|good")`

## What NOT to Change

- `containerlab/lab.yml` network topology — hardcoded IPs and device names are referenced throughout all scenarios
- Docker network name `network-observability` — external dependency across all scenarios
- Credentials in `example.env` — intentionally simple for lab use
- `netobs` CLI command structure — stable interface expected by users

## Debugging Tips

- **Nautobot not ready**: `netobs docker logs nautobot --tail 10 -f` — wait for "Nautobot initialized!"
- **Missing metrics**: Check Prometheus targets at `http://localhost:9090/targets`
- **Permission errors**: Set `LAB_SUDO=true` in `.env`
- **Docker Compose**: Use `docker compose` (v2); set `DOCKER_COMPOSE_WITH_HASH=true` for older installs
- **Trigger test alerts**: `netobs utils device-interface-flap --device ceos-02 --interface Ethernet2`
- **SSH to device**: `ssh netobs@ceos-02` (password: `netobs123`)
