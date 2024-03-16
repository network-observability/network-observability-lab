from scapy.all import *

host = "1.1.1.1"

# ICMP test
send(IP(dst=host)/ICMP())

response = sr1(IP(dst=host)/ICMP())


# DNS test
response = sr1(IP(dst=host)/UDP()/DNS(rd=1,qd=DNSQR(qname="www.example.org")))
response.show()
response[DNSRR].rdata
