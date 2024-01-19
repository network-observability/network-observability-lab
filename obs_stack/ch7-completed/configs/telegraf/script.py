"""BGP neighbor state_pfxrcd/state_pfxacc to InfluxDB line protocol script."""
import os
import sys
from typing import Optional
from dataclasses import dataclass

from netmiko import ConnectHandler
from line_protocol_parser import parse_line


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

    # Execute the show version command on the device
    output = net_connect.send_command("show ip bgp summary", use_textfsm=True)

    # Print the output of the command
    # print(output)

    # Print the state_pfxrcd / state_pfxacc value for each BGP neighbor in the influx line protocol format
    for neighbor in output:
        # Ignore neighbors that are not in the Established state
        if not neighbor['state_pfxrcd']:  # type: ignore
            continue

        # Create the measurement, tags, and fields for InfluxDB line protocol format
        measurement = "bgp"
        tags = {
            "neighbor": neighbor['bgp_neigh'],  # type: ignore
            "neighbor_asn": neighbor['neigh_as'],  # type: ignore
            "vrf": neighbor['vrf'],  # type: ignore
        }
        fields = {
            "prefixes_received": neighbor['state_pfxrcd'],  # type: ignore
            "prefixes_accepted": neighbor['state_pfxacc'],  # type: ignore
        }

        # Generate the line protocol string
        line_protocol = InfluxMetric(measurement, tags, fields)

        # Print the line protocol string.
        # For example: bgp,neighbor=x.x.x.x,neighbor_asn=xxxx,vrf=default prefixes_received=0,prefixes_accepted=0
        print(line_protocol)


if __name__ == "__main__":
    # Get the device type and host from the command line
    device_type = sys.argv[1]
    host = sys.argv[2]

    # Call the main function passing in the device type and host
    main(device_type, host)
