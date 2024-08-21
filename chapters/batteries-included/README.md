# Batteries Included Scenario

The goal of this lab scenario is to showcase a comprehensive observability stack using open-source tools. It integrates most of the configurations and system designs provided in the chapters of the book, offering a practical, hands-on environment to explore these tools in action.

## High-Level Overview

The following diagram illustrates the topology of the lab environment:

![Batteries Included Topology](./../../pics/batteries-included-lab.png)

**IMPORTANT!:** If you have followed the tutorial for setting up the [VM hosting the lab environment in DigitalOcean](./../../setup/README.md), the `batteries-included` scenario should be up and running. If not, we recommend completing the tutorial to set up the environment.

> **Note:** The environment does not have to be hosted on a DigitalOcean VM/Droplet exclusively. The tutorial is also applicable to any Debian-based Linux system. Additionally, you can run the environment in GitHub Codespaces—see the general [README](./../../README.md) for more information.

### Checking the Lab Environment

To check if the lab environment is running, use the following command:

```bash
netobs lab show
```

This command will display all the containers and Containerlab devices currently running. If none are listed, you can start the environment with:

```bash
netobs lab prepare --scenario batteries-included
```

---

## Component Overview and Interaction Guide

The following are sections for each components describing their role and how to interact with them. An important thing to highlight is that you will need to get the necessary credentials for the lab environment stored in your `.env` file. When in search of the credentials look there.

### Network Devices (`cEOS`)

The `cEOS` devices (`cEOS-01` and `cEOS-02`) are simulated network routers running in Containerlab. These devices generate metrics and logs, which are collected by the observability stack. They serve as the data sources for the lab, mimicking real-world network equipment.

#### Checking the Containerlab Topology

To view the current network topology and ensure the devices are running, use the following command:

```bash
netobs containerlab inspect

# If sudo mode is needed
netobs containerlab inspect --sudo
```

This will display a detailed overview of the Containerlab environment, including the status of the `cEOS` devices.

If is giving you an error about permissions, you might need to run the command in `sudo` mode, by either passing the command line flag or setting the environment variable `LAB_SUDO=true` in your `.env` file.

#### Logging into the Devices

You can log into the `cEOS` devices using SSH to perform network operations, such as shutting down interfaces or viewing configuration details:

```bash
# Example connecting to ceos-02 using the default netobs credentials
ssh netobs@ceos-02
```

Once logged in, you can execute standard network commands. For example, to shut down an interface:

```bash
configure
interface Ethernet2
no shutdown
```

This command shuts down the `Ethernet2` interface, which will trigger alerts and logs that can be observed through the observability stack.

#### Commands to Interact with the Devices

Here are some useful commands to interact with the `cEOS` devices:

- **Check Interface Status:**

  ```bash
  show interfaces status
  ```

- **View Logs:**

  ```bash
  show logging
  ```

- **Ping Test:** Useful to generate some lightweight traffic and check it on the dashboards

  ```bash
  ping <destination_ip> size 1400
  ```

### Nautobot

Nautobot acts as the source of truth for the network. It enriches data collected by Telegraf and Logstash with additional context, such as device metadata or topology information.

### Verifying and Populating Nautobot

Before populating Nautobot with data from your network devices, ensure that the Nautobot service is fully operational. Here are three methods to verify its readiness:

1. **Check the `nautobot` Service Health:**
   Run the following command to check the status of the `nautobot` service:

   ```bash
   netobs lab show | grep nautobot
   ```

   If the service is still starting, you will see a message indicating its health status as `(health: starting)`. For example:

   ```shell
   ❯ netobs lab show | grep nautobot
   nautobot            docker.io/networktocode/nautobot:2.2-py3.10    "/docker-entrypoint.…"   nautobot            About a minute ago   Up About a minute (health: starting)   0.0.0.0:8080->8080/tcp, :::8080->8080/tcp, 0.0.0.0:8443->8443/tcp, :::8443->8443/tcp
   ```

2. **Monitor the Meta Monitoring Dashboard:**
   The Meta Monitoring dashboard in Grafana provides an overview of the
   health of your services. Access it via `http://<lab-machine-address>:3000/dashboards`.

   If Nautobot is still starting, the dashboard will reflect this status. Here is an example of what you might see:
   ![Meta Monitoring Dashboard](./../../pics/batteries-included-grafana.png)

3. **Review the `nautobot` Logs:**
   You can follow the logs of the Nautobot container to monitor its startup process. Use the command:

   ```bash
   netobs docker logs nautobot --tail 10 --follow
   ```

   Wait until you see the message `Nautobot initialized!`, which confirms that Nautobot is ready for use.

Once Nautobot is ready, you can populate it with data from your network devices by running the following command:

```bash
netobs utils load-nautobot
```

This command will load the necessary data into Nautobot, making it fully operational and ready for use with the other components in your observability stack.

#### Accessing Nautobot

You can access Nautobot via its web interface:

```
http://<lab-machine-address>:8080
```

Login to explore network device inventories, view relationships, and check the data being fed into Grafana.

#### Enriching Data

Nautobot can be queried using its GraphQL API. For example, to enrich device data in Grafana:

```graphql
{
  devices {
    name
    site {
      name
    }
  }
}
```

This query will return device names and their corresponding sites, which can then be used to add context to your Grafana visualizations, enhancing the insights you can derive from your observability data.

### Telegraf

Telegraf is an agent used for collecting and reporting metrics. In this lab, Telegraf is configured to collect metrics from `cEOS` devices using SNMP, gNMI and SSH protocols, which it then forwards to Prometheus. The data collected from the different methods is normalized for easier dashboarding and creation of alerts.

It also performs synthetic monitoring on the devices and services of the stach using `ping` and `HTTP` probes against them.

