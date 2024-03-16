from pygnmi.client import gNMIclient
import json


with gNMIclient(
    target=("ceos-01", 50051), username="netobs", password="netobs123", insecure=True
) as gc:
    result = gc.capabilities()

print(json.dumps(result, indent=True))
