import requests
from requests.auth import HTTPBasicAuth
import json

# Disable the warning for not certificate verification
requests.packages.urllib3.disable_warnings()

router = "ceos-01"
restconf_port = 5900

result = requests.get(
    f"https://{router}:{restconf_port}/restconf/data/openconfig-interfaces:interfaces/interface=Management0/state",
    auth=HTTPBasicAuth("netobs", "netobs123"),
    headers={
        "Content-Type": "application/yang-data+json",
        "Accept": "application/yang-data+json"
    },
    verify=False)

print(json.dumps(
    result.json()['openconfig-interfaces:counters'], indent=True
))
