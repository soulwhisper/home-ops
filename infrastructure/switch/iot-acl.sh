#!/bin/sh
# This script configures H3C S6520-24S-SI IOT ACL.
# If pasted into the switch console, make sure to paste by phases to avoid errors

system-view

# IOT subnet = 10.20.10.0/24
# aqara hub = 10.20.10.100

acl advanced 3500
 description IoT-VLAN210-Egress-Control
 rule 0  permit udp source any destination 255.255.255.255 0 destination-port eq 67
 rule 1  permit udp source 10.20.10.0 0.0.0.255 destination 10.20.10.1 0 destination-port eq 67
 rule 5  permit udp source 10.20.10.0 0.0.0.255 destination 10.20.10.1 0 destination-port eq 53
 rule 6  permit tcp source 10.20.10.0 0.0.0.255 destination 10.20.10.1 0 destination-port eq 53
 rule 10 permit udp source 10.20.10.0 0.0.0.255 destination-port eq 123
 rule 15 permit icmp source 10.20.10.0 0.0.0.255 destination 10.20.10.1 0
 rule 20 permit ip source 10.20.10.100 0 destination 10.20.0.0 0.0.0.255
 rule 41 deny udp source 10.20.10.0 0.0.0.255 destination-port eq 53
 rule 42 deny tcp source 10.20.10.0 0.0.0.255 destination-port eq 53
 rule 50 deny ip source 10.20.10.0 0.0.0.255 destination 10.0.0.0 0.0.0.255
 rule 51 deny ip source 10.20.10.0 0.0.0.255 destination 10.0.10.0 0.0.0.255
 rule 52 deny ip source 10.20.10.0 0.0.0.255 destination 10.10.0.0 0.0.0.255
 rule 53 deny ip source 10.20.10.0 0.0.0.255 destination 10.20.0.0 0.0.0.255
 rule 54 deny ip source 10.20.10.0 0.0.0.255 destination 10.255.255.0 0.0.0.3
 rule 60 deny ip source 10.20.10.0 0.0.0.255 destination 10.0.0.0 0.255.255.255
 rule 61 deny ip source 10.20.10.0 0.0.0.255 destination 172.16.0.0 0.15.255.255
 rule 62 deny ip source 10.20.10.0 0.0.0.255 destination 192.168.0.0 0.0.255.255
 rule 1000 permit ip source 10.20.10.0 0.0.0.255

acl advanced 3510
 description Home-to-IoT-Control
 rule 0  permit ip source 10.20.0.0 0.0.0.255 destination 10.20.10.100 0
 rule 10 permit tcp source 10.20.0.0 0.0.0.255 destination 10.20.10.0 0.0.0.255 destination-port eq 80
 rule 11 permit tcp source 10.20.0.0 0.0.0.255 destination 10.20.10.0 0.0.0.255 destination-port eq 443
 rule 15 permit icmp source 10.20.0.0 0.0.0.255 destination 10.20.10.0 0.0.0.255
 rule 100 deny ip source 10.20.0.0 0.0.0.255 destination 10.20.10.0 0.0.0.255
 rule 1000 permit ip

acl advanced 3600
 description Traffic-from-IOT-Control
 rule 0 permit ip source 10.20.10.0 0.0.0.255

traffic classifier tc-iot-all
 if-match acl 3600

traffic behavior tb-iot-rate-limit
 car cir 10000 cbs 1536000

qos policy qp-iot-rate
 classifier tc-iot-all behavior tb-iot-rate-limit

interface vlan-interface 210
 packet-filter 3500 inbound

interface vlan-interface 200
 packet-filter 3510 inbound

interface ten-gigabitethernet 1/0/21
 qos apply policy qp-iot-rate inbound
