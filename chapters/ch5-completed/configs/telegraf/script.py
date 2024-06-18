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


def convert_state(state):
    """Convert the state to a more readable format."""
    state_mapping = {
        "Estab": "ESTABLISHED",
        "Idle(NoIf)": "IDLE",
        "Idle": "IDLE",
        "Connect": "CONNECT",
        "Active": "ACTIVE",
        "opensent": "OPENSENT",
        "openconfirm": "OPENCONFIRM"
    }
    # Return the mapped state or the original state in uppercase
    return state_mapping.get(state, state.upper())


def netmiko_connect(device_type, host):
    """Connect to a device using Netmiko."""
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

    # Return the Netmiko connection object
    return net_connect


def main(device_type, host):
    """Get BGP neighbor data and print it in Influx line protocol format."""
    # Connect to the device
    net_connect = netmiko_connect(device_type, host)

    # Execute the show version command on the device
    output = net_connect.send_command("show ip bgp summary", use_textfsm=True)

    # Iterate over the BGP neighbors and process the data
    for neighbor in output:
        measurement = "bgp"
        tags = [
            f"neighbor={neighbor['bgp_neigh']}",  # type: ignore
            f"neighbor_asn={neighbor['neigh_as']}",  # type: ignore
            f"vrf={neighbor['vrf']}",  # type: ignore
            f"device={host}",
        ]

        # Call the convert_state function to get the mapped state
        state = convert_state(neighbor['state'])  # type: ignore

        fields = [
            f"prefixes_received={neighbor['state_pfxrcd']}",  # type: ignore
            f"prefixes_accepted={neighbor['state_pfxacc']}",  # type: ignore
            f"neighbor_state={state}"
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
