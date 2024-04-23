import os
import time
import datetime

import requests
import typer
from prometheus_api_client import PrometheusConnect
from rich.console import Console
from rich.theme import Theme
from rich.table import Table
from rich.live import Live

app = typer.Typer(name="observer", no_args_is_help=True, add_completion=False)

console = Console(theme=Theme({"info": "cyan", "warning": "bold magenta", "error": "bold red", "good": "bold green"}))

BGP_STATES = {
    1: "Established",
    2: "Idle",
    3: "Connect",
    4: "Active",
    5: "OpenSent",
    6: "OpenConfirmed",
}


def sizeof_fmt(num, suffix="bps") -> str:
    """Convert a number to a human-readable format.

    Args:
        num (int): The number to convert.
        suffix (str): The suffix to add to the number.

    Returns:
        str: The human-readable number.
    """
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1000.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1000.0
    return f"{num:.1f}Y{suffix}"


def retrieve_data_prometheus(query: str, url: str = "http://localhost:9090") -> list[dict]:
    """Collect metrics from Prometheus.

    Args:
        query (str): The Prometheus query to execute.

    Returns:
        list[dict]: The Prometheus query result.
    """
    prom = PrometheusConnect(url=url, disable_ssl=True)
    results = prom.custom_query(query=query)
    if not results:
        console.log(f"No results returned for query: {query}", style="error")
        raise typer.Exit(1)

    return results


def retrieve_data_loki(query: str, start_timestamp: int, end_time: int) -> dict:
    """Retrieve data from Grafana Loki.

    Args:
        query (str): Loki query
        start_timestamp (int): Start timestamp
        end_time (int): End timestamp

    Returns:
        dict: Loki query result
    """
    response = requests.get(
        url=f"http://localhost:3001/loki/api/v1/query_range",
        params={
            "query": query,
            "start": int(start_timestamp),
            "end": int(end_time),
            "limit": 1000,
        },
    )
    return response.json()["data"]["result"]


def retrieve_device_info(device: str) -> dict:
    """Retrieve device information from Nautobot.

    Args:
        device (str): The device name.

    Returns:
        dict: The device information.
    """
    gql = """
    query($device: [String]) {
        devices(name: $device) {
            device_type {
                model
                manufacturer {
                    name
                }
            }
        }
    }
    """
    token = os.getenv("NAUTOBOT_TOKEN")
    if not token:
        console.log("NAUTOBOT_TOKEN environment variable not set", style="error")
        raise typer.Exit(1)

    response = requests.post(
        url="http://localhost:8080/api/graphql/",
        headers={"Authorization": f"Token {token}"},
        json={"query": gql, "variables": {"device": device}},
    )
    response.raise_for_status()
    return response.json()["data"]["devices"][0]


def gen_intf_traffic_table(device: str, threshold: float) -> Table:
    """Generate a table with the interfaces with traffic higher than the threshold.

    Args:
        device (str): The device name.
        threshold (float): The traffic threshold.

    Returns:
        Table: The table with the interfaces with traffic higher than the threshold.
    """
    query = f'rate(interface_in_octets{{device=~"{device}"}}[2m])*8 > {threshold}'

    # Collect metrics
    metrics = retrieve_data_prometheus(query)

    table = Table(title="High Bandwidth Links", show_lines=True)
    table.add_column("Device")
    table.add_column("Interface")
    table.add_column("Traffic IN", justify="right", style="green")

    # Build the table with the results
    for metric in metrics:
        interface = metric["metric"]["name"]
        traffic = sizeof_fmt(float(metric["value"][-1]))
        table.add_row(device, interface, traffic)
    return table


@app.command()
def high_bw_links(device: str, threshold: float = 1000.0, watch: bool = False):
    """Get the links with bandwidth higher than the threshold.

    Example:

        > python observer.py high-bw-links --device ceos-01 --threshold 1000
    """
    console.log("Getting links with Bandwidth higher than threshold", style="info")

    # Generate and watch the interface traffic table for about a minute
    if watch is True:
        with Live(gen_intf_traffic_table(device, threshold), refresh_per_second=4, screen=True) as live:
            for _ in range(60):
                time.sleep(1)
                live.update(gen_intf_traffic_table(device, threshold), refresh=True)
        return

    # Generate the table and print it
    else:
        table = gen_intf_traffic_table(device, threshold)

        # Print the table
        console.print(table)


