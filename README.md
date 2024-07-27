[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/network-observability/network-observability-lab?quickstart=1&devcontainer_path=.devcontainer%2Fbatteries-included%2Fdevcontainer.json)
# Network Observability Lab

This repository contains the resources for building and managing an observability stack within a network lab environment, specifically designed for the "Modern Network Observability" book. It includes scripts, configuration files, and documentation to set up and operate various observability tools like Prometheus, Grafana Loki, and others, helping you implement and learn about network observability practices in a practical, hands-on manner.

![Modern Network Observability](/pics/netobs-observability.png)

The repository includes all the lab scenarios from the book, which progressively cover topics from metrics and logs collection all the way to leveraging AI for improving observability practices. More specifically:

- **Data Collection Methods (Chapter 3)**: Learn different ways to gather network data, like using SNMP and gNMI.
- **Metrics and Logs Collection (Chapter 5)**: Collect important metrics and logs from network devices with tools like Telegraf and Logstash.
- **Data Normalization, Enrichment, and Distribution (Chapter 6)**: Transform raw data into useful formats and share it across systems.
- **Storage and Querying with PromQL and LogQL (Chapter 7)**: Store data and use powerful query languages to search through metrics and logs.
- **Visualization (Chapter 8)**: Create dashboards and reports to make data easy to understand using Grafana.
- **Alerting (Chapter 9)**: Set up alerts to monitor and quickly respond to network problems.
- **Scripts and Event-Driven Automation with Observability Events and Data (Chapter 12)**: Automate reports and actions based on data developing scripts, CLI tools and using event-driven systems.
- **AI for Enhanced Observability (Chapter 13)**: Use AI to predict problems, find anomalies, and improve network management.

---

## Requirements

The lab environments are designed to set up a small network and an attached observability stack. Developed and tested on Debian-based systems, we provide **[setup](setup/README.md) documentation to guide** you through automatic setup on a DigitalOcean droplet. This process will provision, install dependencies, and configure the environment automatically. But if you want to host the lab environment, ensure the following:

- `docker` installed (version `26.1.1` or above)
- `containerlab` for the network lab (version `0.54.2` or above)
- `netobs` for managing the network lab and observability stack (installed with this repository, more details later)
- Arista `cEOS` images for the `containerlab` environment. You can open an account and download them at [arista.com](https://www.arista.com)

For detailed setup instructions, please refer to the [setup README](./setup/README.md). It provides a comprehensive guide on installing the lab environment on a DigitalOcean Droplet.

### Prepare cEOS image

After downloading the image, use the following command to import them as Docker images:

```bash
# Import cEOS images as Docker images
docker import <path-to-image>/cEOS64-lab-<version>.tar.xz ceos:image
```

## Quickstart

To get started with the network lab and observability stack, you need to:

1. Copy the necessary environment variables to configure the components used withing the lab scenarios.

```bash
# Setup environment variables (edit the .env file to your liking)
cp example.env .env
```

2. Install the `netobs` utility command that helps manage the entire lab environment.

```bash
# Install the python dependencies
pip install .
```

3. Test everything is working by deploying lab that hast most of the components configured and ready to go.

```bash
# Start the network lab
netobs lab deploy --scenario batteries-included
```

---

## Managing Lab Environment with `netobs`

The `netobs` utility tool simplifies managing and monitoring the network lab and observability stack set up within this repository. It provides a suite of commands designed to streamline various tasks associated with your network infrastructure.

### Top-Level Commands

The `netobs` utility includes five main commands to help manage the environment:

- **`netobs setup`**: Manages the overall setup of a remote DigitalOcean droplet hosting this repository and its lab environment. This command simplifies the process of preparing a hosting environment for users.

- **`netobs containerlab`**: Manages the `containerlab` pre-configured setup. All lab scenarios presented in the chapters operate under this network lab configuration.

- **`netobs docker`**: Manages the Docker Compose setups for each lab scenario. It ensures the appropriate containers are running for each specific lab exercise.

- **`netobs lab`**: A wrapper utility that combines `netobs containerlab` and various `netobs docker` commands to perform major actions. For example:
  - `netobs lab purge`: Cleans up all running environments.
  - `netobs lab prepare --scenario ch7`: Purges any scenario that is up and prepares the environment for Chapter 7.

- **`netobs utils`**: Contains utility commands for interacting with the lab environment. This includes scripts for enabling/disabling an interface on a network device to simulate interface flapping and other useful actions.

### Example Usage

For instance, the `netobs lab deploy` command builds and starts a `containerlab` environment along with the observability stack. This command sets up the entire lab scenario, ensuring that all necessary components are up and running.

```bash
# Start the network lab
❯ netobs lab deploy batteries-included --sudo
[21:50:42] Deploying lab environment
           Network create: network-observability
           Running command: docker network create --driver=bridge  --subnet=198.51.100.0/24 network-observability
           Successfully ran: network create
─────────────────────────────────────────────────── End of task: network create ────────────────────────────────────────────────────

           Deploying containerlab topology
           Topology file: containerlab/lab.yml
           Running command: sudo containerlab deploy -t containerlab/lab.yml
INFO[0000] Creating container: "ceos-01"
INFO[0000] Creating container: "ceos-02"
INFO[0001] Creating virtual wire: ceos-01:eth2 <--> ceos-02:eth2
INFO[0001] Creating virtual wire: ceos-01:eth1 <--> ceos-02:eth1
+---+---------+--------------+----------------+------+---------+------------------+--------------+
| # |  Name   | Container ID |     Image      | Kind |  State  |   IPv4 Address   | IPv6 Address |
+---+---------+--------------+----------------+------+---------+------------------+--------------+
| 1 | ceos-01 | d59629fbbdc0 | ceos:4.28.5.1M | ceos | running | 198.51.100.11/24 | N/A          |
| 2 | ceos-02 | 80854bfd7e08 | ceos:4.28.5.1M | ceos | running | 198.51.100.12/24 | N/A          |
+---+---------+--------------+----------------+------+---------+------------------+--------------+
[21:51:14] Successfully ran: Deploying containerlab topology
─────────────────────────────────────────── End of task: Deploying containerlab topology ───────────────────────────────────────────

           Running command: docker compose --project-name netobs -f chapters/docker-compose.yml --verbose up -d --remove-orphans
[+] Building 0.0s (0/0)
[+] Running 10/10
 ✔ Volume "netobs_grafana-01_data"     Created                                                                                 0.0s
 ✔ Volume "netobs_prometheus-01_data"  Created                                                                                 0.0s
 ✔ Container netobs-grafana-01-1       Started                                                                                 0.7s
 ✔ Container netobs-prometheus-01-1    Started                                                                                 1.3s
 ✔ Container netobs-telegraf-02-1      Started                                                                                 1.0s
[21:51:16] Successfully ran: start stack
───────────────────────────────────────────────────── End of task: start stack ─────────────────────────────────────────────────────
```
