# Modern Network Observability

<a href="https://www.packtpub.com/en-us/product/modern-network-observability-9781835081068"><img src="https://m.media-amazon.com/images/I/71oudvXWE4L._SL1500_.jpg" alt="" height="256px" align="right"></a>

This is the code repository for [Modern Network Observability](https://www.packtpub.com/en-us/product/modern-network-observability-9781835081068), published by Packt.

**A hands-on approach using open source tools such as Telegraf, Prometheus, and Grafana**

## What is this book about?
This book equips network professionals with the skills to monitor, analyze, and optimize network infrastructures using specific tools. With advanced techniques, you’ll learn how to build tailored observability solutions for your needs.

This book covers the following exciting features:
* Collect and normalize data from various sources using Telegraf and Logstash
* Enrich operational data with crucial context from a Source of Truth such as Nautobot
* Visualize data and create insightful dashboards with Grafana
* Automate alerts and responses for your network operations strategy using Prefect
* Understand when to build or buy an observability stack, with tips and best practices
* Explore practical machine learning techniques to enhance observability data value

If you feel this book is for you, get your [copy](https://www.amazon.com/dp/1835081061) today!

<a href="https://www.packtpub.com/?utm_source=github&utm_medium=banner&utm_campaign=GitHubBanner"><img src="https://raw.githubusercontent.com/PacktPublishing/GitHub/master/GitHub.png" 
alt="https://www.packtpub.com/" border="5" /></a>

## Instructions and Navigations

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/network-observability/network-observability-lab?quickstart=1&devcontainer_path=.devcontainer%2Fbatteries-included%2Fdevcontainer.json)

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

1. Copy the necessary environment variables to configure the components used within the lab scenarios.

  ```bash
  # Setup environment variables (edit the .env file to your liking)
  cp example.env .env
  ```

2. Install the `netobs` utility command that helps manage the entire lab environment.

  ```bash
  # Install the python dependencies
  pip install .
  ```

3. Test everything is working by deploying a lab that has most of the components configured and ready to go.

  ```bash
  # Start the network lab
  netobs lab deploy --scenario batteries-included
  ```

> NOTE: Our lab comes with a `batteries-included` setup, providing you with everything you need to get started with network observability right away. This setup includes pre-configured tools and detailed step-by-step instructions to help you explore and learn without any hassle. Head over to the [instructions](./chapters/batteries-included/README.md) section to begin!

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

---

## Lab Scenarios

The [`chapters/`](./chapters/) folder contains a collection of lab scenarios designed to help you explore modern network observability techniques using open-source tools. These scenarios are directly aligned with the chapters of the book.

Each practical chapter provides two lab scenarios:

1. **Skeleton Scenario (`ch<number>`):** This scenario includes only the bare minimum setup required to follow along with the exercises in the corresponding chapter of the book.
2. **Completed Scenario (`ch<number>-completed`):** This scenario comes fully configured, with all components set up as described in the chapter.

![Lab Components Grafana](./pics/batteries-included-grafana.png)

### Overview of Practical Chapters

Here is a brief overview of the practical chapters and the key concepts you will encounter:

- **Chapter 3 - Network Observability Data:** This chapter explores various methods and techniques to obtain operational data from network devices using popular Python libraries and other low-level tools. It covers protocols such as SNMP, gNMI, SSH CLI parsing, REST APIs, eBPF and more.

- **Chapter 5 - Data Collectors:** Building on the concepts from Chapter 3, this chapter introduces tools like Telegraf and Logstash, which are widely used in production environments to collect metrics and syslog data from network devices.

- **Chapter 6 - Data Distribution and Processing:** This chapter delves deeper into configuring Telegraf and Logstash to normalize and enrich the collected data. It also introduces the use of Message Brokers like Kafka for handling data in larger environments, with practical examples included in the lab.

- **Chapter 7 - Data Storage with Prometheus and Loki:** This chapter focuses on using Prometheus to scrape, store, and analyze normalized and enriched metrics from Telegraf. It includes practical examples of PromQL queries to extract meaningful insights from your network data. Additionally, the chapter covers Loki for log data storage and retrieval using LogQL, as well as the implementation of recording rules in both systems to optimize query performance and precompute frequent calculations.

- **Chapter 8 - Data Visualization:** This chapter centers on Grafana, demonstrating how to create panels and dashboards to visualize the data collected from the network.

- **Chapter 9 - Alerting:** This chapter dives into generating alerts with Prometheus and Loki based on the collected data. It introduces Alertmanager, which manages the routing of alerts to different destinations, including integration with [Keep](https://keephq.dev) for alert and incident management workflows.

- **Chapter 12 - Automation with Observability Data:** This chapter delves into leveraging automation tools, such as [Prefect](https://www.prefect.io/), to streamline and automate day 2 operations using your network’s observability data. It highlights how automation can enhance efficiency, reduce manual effort, and improve the reliability of ongoing network management tasks.

- **Chapter 13 - Machine Learning and AI:** This chapter explores how machine learning and AI techniques can enhance your observability practices. It covers basic forecasting, AI-driven Root Cause Analysis (RCA), and advanced anomaly detection.

- **[`Batteries Included`](./chapters/batteries-included/) Scenario:** This scenario brings everything together in a fully configured environment, offering a glimpse into the full potential of these tools. The batteries-included scenario [README](./chapters/batteries-included/README.md) provides an overview and detailed explanation of the setup, giving you a holistic view of what is achievable with this setup.


### Related products
* Automating Security Detection Engineering [[Packt]](https://www.packtpub.com/en-us/product/automating-security-detection-engineering-9781837636419) [[Amazon]](https://www.amazon.com/dp/1837636419)

* Python for Security and Networking [[Packt]](https://www.packtpub.com/en-us/product/python-for-security-and-networking-9781837637553) [[Amazon]](https://www.amazon.com/dp/1837637555)

## Get to Know the Authors
**David Flores**
throughout his career has built observability solutions for financial, retail, and managed services networks, optimizing performance across diverse environments. Currently focused on network automation with an emphasis on observability, his expertise spans Linux, Python, Docker, and Kubernetes. Passionate about education, David shares his knowledge on implementing solutions using Telegraf, Prometheus, and Grafana.

**Christian Adell**
is a network software engineer who has played multiple roles related to networking and IT automation, and currently, as Principal Architect at Network to Code, is focused on building network automation solutions for diverse use cases (including network monitoring and observability), with great emphasis on open source software.

**Josh VanDeraa**
is a 20-year networking veteran who has been doing network automation for the past 8 years. He has worked in large enterprise retail, travel, managed services, and most recently, professional services industries. He has worked on networks of all sizes, bringing multiple different network automation solutions to the table to drive real value with Python, Ansible, and Python web framework solutions.
Josh is the author of Open Source Network Management and maintains a blog site to provide additional content to those on the web.