@app.command()
def site_health(site: str):
    """Retrieves and displays health information for devices in a specific site.

    Example:

        > python observer.py site-health --site "lab-site-01"
    """
    console.log(f"Getting site [orange2 i]{site}[/] health", style="info")
    # Placeholder for the devices information
    devices = {}

    # Collect the device uptime and set a placeholder for BGP information
    query = f"device_uptime{{site=~'{site}'}}"
    metrics = retrieve_data_prometheus(query)
    for metric in metrics:
        # Convert time ticks to human readable format
        time_ticks = int(metric["value"][-1]) / 100
        uptime = str(datetime.timedelta(seconds=time_ticks))

        # Store the device uptime and take the milliseconds off
        device_name = metric["metric"]["device"]
        devices[device_name] = {"uptime": ":".join(str(uptime).split(":")[:2])}

    # Ping response (latency) for each device
    query = f"ping_average_response_ms{{site=~'{site}'}}"
    metrics = retrieve_data_prometheus(query)
    for metric in metrics:

        # Store the device's latency
        device_name = metric["metric"]["device"]
        devices[device_name]["latency"] = f"{metric['value'][-1]} ms"

    # Avg CPU and Memory usage
    query = f"avg by (device) (cpu_used{{site=~'{site}'}})"
    metrics = retrieve_data_prometheus(query)
    for metric in metrics:

        # Store the device's CPU usage
        device_name = metric["metric"]["device"]
        devices[device_name]["cpu"] = f"{metric['value'][-1]}%"

    query = f"avg by (device) (memory_used{{site=~'{site}'}})"
    metrics = retrieve_data_prometheus(query)
    for metric in metrics:

        # Store the device's Memory usage
        device_name = metric["metric"]["device"]
        devices[device_name]["memory"] = sizeof_fmt(float(metric["value"][-1]), suffix="B")

    # Overall BW usage
    query = f"""
        sum by (device) (
            rate(interface_in_octets{{site=~'{site}'}}[2m])*8 +
            rate(interface_out_octets{{site=~'{site}'}}[2m])*8
        )
    """
    metrics = retrieve_data_prometheus(query)
    for metric in metrics:

        # Store the device's bandwidth usage
        device_name = metric["metric"]["device"]
        devices[device_name]["bandwidth"] = sizeof_fmt(float(metric["value"][-1]))

    # BGP state for each device in a site
    query = f"bgp_neighbor_state{{site=~'{site}'}}"
    metrics = retrieve_data_prometheus(query)
    for metric in metrics:

        # Create BGP state lists for each device
        device_name = metric["metric"]["device"]
        if "bgp" not in devices[device_name]:
            devices[device_name]["bgp"] = {"up": [], "down": []}

        # Store the device's BGP state
        state = BGP_STATES[int(metric["value"][-1])]
        if state == "Established":
            devices[device_name]["bgp"]["up"].append(state)
        else:
            devices[device_name]["bgp"]["down"].append(state)

    # Device Manufacturer and Model from Nautobot
    for device in devices.keys():

        # Get the device manufacturer and model from Nautobot
        device_info = retrieve_device_info(device)

        # Store the device's manufacturer and model
        devices[device]["manufacturer"] = device_info["device_type"]["manufacturer"]["name"]
        devices[device]["model"] = device_info["device_type"]["model"]

    # Create initial table of the site health
    table = Table(title=f"Site Health: {site}", show_lines=True)
    table.add_column("Device")
    table.add_column("Manufacturer")
    table.add_column("Model")
    table.add_column("Uptime")
    table.add_column("Latency")
    table.add_column("CPU")
    table.add_column("Memory")
    table.add_column("Bandwidth")
    table.add_column("BGP State")

    # Build the table with the results
    for device, data in devices.items():

        # Count the number of BGP states and color them
        up_bgp = f"[green]{len(data['bgp']['up'])}[/]"
        down_bgp = f"[red]{len(data['bgp']['down'])}[/]"

        # Add the row to the table
        table.add_row(
            device,
            data["manufacturer"],
            data["model"],
            data["uptime"],
            data["latency"],
            data["cpu"],
            data["memory"],
            data["bandwidth"],
            f"{up_bgp} UP, {down_bgp} DOWN",
        )

    # Print the table
    console.print(table)

    # Now lets collect the logs for the site in the last 15 minutes
    log_results = []
    for device in devices.keys():

        # Create the Loki query filtering by device
        query = f'{{device=~"{device}"}}'

        # Set the start and end time for the query based on the current time and 15 minutes ago
        now = datetime.datetime.now()
        start_timestamp = datetime.datetime.timestamp(now - datetime.timedelta(minutes=15))
        end_time = datetime.datetime.timestamp(now)

        # Retrieve the logs
        loki_results = retrieve_data_loki(query, start_timestamp, end_time)  # type: ignore

        # Add the first 4 logs to the results
        log_results.extend(loki_results[:4])

    # Print the logs
    table = Table(title="Logs", show_lines=True)
    table.add_column("Device")
    table.add_column("Time")
    table.add_column("Message")

    for log in log_results:
        # Extract the logs information
        labels = log["stream"]
        log_time = log["values"][0][0]
        log_message = log["values"][0][1].strip()

        # Extract the log time and make it human readable
        log_time_fmt = datetime.datetime.fromtimestamp(float(log_time) / 1000000000).strftime("%Y-%m-%d %H:%M:%S")

        # Extract the log message and color it
        if labels["vendor_facility_process"] == "OSPF_ADJACENCY_ESTABLISHED":
            log_message = f"[green i]{log_message}[/]".replace("established", "[bold]established[/]")
        elif labels["vendor_facility_process"] == "OSPF_ADJACENCY_TEARDOWN":
            log_message = f"[red]{log_message}[/]"

        # Add the row to the table
        table.add_row(labels["device"], log_time_fmt, log_message)

    # Print the table
    console.print(table)


if __name__ == "__main__":
    app()
