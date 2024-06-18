# Notes for Chapter 10

The first major solution when looking at simplifying the complexities that come along with the open source solutions such as Telegraf is the use of templating their configuration and deployment. This is where Infrastructure as Code tools like [Ansible](https://www.ansible.com/), and [Terraform](https://www.terraform.io/) or even some templating scripts can help by  out the complicated pieces and simplifying the Telegraf configuration generation problem.

Ansible Environment
We are going to use the code in ch10 examples<INSERT THE FOLDER> to establish the Ansible environment.

> NOTE: There are many great resources on getting started with Ansible. Especially for how Ansible will be used in this example.  If you are not familiar with Ansible take a look Learning Ansible (https://www.packtpub.com/product/learn-ansible/9781788998758) and Ansible Playbook Essentials (https://www.packtpub.com/product/ansible-playbook-essentials/9781784398293) for further reading.

```no-highlight
$ tree
.
├── ansible_generate_configs.yml
├── inventory.ini
├── outputs
│   ├── ceos-01.conf
│   └── ceos-02.conf
└── templates
    ├── gnmi.j2
    ├── net_response.j2
    ├── output_file.j2
    ├── output_prometheus.j2
    ├── snmp_conf.j2
    └── telegraf.conf.j2

3 directories, 10 files
```

> There are many great resources on getting started with Ansible. Especially for how Ansible will be used in this example. The getting started is to create a new Python virtual environment, with either Poetry or just a standard Python Virtual Environment. Then pip install ansible. You will be on your way.

The table below outlines the purpose of each of the files within the output.


| File Name | Purpose | Notes |
| --------- | ------- | ----- |
| ansible_generate_configs.yml | Ansible Playbook (this is where the logic lives) | This is where some of the variables are stored for the entire organization. <br>This file also is the logic for executing the generation of content from the template files. This could be replaced with a Python application as well. |
| inventory.ini | Ansible Inventory (this is where the devices to targeted are defined) | In this example, the file also holds device-specific variables. <br>
The inventory can be statically defined or generated dynamically from an external inventory system |
| outputs/ | Directory where the outputs will be stored | |
| templates/ | Directory for all of the template content to be rendered by Ansible. | |
| templates/gnmi.j2 | Telegraf gNMI input plugin configuration template. | |
| templates/net_response.j2 | Telegraf Net Response input plugin configuration template. | |
| templates/output_file.j2 | Telegraf File Output plugin configuration template. | |
| templates/output_prometheus.j2 | Telegraf Prometheus Output plugin configuration template. | |
| templates/snmp_conf.j2 | Telegraf SNMP input plugin configuration template. | |
| templates/telegraf.conf.j2 | Base Telegraf configuration template | This is the entry point to the entire configuration template which includes the others |

> Note, that this is a good way to get experience with Ansible and the templating capabilities. This example shortcuts the usage of a Source of Truth where variable data should be gathered from. The variables in this example are in the inventory and play definition. But these SHOULD be gathered from the source of truth as part of the first play task. Not in the inventory or play.

The getting started is to create a new Python virtual environment, with either Poetry or just a standard Python Virtual Environment. Then, pip install ansible. You will be on your way.

## Ansible Inventory
The ansible inventory is a place where we define the targeted Telegraf instances we want to orchestrate. Here is an example of a standard Ansible inventory file that holds the target information, alongside variables that can then later be used in their orchestration

```
[telegraf_hosts]
ceos-01 use_gnmi=False use_snmp_interfaces=True prom_port=9004
ceos-02 use_gnmi=True use_snmp_interfaces=False gnmi_port=50051 prom_port=9005
```

## Ansible Playbook - Templating Telegraf Configurations

The following Ansible playbook is an example of how it can read the inventory file of the telegraf instances and use its tasks and variables to generate their configuration..

```yaml
---
- name: "ANSIBLE PLAY TO GENERATE TELEGRAF CONFIGS"
  hosts: telegraf_hosts  # Telegraf instances from inventory.ini
  connection: local
  gather_facts: no
  vars:
    # Variables used to render the configuration file
    snmp_version: "2"
    snmp_community: "public"
    snmp_interval: "60s"
    snmp_timeout: "10s"
    snmp_retries: "3"
    use_net_response: true
    use_output_file: true
    use_output_prometheus: true
  tasks:
    - name: "GENERATE TELEGRAF CONFIGS"
      ansible.builtin.template: # Ansible module that uses Jinja2 to render files from a template
        src: "telegraf.conf.j2"  # Telegraf Jinja2 template
        dest: "outputs/{{ inventory_hostname }}.conf"  # Telegraf resulting configs destination
        trim_blocks: "no"

```

The tasks include a single task, which is using the Ansible built-in module of template. The template module takes a src parameter of what the source file name is, the dest that indicates where to send the file to. In this case that is going into the outputs directory, using the inventory hostname (ceos-01, ceos-02) as a base file name. You see Jinja2 template language here with the double curly braces indicating that this is a templated section inside, with the variable defined without any string indicators. Then the files end in .conf. Ansible uses the inventory to run the tasks on each.

The `trim_blocks` parameter is something that we are using in this playbook to help with the formatting of the template files. This helps to have the appropriate white space when making calls to additional template files.

This playbook will create the necessary telegraf configurations.

## Templating Configuration
The first file, which is referenced in the Ansible Playbook file, is the telegraf.conf.j2 file. One may expect to have all of the configuration templated out, however, this breaks the parts of the configuration into individual files. This will allow for more granular changes and enable more speed and agility when it comes to working with the template. The one piece that is configuration in this first file is the [agent] information.

```
[agent]
  hostname = "{{ inventory_hostname }}"

{% if use_net_response is defined and use_net_response -%}
{% include 'net_response.j2' %}
{%- endif %}

{% if use_snmp_interfaces is defined and use_snmp_interfaces -%}
{% include 'snmp_conf.j2' %}
{%- endif %}

{% if use_gnmi is defined and use_gnmi -%}
{% include 'gnmi.j2' %}
{%- endif %}

{% if use_output_file is defined and use_output_file -%}
{% include 'output_file.j2' %}
{%- endif %}

{% if use_output_prometheus is defined and use_output_prometheus -%}
{% include 'output_prometheus.j2' %}
{%- endif %}

```

The rest of the sections make callouts to other component configurations. First, in the if statements are a check to see if the variable is defined. If it is not defined, then there will be a syntax error at this point. The second part of the if statements is a boolean check. As the template is processed by the Jinja2 templating engine, it will combine each of the components. Which will then result in a singular output file. Let’s take a look at each of the individual files.

Below is the net_response.j2 file. This is pretty short, and there is not a new line at the end. All of the line spacing between plugins is being handled within the telegraf.conf.j2 file. The only variable in this file is the inventory_hostname to use the DNS entry to get to the Docker container. If you had IP addresses inside the inventory in the ansible_host section, this may be where you would swap out inventory_hostname for ansible_host.

```
[[inputs.net_response]]
  protocol = "tcp"
  address = "{{ inventory_hostname }}"
```

Onto the second file is the SNMP configuration. In the inventory, only ceos-01 has SNMP enabled. So this will only be processed for that particular device. You will also notice a bunch of other variables as well in this set up from the play scoped level variables.

```
[[inputs.snmp]]
  agents = ["{{ inventory_hostname }}"]
  version = {{ snmp_version }}
  community = "{{ snmp_community }}"
  interval = "{{ snmp_interval }}"
  timeout = "{{ snmp_timeout }}"
  retries = "{{ snmp_retries }}"

  [[inputs.snmp.field]]
    # Overriding the name of the metric collected to "uptime"
    name = "uptime"
    # SNMP OID
    oid = "RFC1213-MIB::sysUpTime.0"

  # Example of SNMP Walk operation
  [[inputs.snmp.table]]
    # Name of the metrics collected
    name = "interface"


  # Example of retrieving an specific field from the table
  [[inputs.snmp.table.field]]
    # Overriding the name of this field
    name = "name"
    # SNMP OID which has the Interface Name
    oid = "IF-MIB::ifDescr"
    # Flag that signal to use this as a tag instead of a metric value
    is_tag = true

    # By default the plugin is collecting all the metrics from the table walk
  # but in this case we are selecting some specific fields to showcase in the book
  [[inputs.snmp.table.field]]
    name = "in_octets"
    oid = "IF-MIB::ifHCInOctets"

  [[inputs.snmp.table.field]]
    name = "out_octets"
```

The gNMI plugin is next in the processed list and this time the controls are swapped, in that this will be processed for ceos-02 instead of ceos-01. And note that there continues to be the environment variable configuration in this file. These are still controlled by the Telegraf environment variables, and not processed through the Ansible Playbook.

```
[[inputs.gnmi]]
  # Targets for gNMI plugin - we are using port 50051 as is the port configured for gNMI in the cEOS devices
  addresses = ["{{ inventory_hostname }}:{{ gnmi_port}}"]
  # Creds to connect to the device
  username = "${NETWORK_AGENT_USER}"
  password = "${NETWORK_AGENT_PASSWORD}"
  # Retries in case of failure
  redial = "20s"


[[inputs.gnmi.subscription]]
  # Name of the resulting metric namespace
  name = "interface"
  # Specific YANG path for interface counters
  path = "/interfaces/interface/state/counters"
  # gNMI subscription mode ("target_defined", "sample", "on_change")
  subscription_mode = "sample"
  # Interval to send each sample
  sample_interval = "10s"


[[inputs.gnmi.subscription]]
  name = "interface"
  # Specific path to collect interface oper-status
  path = "/interfaces/interface/state/oper-status"
  subscription_mode = "sample"
  sample_interval = "10s"

```

The rest of the files can be found on the GitHub repository for reference. The final output of the files once processed for each of the items looks like the following for ceos-01.conf:

```
[agent]
  hostname = "ceos-01"

[[inputs.net_response]]
  protocol = "tcp"
  address = "ceos-01"

[[inputs.snmp]]
  agents = ["ceos-01"]
  version = 2
  community = "public"
  interval = "60s"
  timeout = "10s"
  retries = "3"

  [[inputs.snmp.field]]
    # Overriding the name of the metric collected to "uptime"
    name = "uptime"
    # SNMP OID
    oid = "RFC1213-MIB::sysUpTime.0"

  # Example of SNMP Walk operation
  [[inputs.snmp.table]]
    # Name of the metrics collected
    name = "interface"


  # Example of retrieving an specific field from the table
  [[inputs.snmp.table.field]]
    # Overriding the name of this field
    name = "name"
    # SNMP OID which has the Interface Name
    oid = "IF-MIB::ifDescr"
    # Flag that signal to use this as a tag instead of a metric value
    is_tag = true

    # By default the plugin is collecting all the metrics from the table walk
  # but in this case we are selecting some specific fields to showcase in the book
  [[inputs.snmp.table.field]]
    name = "in_octets"
    oid = "IF-MIB::ifHCInOctets"

  [[inputs.snmp.table.field]]
    name = "out_octets"



[[outputs.file]]
  files = ["stdout"]

[[outputs.prometheus_client]]
  listen = ":9004"
  metric_version = 2

And the rendered configuration for ceos-02.conf:

[agent]
  hostname = "ceos-02"

[[inputs.net_response]]
  protocol = "tcp"
  address = "ceos-02"



[[inputs.gnmi]]
  # Targets for gNMI plugin - we are using port 50051 as is the port configured for gNMI in the cEOS devices
  addresses = ["ceos-02:50051"]
  # Creds to connect to the device
  username = "${NETWORK_AGENT_USER}"
  password = "${NETWORK_AGENT_PASSWORD}"
  # Retries in case of failure
  redial = "20s"


[[inputs.gnmi.subscription]]
  # Name of the resulting metric namespace
  name = "interface"
  # Specific YANG path for interface counters
  path = "/interfaces/interface/state/counters"
  # gNMI subscription mode ("target_defined", "sample", "on_change")
  subscription_mode = "sample"
  # Interval to send each sample
  sample_interval = "10s"


[[inputs.gnmi.subscription]]
  name = "interface"
  # Specific path to collect interface oper-status
  path = "/interfaces/interface/state/oper-status"
  subscription_mode = "sample"
  sample_interval = "10s"

[[outputs.file]]
  files = ["stdout"]

[[outputs.prometheus_client]]
  listen = ":9005"
  metric_version = 2

```

Each file is rendered through a single execution. Now you are able to work with the configuration files.
Orchestrating Files
Once the configuration files are completed, the next step is to get the files into the proper location where Telegraf will read them. There are several methods to orchestrate the Telegraf application and how the configurations are loaded. The goal is to get the appropriate instances of the application, whether running natively on a virtual machine or in a container orchestration system such as Kubernetes.

To keep things simpler, we continue with Ansible as a simple orchestrator either Docker containers or a Linux systemd process that would maintain the application. Let’s take a look at how you may use Ansible to automate the execution of Docker containers.

Let’s take a look at the template file that was added now, templates/docker-compose.yml.j2. We just show the section between the Grafana definition and the Logstash definition from the materials on GitHub.

```
      - network-observability <... From Grafana definition ...>
{% for inventory_host in vars['groups']['telegraf_hosts'] %}
  telegraf-{{ inventory_host }}:
    build:
      dockerfile: "./configs/telegraf/telegraf.Dockerfile"
    command: telegraf --config /etc/telegraf/telegraf.conf
    tty: true
    volumes:
      - ./outputs/{{ inventory_host }}.conf:/etc/telegraf/telegraf.conf
    ports:
      - {{ vars['hostvars'][inventory_host]['prom_port'] }}:{{ vars['hostvars'][inventory_host]['prom_port']}}
    env_file:
      - ../../.env
    networks:
      - network-observability

{% endfor %}
  logstash: <... Continued logstash definition ...>
```

With the for loop in the Jinja2 template, you get the docker-compose for all of the devices defined in the inventory, so docker-compose will spin up a Telegraf instance for each target device from the inventory.
