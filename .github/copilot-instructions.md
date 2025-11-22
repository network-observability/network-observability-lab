# Copilot Instructions for Network Observability Lab

## Project Overview

This is a **network observability laboratory** built for the "Modern Network Observability" book. It combines containerized network devices (Arista cEOS via Containerlab) with a full observability stack (Telegraf, Logstash, Prometheus, Loki, Grafana, Alertmanager, Nautobot). The project demonstrates progressive observability concepts through chapter-based scenarios.

**Chapter Progression**: Scenarios build on each other (Ch 3 → Ch 5 → Ch 6 → Ch 7 → Ch 8 → Ch 9 → Ch 12 → Ch 13), with each adding new components or capabilities. Start with earlier chapters to understand foundational patterns before advanced automation/ML features.

## Architecture

### Multi-Scenario Structure
- **Scenario Pattern**: Each chapter has two variants in `chapters/`:
  - `ch<N>/` - Skeleton setup for following exercises
  - `ch<N>-completed/` - Fully configured reference implementation
  - `batteries-included/` - Production-like demo with all integrations

### Core Components
1. **Network Layer** (`containerlab/lab.yml`): Two Arista cEOS routers on a Docker bridge network (`198.51.100.0/24`)
2. **Data Collection**: Telegraf (metrics via SNMP/gNMI/SSH) + Logstash (syslog processing)
3. **Storage**: Prometheus (metrics) + Loki (logs)
4. **Visualization**: Grafana with Nautobot enrichment
5. **Alerting**: Prometheus/Loki rules → Alertmanager → Keep/Slack/webhooks
6. **Automation**: Prefect workflows for event-driven responses (Ch 12+)
7. **Source of Truth**: Nautobot populated from `containerlab/lab_vars.yml`

## Critical Workflows

### Environment Setup
```bash
# 1. Configure environment (copy example.env → .env, edit as needed)
cp example.env .env

# 2. Import cEOS image (required, not included)
docker import cEOS64-lab-<version>.tar.xz ceos:image

# 3. Install CLI tool
pip install .  # Creates 'netobs' command

# 4. Deploy full stack
netobs lab deploy --scenario batteries-included
```

### CLI Tool (`netobs`)
The `netobs/main.py` Typer CLI is the **primary interface**:
- `netobs setup {deploy,destroy,show}` - Remote DigitalOcean droplet provisioning (one-time setup)
- `netobs containerlab {deploy,destroy,inspect}` - Manage network topology (local operations)
- `netobs docker {start,stop,logs,exec,build}` - Control observability stack (local operations)
- `netobs lab {deploy,destroy,prepare,update,rebuild}` - Orchestrate both layers (local operations)
- `netobs utils {load-nautobot,device-interface-flap}` - Utility commands (local operations)

**Key Patterns**:
- `setup` commands provision remote infrastructure; all other commands interact with local lab
- Commands accept `--scenario <name>` to target specific chapter setups (default via `LAB_SCENARIO` env var)

### Development Cycle
```bash
# Edit config in chapters/batteries-included/telegraf/
netobs lab update telegraf-01 telegraf-02  # Rebuild+restart specific services

# View logs
netobs docker logs telegraf-01 --tail 20 --follow

# Access container shell
netobs docker exec telegraf-01 bash
```

## Project-Specific Conventions

### Telegraf Custom Collectors
- **Location**: `chapters/*/telegraf/routing_collector.py`
- **Pattern**: Python scripts output **Influx Line Protocol** to stdout
- **Integration**: Telegraf's `[[inputs.execd]]` plugin consumes these scripts
- **Example Structure**:
  ```python
  @dataclass
  class InfluxMetric:
      measurement: str
      tags: dict      # device, device_type, vrf, etc.
      fields: dict    # numeric values or strings

  def <protocol>_collector(net_connect: BaseConnection, host: str) -> list[InfluxMetric]:
      # Use netmiko to run show commands
      # Parse with TextFSM/TTP
      # Return metrics
  ```
- Telegraf config mounts these scripts as volumes (see `docker-compose.yml`)

