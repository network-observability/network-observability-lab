from pygnmi.client import gNMIclient, telemetryParser
import json

with gNMIclient(
    target=("ceos-01", 50051),
    username="netobs",
    password="netobs123",
    insecure=True
) as gc:
    telemetry_stream = gc.subscribe(
        subscribe={
            "subscription": [
                {
                    "path": "interfaces/interface[name=Management0]/state/counters/in-pkts",
                    "mode": "sample",
                    "sample_interval": 10000000000,
                },
            ],
            "mode": "stream",
            "encoding": "json"
        })

    for telemetry_entry in telemetry_stream:
        print(json.dumps(telemetryParser(telemetry_entry), indent=True))
