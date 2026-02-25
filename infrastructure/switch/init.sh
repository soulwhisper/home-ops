#!/bin/sh
# This script configures H3C S6520-24S-SI as core switch for the environment
# If pasted into the switch console, make sure to paste by phases to avoid errors

# reset
# display default-configuration
# restore factory-default
# reboot

# defaults
sysname core-switch

ntp-service enable
clock timezone Beijing add 08:00:00
clock protocol ntp
ntp-service unicast-server 10.255.255.2

# dhcp
dhcp enable
dhcp snooping enable

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

# eBGP with BFD & OSPF
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
 jumboframe enable
 stp edged-port
 ipv6 nd raguard role host
 broadcast-suppression 5
 multicast-suppression 5
 unicast-suppression 5

interface bridge-aggregation 20
 description k8s-node-02
 link-aggregation mode dynamic
 port link-type access
 port access vlan 100
 jumboframe enable
 stp edged-port
 ipv6 nd raguard role host
 broadcast-suppression 5
 multicast-suppression 5
 unicast-suppression 5

interface bridge-aggregation 30
 description k8s-node-03
 link-aggregation mode dynamic
 port link-type access
 port access vlan 100
 jumboframe enable
 stp edged-port
 ipv6 nd raguard role host
 broadcast-suppression 5
 multicast-suppression 5
 unicast-suppression 5

interface ten-gigabitethernet 1/0/1
 port link-aggregation group 10

interface ten-gigabitethernet 1/0/2
 port link-aggregation group 10

interface ten-gigabitethernet 1/0/3
 port link-aggregation group 20

interface ten-gigabitethernet 1/0/4
 port link-aggregation group 20

interface ten-gigabitethernet 1/0/5
 port link-aggregation group 30

interface ten-gigabitethernet 1/0/6
 port link-aggregation group 30

# to nas, LACP 70
interface bridge-aggregation 70
 description nas
 link-aggregation mode dynamic
 port link-type access
 port access vlan 100
 jumboframe enable
 stp edged-port
 ipv6 nd raguard role host
 broadcast-suppression 5
 multicast-suppression 5
 unicast-suppression 5

interface ten-gigabitethernet 1/0/13
 port link-aggregation group 70

interface ten-gigabitethernet 1/0/14
 port link-aggregation group 70

# to workstation-fiber, LACP 80
interface bridge-aggregation 80
 description workstation-fiber
 link-aggregation mode dynamic
 port link-type access
 port access vlan 100
 jumboframe enable
 stp edged-port
 ipv6 nd raguard role host
 broadcast-suppression 5
 multicast-suppression 5
 unicast-suppression 5

interface ten-gigabitethernet 1/0/15
 port link-aggregation group 80

interface ten-gigabitethernet 1/0/16
 port link-aggregation group 80

# to access fiber, or LACP 110
interface ten-gigabitethernet 1/0/21
 description access-fiber
 port link-type trunk
 port trunk permit vlan 1 10 200 210
 stp root-protection
 stp point-to-point force-true
 ipv6 nd raguard role host
 broadcast-suppression 1
 multicast-suppression 1
 unicast-suppression 1

# to router fiber, LACP 120
interface bridge-aggregation 120
 description router-transit
 port link-type access
 port access vlan 1000
 jumboframe enable
 stp point-to-point force-true
 dhcp snooping trust
 ipv6 nd raguard role router
 broadcast-suppression 5
 multicast-suppression 5
 unicast-suppression 5

interface ten-gigabitethernet 1/0/23
 port link-aggregation group 120

interface ten-gigabitethernet 1/0/24
 port link-aggregation group 120

# VIF
# DHCP Server at x.x.x.254
interface vlan-interface 1
 ip address 10.0.0.1 24
 dhcp select relay
 dhcp relay server-address 10.255.255.2

interface vlan-interface 10
 ip address 10.0.10.1 24
 dhcp select relay
 dhcp relay server-address 10.255.255.2

interface vlan-interface 100
 ip address 10.10.0.1 24
 dhcp select relay
 dhcp relay server-address 10.255.255.2

interface vlan-interface 200
 ip address 10.20.0.1 24
 dhcp select relay
 dhcp relay server-address 10.255.255.2

interface vlan-interface 210
 ip address 10.20.10.1 24
 dhcp select relay
 dhcp relay server-address 10.255.255.2

interface vlan-interface 1000
 ip address 10.255.255.1 30

# Route
ip route-static 0.0.0.0 0 10.255.255.2
