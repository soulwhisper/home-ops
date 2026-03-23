#!/bin/sh
# This script configures H3C S6520-24S-SI as core switch for the environment
# If pasted into the switch console, make sure to paste by phases to avoid errors

# reset
# display default-configuration
# restore factory-default
# reboot
system-view

# defaults
sysname core-switch

ntp-service enable
clock timezone Beijing add 08:00:00
clock protocol ntp
ntp-service unicast-server 10.255.255.2

local-user admin class manage
 password hash $h$6$OVjMabRGiXTaA6o1$trdfOOxutBiTMcL7H/cx8pKCQ8PWkufiyu6FDotSdoqWRmy1Kdl66DSeSFlgni/WffDVUv2V50r1lgAkBILXIQ==
 service-type ssh terminal
 authorization-attribute user-role network-admin
 authorization-attribute user-role network-operator

ssh server enable
ssh user admin service-type all authentication-type password

public-key local create rsa
public-key local create ecdsa

undo telnet server enable

line vty 0 4
 authentication-mode scheme
 protocol inbound ssh
 user-role network-admin

# lacp
lacp system-priority 100

# dhcp
dhcp enable
dhcp snooping enable

# unifi: "https://10.10.0.200:8443/inform"
dhcp server ip-pool 0
gateway-list 10.0.0.1
dns-list 10.0.0.254
option 43 hex 68747470733a2f2f31302e31302e302e3230303a383434332f696e666f726d
static-bind ip-address 10.0.0.201 24 hardware-address 9C05-D6A1-6277
static-bind ip-address 10.0.0.202 24 hardware-address 9C05-D6A1-69C7

# stp
stp mode rstp
stp instance 0 root primary
stp bpdu-protection

# vlan
vlan 1
 dhcp snooping binding record

vlan 10
 dhcp snooping binding record

vlan 100
 dhcp snooping binding record

vlan 200
 dhcp snooping binding record

vlan 210
 dhcp snooping binding record

vlan 1000
 dhcp snooping binding record

# VIF
# DHCP Server at x.x.x.254
interface vlan-interface 1
 ip address 10.0.0.1 24
 undo dhcp client identifier
 undo ipv6 address dhcp-alloc
 undo ipv6 dhcp client duid

interface vlan-interface 10
 ip address 10.0.10.1 24

interface vlan-interface 100
 ip address 10.10.0.1 24
 bfd min-transmit-interval 400
 bfd min-receive-interval 400
 bfd detect-multiplier 5

interface vlan-interface 200
 ip address 10.20.0.1 24

interface vlan-interface 210
 ip address 10.20.10.1 24

interface vlan-interface 1000
 ip address 10.255.255.1 30

# Route
ip route-static 0.0.0.0 0 10.255.255.2

# eBGP with BFD
bfd session init-mode active
bgp 65000
 router-id 10.10.0.1
 timer keepalive 10 hold 30
 group k8s external
  peer k8s bfd
  peer k8s as-number 65100
  peer k8s connect-interface vlan-interface 100
 peer 10.10.0.101 group k8s
 peer 10.10.0.102 group k8s
 peer 10.10.0.103 group k8s
 address-family ipv4
  peer k8s enable
  import-route direct

# LACP to K8S
interface bridge-aggregation 10
 description k8s-node-01
 link-aggregation mode dynamic
 port link-type access
 port access vlan 100
 stp edged-port
 ipv6 nd raguard role host

interface bridge-aggregation 20
 description k8s-node-02
 link-aggregation mode dynamic
 port link-type access
 port access vlan 100
 stp edged-port
 ipv6 nd raguard role host

interface bridge-aggregation 30
 description k8s-node-03
 link-aggregation mode dynamic
 port link-type access
 port access vlan 100
 stp edged-port
 ipv6 nd raguard role host

interface ten-gigabitethernet 1/0/1
 port link-aggregation group 10 force
 lacp period short

interface ten-gigabitethernet 1/0/2
 port link-aggregation group 10 force
 lacp period short

interface ten-gigabitethernet 1/0/3
 port link-aggregation group 20 force
 lacp period short

interface ten-gigabitethernet 1/0/4
 port link-aggregation group 20 force
 lacp period short

interface ten-gigabitethernet 1/0/5
 port link-aggregation group 30 force
 lacp period short

interface ten-gigabitethernet 1/0/6
 port link-aggregation group 30 force
 lacp period short

# to nas, LACP 70
interface bridge-aggregation 70
 description nas
 link-aggregation mode dynamic
 port link-type access
 port access vlan 100
 stp edged-port
 ipv6 nd raguard role host

interface ten-gigabitethernet 1/0/13
 port link-aggregation group 70 force
 lacp period short

interface ten-gigabitethernet 1/0/14
 port link-aggregation group 70 force
 lacp period short

# to workstation-fiber, LACP 80
interface bridge-aggregation 80
 description workstation-fiber
 link-aggregation mode dynamic
 port link-type access
 port access vlan 100
 stp edged-port
 ipv6 nd raguard role host

interface ten-gigabitethernet 1/0/15
 port link-aggregation group 80 force
 lacp period short

interface ten-gigabitethernet 1/0/16
 port link-aggregation group 80 force
 lacp period short

# to management eth
interface ten-gigabitethernet 1/0/19
 description management-eth
 port link-type access
 stp edged-port
 broadcast-suppression 5
 multicast-suppression 5
 unicast-suppression 5

# to access fiber, or LACP 110
interface ten-gigabitethernet 1/0/21
 description access-fiber
 port link-type trunk
 port trunk permit vlan 1 10 200 210
 stp root-protection
 stp point-to-point force-true
 ipv6 nd raguard role host
 broadcast-suppression 5
 multicast-suppression 5
 unicast-suppression 5

# to router fiber, static LAG 120
# esxi vss not support LACP
interface bridge-aggregation 120
 description router-fiber
 port link-type trunk
 undo port trunk permit vlan 1
 port trunk permit vlan 10 100 200 210 1000
 stp point-to-point force-true
 dhcp snooping trust
 ipv6 nd raguard role router

interface ten-gigabitethernet 1/0/23
 port link-aggregation group 120 force
 lacp period short

interface ten-gigabitethernet 1/0/24
 port link-aggregation group 120 force
 lacp period short
