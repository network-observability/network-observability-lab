"""BGP neighbor state_pfxrcd/state_pfxacc to InfluxDB line protocol script."""
import os
import sys
from netmiko import ConnectHandler


def influx_line_protocol(measurement, tags, fields):
    """Generate an InfluxDB line protocol string."""
    # Create the measurement string
    line_protocol = f"{measurement},"

    # Add the tags to the line protocol
    for tag in tags:
        line_protocol += f"{tag},"

    # Remove the trailing comma
    line_protocol = line_protocol[:-1]

    # Add the fields to the line protocol
    line_protocol += " "
    for field in fields:
        line_protocol += f"{field},"

    # Remove the trailing comma
    line_protocol = line_protocol[:-1]

    # Return the line protocol string.
    return line_protocol


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
        tags = [
            f"neighbor={neighbor['bgp_neigh']}",  # type: ignore
            f"neighbor_asn={neighbor['neigh_as']}",  # type: ignore
            f"vrf={neighbor['vrf']}",  # type: ignore
        ]
        fields = [
            f"prefixes_received={neighbor['state_pfxrcd']}",  # type: ignore
            f"prefixes_accepted={neighbor['state_pfxacc']}",  # type: ignore
        ]

        # Generate the line protocol string
        line_protocol = influx_line_protocol(measurement, tags, fields)

        # Print the line protocol string.
        # For example: bgp,neighbor=x.x.x.x,neighbor_asn=xxxx,vrf=default prefixes_received=0,prefixes_accepted=0
        print(line_protocol)


if __name__ == "__main__":
    # Get the device type and host from the command line
    device_type = sys.argv[1]
    host = sys.argv[2]

    # Call the main function passing in the device type and host
    main(device_type, host)
