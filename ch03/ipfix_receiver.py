from scapy.all import *

# Import packets from a PCAP file
capture = rdpcap("ipfix.pcap")

# IPFIX and NETFLOWv9 share same structure
pkt = netflowv9_defragment(capture)[0]

# Print the packet summary
pkt.summary()

# Print the detail of the packet structure
pkt.show()

# Print the Ethernet destination address
print("\n- Destination Ethernet address")
print(pkt.dst)

# Print the IP destination IP address
print("\n- Destination IP address")
print(pkt[IP].dst)

# Check the packet layers
print("\n- Packet layers)")
print(pkt.layers())

# Validate the UDP port and Netflow flow sequence
print("\n- UDP port and Netflow flow sequence")
print(pkt["UDP"].sport)
print(pkt["NetflowHeaderV10"].flowSequence)
