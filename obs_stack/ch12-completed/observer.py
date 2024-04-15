import os
import time
import datetime
from typing import Generator

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


def get_prometheus_client(url: str = "http://localhost:9090") -> PrometheusConnect:
    """Create a Prometheus API client.

    Args:
        url (str): The URL of the Prometheus server.

    Returns:
        PrometheusConnect: The Prometheus API client.
    """
    return PrometheusConnect(url=url, disable_ssl=True)


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
    return f"{num:.1f}Yi{suffix}"


def collect_metrics(query: str) -> Generator[tuple, None, None]:
    """Collect metrics from Prometheus.

    Args:
        query (str): The Prometheus query to execute.

    Yields:
        tuple: A tuple containing the device and the value.
    """
    prom = get_prometheus_client()
    results = prom.custom_query(query=query)
    if not results:
        console.log(f"No results returned for query: {query}", style="error")
        raise typer.Exit(1)

    for metric in results:
        labels = metric["metric"]
        value = metric["value"][-1]
        yield labels, value


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
    response = requests.post(
        url="http://localhost:8080/api/graphql/",
        headers={"Authorization": f"Token {os.getenv('NAUTOBOT_SUPERUSER_API_TOKEN')}"},
        json={"query": gql, "variables": {"device": device}},
    )
    response.raise_for_status()
    return response.json()["data"]["devices"][0]


def gen_intf_traffic_table(device: str, threshold: float) -> Table:
    query = f'rate(interface_in_octets{{device=~"{device}"}}[2m])*8 > {threshold}'

    # Collect metrics by device
    metrics = collect_metrics(query)

    table = Table(title="High Bandwidth Links", show_lines=True)
    table.add_column("Device")
    table.add_column("Interface")
    table.add_column("Traffic IN", justify="right", style="green")

    # Build the table with the results
    for labels, value in metrics:
        _interface = labels["name"]
        _traffic = sizeof_fmt(float(value))
        table.add_row(device, _interface, _traffic)
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
    console.log(f"Getting site [orange2 i]{site}[/] health", style="info")
    # Placeholder for the devices information
    devices = {}

    # Collect the device uptime and set a placeholder for BGP information
    query = f"device_uptime{{site=~'{site}'}}"
    for labels, value in collect_metrics(query):
        # Convert time ticks to human readable format
        _uptime = str(datetime.timedelta(seconds=int(value) / 100))

        # Store the device uptime and take the milliseconds off
        devices[labels["device"]] = {"uptime": ":".join(str(_uptime).split(":")[:2])}

        # Set a placeholder for BGP information
        devices[labels["device"]]["bgp"] = {"up": [], "down": []}

    # Now lets collect the ping response (latency) for each device
    query = f"avg by (device) (ping_average_response_ms{{site=~'{site}'}})"
    for labels, value in collect_metrics(query):
        devices[labels["device"]]["latency"] = f"{value}ms"

    # Now lets collect avg CPU and Memory usage
    query = f"avg by (device) (cpu_used{{site=~'{site}'}})"
    for labels, value in collect_metrics(query):
        devices[labels["device"]]["cpu"] = f"{value}%"

    query = f"avg by (device) (memory_used{{site=~'{site}'}})"
    for labels, value in collect_metrics(query):
        devices[labels["device"]]["memory"] = sizeof_fmt(float(value), suffix="B")

    # Now lets collect the overall BW usage
    query = f"""
        sum by (device) (
            rate(interface_in_octets{{site=~'{site}'}}[2m])*8 +
            rate(interface_out_octets{{site=~'{site}'}}[2m])*8
        )
    """
    for labels, value in collect_metrics(query):
        devices[labels["device"]]["bandwidth"] = sizeof_fmt(float(value))

    # Nows lets collect the BGP state for each device in a site
    query = f"bgp_neighbor_state{{site=~'{site}'}}"
    for labels, value in collect_metrics(query):
        _state = BGP_STATES[int(value)]
        if _state == "Established":
            devices[labels["device"]]["bgp"]["up"].append(_state)
        else:
            devices[labels["device"]]["bgp"]["down"].append(_state)

    # Now get the Device Manufacturer and Model from Nautobot
    for device in devices.keys():
        device_info = retrieve_device_info(device)
        devices[device]["manufacturer"] = device_info["device_type"]["manufacturer"]["name"]
        devices[device]["model"] = device_info["device_type"]["model"]

    # Now lets print the results in a Rich Table
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
        _manufacturer = data["manufacturer"]
        _model = data["model"]
        _uptime = data["uptime"]
        _latency = data["latency"]
        _cpu = data["cpu"]
        _memory = data["memory"]
        _bandwidth = data["bandwidth"]
        up_bgp = f"[green]{len(data['bgp']['up'])}[/]"
        down_bgp = f"[red]{len(data['bgp']['down'])}[/]"
        _bgp = f"{up_bgp} UP, {down_bgp} DOWN"

        table.add_row(device, _manufacturer, _model, _uptime, _latency, _cpu, _memory, _bandwidth, _bgp)

    # Print the table
    console.print(table)

    # Now lets collect the logs for the site in the last 15 minutes
    log_results = []
    for device in devices.keys():
        query = f'{{device=~"{device}"}}'
        now = datetime.datetime.now()
        start_timestamp = datetime.datetime.timestamp(now - datetime.timedelta(hours=0, minutes=30))
        end_time = datetime.datetime.timestamp(now)
        loki_results = retrieve_data_loki(query, start_timestamp, end_time)  # type: ignore
        log_results.extend(loki_results[:4])

    # Print the logs
    table = Table(title="Logs", show_lines=True)
    table.add_column("Device")
    table.add_column("Time")
    table.add_column("Message")

    for log in log_results:
        _device = log["stream"]
        _time = datetime.datetime.fromtimestamp(float(log["values"][0][0]) / 1000000000).strftime("%Y-%m-%d %H:%M:%S")
        _message = log["values"][0][1]
        table.add_row(_device["device"], _time, _message)

    # Print the table
    console.print(table)


if __name__ == "__main__":
    app()