### Docker Compose Naming
- All stacks use `network-observability` external bridge network
- Project name: `netobs` (via `--project-name` flag)
- Services follow pattern: `<tool>-<instance>` (e.g., `telegraf-01`, `telegraf-02`)

### Environment Variables
- **Configuration**: `.env` + `.setup.env` loaded by `netobs` CLI
- **Dotenv Pattern**: `ENVVARS = {**dotenv_values(".env"), **dotenv_values(".setup.env"), **os.environ}`
- **Required for operations**:
  - `NETWORK_AGENT_USER`/`NETWORK_AGENT_PASSWORD` - Device SSH credentials
  - `NAUTOBOT_SUPERUSER_API_TOKEN` - For topology loading
  - `LAB_SUDO` - Whether containerlab needs sudo (typically `true`)

### Nautobot Integration
- **Enrichment Source**: Grafana queries Nautobot's GraphQL API to add device metadata
- **Initialization**: Run `netobs utils load-nautobot` after first deploy
- **Data Sources**:
  - Containerlab topology (`containerlab/lab.yml`)
  - Extended attributes (`containerlab/lab_vars.yml`) with interface IPs

### Alerting Chain
1. **Prometheus/Loki Rules** (`prometheus/rules/*.yml`, `loki/rules/*.yml`)
2. **Alertmanager Routes** (`alertmanager/alertmanager.yml`) - Match by labels
3. **Receivers**: webhook → Prefect flow, Slack (API URL in `alertmanager/slack_webhook` - gitignored)

### Python Applications in Scenarios
- **Prefect Workflows** (Ch 12+): `event-automation.py`, `rca.py`, `devnet-demo.py` - Event-driven automation flows
- **FastAPI Services**: `webhook/app/main.py` - Receives Alertmanager alerts, triggers Prefect deployments
- **CLI Tools**: `observer.py` - Standalone command-line utilities for observability operations
- **Pattern**: Webhook validates Prefect Cloud URL → triggers deployment via API
- **Secrets**: Store in Prefect Blocks (accessed via `Secret.load()`) or environment variables

## Key Files/Directories

- `netobs/main.py` - CLI orchestration logic, all management commands
- `containerlab/lab.yml` + `lab_vars.yml` - Network topology + Nautobot seed data
- `chapters/batteries-included/docker-compose.yml` - Full stack definition (338 lines, includes Prefect)
- `chapters/batteries-included/README.md` - Hands-on tutorial with alert creation example
- `chapters/batteries-included/telegraf/routing_collector.py` - Reference custom collector
- `.env` - Primary configuration (copy from `example.env`)

## Testing/Debugging

### Verify Stack Health
```bash
netobs lab show  # List all containers + containerlab devices
```

### Common Issues
- **Nautobot not ready**: Check `netobs docker logs nautobot --tail 10 -f` for "Nautobot initialized!"
- **Permission errors**: Set `LAB_SUDO=true` in `.env`
- **Missing metrics**: Verify Prometheus targets at `http://localhost:9090/targets`
- **Docker version**: Use `docker compose` (not `docker-compose`) unless `DOCKER_COMPOSE_WITH_HASH=true`

### Trigger Test Alerts
```bash
# Flap interface to generate syslog/metrics
netobs utils device-interface-flap --device ceos-02 --interface Ethernet2

# Or SSH manually
ssh netobs@ceos-02  # Password: netobs123
> enable
# configure
# interface Ethernet2
# shutdown
```

## Code Style

- **Python**: Ruff linting (120 char line length, see `pyproject.toml`)
- **Security**: Uses `nosec` comments for subprocess calls (intentional, users run their own commands)
- **Logging**: Rich console with themed output (`console.log(..., style="info|warning|error|good")`)

## What NOT to Change
- `containerlab/lab.yml` network topology (hardcoded IPs, device names referenced throughout)
- Docker network name `network-observability` (external dependency across all scenarios)
- Credentials in `example.env` (designed for lab use, not production)
- `netobs` CLI command structure (users expect stable interface)
