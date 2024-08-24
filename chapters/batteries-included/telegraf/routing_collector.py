"""BGP neighbor state_pfxrcd/state_pfxacc to InfluxDB line protocol script."""

import os
import sys
from dataclasses import dataclass
from typing import Optional

from netmiko import BaseConnection, ConnectHandler


@dataclass
class InfluxMetric:
    measurement: str
    tags: dict
    fields: dict
    time: Optional[int] = None

    def __str__(self):
        tags_string = ""
        for key, value in self.tags.items():
            if value is not None:
                if isinstance(value, str):
                    value = value.replace(" ", r"\ ")
                tags_string += f",{key}={value}"

        fields_string = ""
        for key, value in self.fields.items():
            if fields_string:
                fields_string += ","
            if isinstance(value, bool):
                fields_string += f"{key}=true" if value else f"{key}=false"
            elif isinstance(value, (int)):
                fields_string += f"{key}={value}i"
            elif isinstance(value, (float)):
                fields_string += f"{key}={value}"
            elif isinstance(value, str):
                value = value.replace(" ", r"\ ")
                fields_string += f'{key}="{value}"'
            else:
                fields_string += f"{key}={value}"

        return (
            f"{self.measurement}{tags_string} {fields_string} {self.time}"
            if self.time
            else f"{self.measurement}{tags_string} {fields_string}"
        )


def bgp_collector(net_connect: BaseConnection) -> list[InfluxMetric]:
    """Collect BGP neighbor information."""
    bgp_output = net_connect.send_command("show ip bgp summary", use_textfsm=True)

    results = []
    for neighbor in bgp_output:
        measurement = "bgp"
        tags = {
            "neighbor": neighbor["bgp_neigh"],  # type: ignore
            "neighbor_asn": neighbor["neigh_as"],  # type: ignore
            "vrf": neighbor["vrf"],  # type: ignore
            "device": host,
        }

        # Convert the state to a more readable format
        if "Estab" in neighbor["state"]:  # type: ignore
            state = "ESTABLISHED"
        elif "Idle" in neighbor["state"]:  # type: ignore
            state = "IDLE"
        elif "Connect" in neighbor["state"]:  # type: ignore
            state = "CONNECT"
        elif "Active" in neighbor["state"]:  # type: ignore
            state = "ACTIVE"
        elif "opensent" in neighbor["state"].lower():  # type: ignore
            state = "OPENSENT"
        elif "openconfirm" in neighbor["state"].lower():  # type: ignore
            state = "OPENCONFIRM"
        else:
            state = neighbor["state"].upper()  # type: ignore

        fields = {"neighbor_state": state}

        if neighbor["state_pfxrcd"]:  # type: ignore
            fields["prefixes_received"] = int(neighbor["state_pfxrcd"])  # type: ignore
            fields["prefixes_accepted"] = int(neighbor["state_pfxacc"])  # type: ignore

        results.append(InfluxMetric(measurement, tags, fields))

    return results


def ospf_collector(net_connect: BaseConnection) -> list[InfluxMetric]:
    """Collect OSPF neighbor information."""
    ospf_output = net_connect.send_command("show ip ospf neighbor", use_textfsm=True)

    results = []
    for neighbor in ospf_output:
        measurement = "ospf"
        address = neighbor.get("ip_address") if neighbor.get("ip_address") else neighbor.get("address")  # type: ignore
        tags = {
            "neighbor": address,
            "interface": neighbor["interface"],  # type: ignore
            "neighbor_id": neighbor["neighbor_id"],  # type: ignore
            "instance": neighbor["instance"],  # type: ignore
            "vrf": neighbor["vrf"],  # type: ignore
        }

        state = neighbor["state"].replace("/BDR", "").replace("/DR", "")  # type: ignore
        fields = {"neighbor_state": state.upper()}
        results.append(InfluxMetric(measurement, tags, fields))

    return results


def main(device_type, host):
    """Connect to a device and print the BGP neighbor pfxrcd/pfxacc value in the influx line protocol format."""
    # Define the device to connect to
    device = {
        "device_type": device_type,
        "host": host,
        # Use environment variables for username and password
        "username": os.getenv("NETWORK_AGENT_USER"),
        "password": os.getenv("NETWORK_AGENT_PASSWORD"),
    }

    # Establish an SSH connection to the device by passing in the device dictionary
    net_connect = ConnectHandler(**device)

    # Collect BGP neighbor information
    bgp_metrics = bgp_collector(net_connect)
    for metric in bgp_metrics:
        print(metric, flush=True)

    # Collect OSPF neighbor information
    ospf_metrics = ospf_collector(net_connect)
    for metric in ospf_metrics:
        print(metric, flush=True)

    # Close the SSH connection
    net_connect.disconnect()


if __name__ == "__main__":
    # Get the device type and host from the command line
    device_type = sys.argv[1]
    host = sys.argv[2]

    # Call the main function passing in the device type and host
    main(device_type, host)
