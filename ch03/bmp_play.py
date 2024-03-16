import pyshark

capture = pyshark.FileCapture("bmp.pcap", decode_as={"tcp.port==6666": "bmp"})

capture.load_packets()

print(f"There are {len(capture)} packets in this capture.")

for packet in capture:
    print(packet.layers)

packet = capture[7]
packet.show()
