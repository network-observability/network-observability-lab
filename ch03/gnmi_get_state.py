from pygnmi.client import gNMIclient
import json

paths = ['openconfig-interfaces:interfaces']

with gNMIclient(
    target=("ceos-01", 50051),
    username="netobs",
    password="netobs123",
    insecure=True
) as gc:

    result = gc.get(path=paths, encoding='json')

print(json.dumps(
    result["notification"][0]["update"][0]["val"]["openconfig-interfaces:interface"][0]["state"],
    indent=True
))
