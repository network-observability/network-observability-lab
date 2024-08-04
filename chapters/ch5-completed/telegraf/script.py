import os
import sys

from netmiko import ConnectHandler


def influx_line_protocol(measurement, tags, fields) -> str:
    """Generate an InfluxDB line protocol string."""
    # Construct the tags string
    tags_string = ""
    for key, value in tags.items():
        if value is not None:
            if isinstance(value, str):
                value = value.replace(" ", r"\ ")
            tags_string += f",{key}={value}"

    # Construct the fields string
    fields_string = ""
    for key, value in fields.items():
        if fields_string:
            fields_string += ","
        if isinstance(value, bool):
            fields_string += f"{key}=true" if value else f"{key}=false"
        elif isinstance(value, int):
            fields_string += f"{key}={value}i"
        elif isinstance(value, float):
            fields_string += f"{key}={value}"
        elif isinstance(value, str):
            value = value.replace(" ", r"\ ")
            fields_string += f'{key}="{value}"'
        else:
            fields_string += f"{key}={value}"

    return f"{measurement}{tags_string} {fields_string}"


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


    # Establish an SSH connection
    net_connect = ConnectHandler(**device)


    # Return the Netmiko connection object
    return net_connect


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


def main(device_type, host):
    """Get BGP neighbor data and print it in Influx line protocol format."""
    # Connect to the device (1)
    net_connect = netmiko_connect(device_type, host)


    # Execute the command on the device (2)
    output = net_connect.send_command("show ip bgp summary", use_textfsm=True)

    # Iterate over the BGP neighbors and process the data (3)
    for neighbor in output:
        measurement = "bgp"
        tags = {
            "neighbor": neighbor["bgp_neigh"],  # type: ignore
            "neighbor_asn": neighbor["neigh_as"],  # type: ignore
            "vrf": neighbor["vrf"],  # type: ignore
            "device": host
        }


        # Call the convert_state function to get the mapped state (4)
        state = convert_state(neighbor['state'])  # type: ignore

        fields = {
            "prefixes_received": neighbor["state_pfxrcd"],  # type: ignore
            "prefixes_accepted": neighbor["state_pfxacc"],  # type: ignore
            "neighbor_state": state
        }


        # Generate the line protocol string (5)
        # line_protocol = influx_line_protocol(measurement, tags, fields)
        line_protocol = influx_line_protocol(measurement, tags, fields)


        # Print the line protocol string (6)
        # For example: bgp,neighbor=x.x.x.x,neighbor_asn=xxxx,vrf=default prefixes_received=0,prefixes_accepted=0
        print(line_protocol, flush=True)


if __name__ == "__main__":
    # Get the device type and host from the command line
    device_type = sys.argv[1]
    host = sys.argv[2]


    # Call the main function passing in the device type and host
    main(device_type, host)