#### Checking Telegraf Logs

To ensure that Telegraf is running correctly and collecting metrics, you can check its logs with the following command:

```bash
netobs docker logs telegraf-01 --tail 20 --follow
```

This will display real-time logs from Telegraf, helping you verify that it is successfully scraping metrics from the `cEOS` devices.

#### Viewing Prometheus Metrics

Telegraf exposes metrics that can be scraped by Prometheus. To view these metrics directly, you can see them in your browser by going to the URL `http://<lab-machine-address>:<prometheus-port>/metrics`:

```bash
# Telegraf-01 metrics endpoint
http://<lab-machine-address>:9004/metrics

# Telegraf-02 metrics endpoint
http://<lab-machine-address>:9005/metrics
```

You can check the status of the Telegraf targets and the metrics being collected by looking into Prometheus web interface `http://<lab-machine-address>:9090/targets`.

#### Running Network Commands from Inside the Telegraf Container

You may need to troubleshoot or run network commands from within the Telegraf container. To do this, use the following command:

```bash
netobs docker exec telegraf-01 sh
```

Once inside the container, you can run network commands like `ping` to test connectivity:

```bash
ping ceos-01
```

Or even open a Python terminal and run commands with [netmiko](https://github.com/ktbyers/netmiko)!.

```bash
# Open the python terminal
python
```

To test it you can use the following snippet.

```python
import netmiko
from rich.pretty import print as rprint

device = netmiko.ConnectHandler(host="ceos-02")

result = device.send_command("show version")

rprint(result)
```

#### Verifying Metrics Scraping in Prometheus

To view the Telegraf metrics scraped from Prometheus, you can access the Prometheus web interface in your browser. The URL will typically be something like:

```
http://<lab-machine-address>:9090/targets
```

Here, you can see the status of the Telegraf targets and the metrics being collected.

### Logstash

Logstash is a data processing pipeline that ingests logs from network devices and forwards them to Grafana Loki for centralized log storage and analysis. In this lab scenario, Logstash is configured to collect Syslog data from the `cEOS` devices, parse their messages with an emphasis on the interfaces `UPDOWN` events for alert generation.

#### Checking Logstash Logs

To verify that Logstash is running properly and processing logs, you can check its logs with the following command:

```bash
netobs docker logs logstash --tail 20 --follow
```

This command will display the real-time logs from Logstash, helping you ensure that it is correctly receiving by showing its output in a `rubydebug` format.

#### Verifying Log Ingestion in Loki

Once Logstash is confirmed to be running, you can verify that logs are being ingested into Grafana Loki. Access the Loki targets via the Grafana web interface:

```
http://<lab-machine-address>:3000/explore
```

In the **Explore** section, select **Loki** as the data source and use the following LogQL query to check for recent logs:

```logql
{collector="logstash"}
```

This query will display all logs processed by Logstash, allowing you to validate that the pipeline is functioning as expected.

### Prometheus

Prometheus is a time-series database used to scrape, store, and query metrics. In this lab, Prometheus collects metrics from Telegraf, allowing you to analyze network performance and trends.

#### Checking Prometheus Status

To check the status of Prometheus and its targets, you can visit the Prometheus web interface:

```
http://<lab-machine-address>:9090/targets
```

This page will show you all the active targets, including Telegraf, and whether Prometheus is successfully scraping them.

#### Querying Metrics with PromQL

PromQL is the query language used by Prometheus to retrieve metrics. You can access the Prometheus query interface through:

```
http://<lab-machine-address>:9090/graph
```

Example query to check network interface metrics:

```promql
rate(interface_in_octets{device="ceos-02"}[5m])
```

This query will show the rate of traffic flowing through interfaces, averaged over the last 5 minutes.

### Grafana

Grafana is the visualization layer of the observability stack. It is used to create dashboards that display metrics collected by Prometheus and logs from Loki.

#### Accessing Grafana

To access Grafana, open your web browser and go to:

```
http://<lab-machine-address>:3000
```

Login with the default credentials (usually `admin/admin`) and explore the pre-built dashboards. These dashboards are connected to Prometheus and Loki, providing real-time insights into network performance and events.

#### Creating a Custom Dashboard

To create a custom dashboard:

1. Click on **Create** > **Dashboard**.
2. Add a new panel, and select **Prometheus** as the data source.
3. Use PromQL to query specific metrics and visualize them.

For example, you could create a panel to show CPU usage across your `cEOS` devices.

### Alertmanager

Alertmanager is responsible for managing alerts generated by Prometheus. It routes these alerts to various destinations based on predefined rules.

#### Checking Alertmanager Status

You can check the status and configuration of Alertmanager by accessing:

```
http://<alertmanager_ip>:9093
```

This interface allows you to view active alerts, silence them, or check the routing rules.

#### Configuring Alerts

To add or modify alerting rules, you can edit the Prometheus configuration file:

```yaml
groups:
  - name: Network Alerts
    rules:
    - alert: HighCPUUsage
      expr: avg(rate(node_cpu_seconds_total{mode!="idle"}[5m])) > 0.8
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "High CPU Usage Detected"
        description: "The average CPU usage is over 80% for more than 5 minutes."
```

Reload Prometheus to apply the new rules.

### Prefect

Prefect is used for automating workflows based on the observability data collected. It can trigger jobs or actions in response to specific events or conditions.

#### Accessing Prefect

Prefect’s UI can be accessed via:

```
http://<prefect_ip>:8080
```

Here, you can create and manage workflows, monitor task status, and review logs.

### Example Workflow
An example workflow could be:

- Automatically generate a network report if Prometheus detects an anomaly.
- Trigger remediation scripts on `cEOS` devices when an interface goes down.

To create a new workflow, use the Prefect UI or define it in code with the Prefect Python API.
