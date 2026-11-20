// @ts-check
/// <reference path="../types-dnscontrol.d.ts" />

var REG_NONE = NewRegistrar("none");
var PDNS = NewDnsProvider("powerdns");
var ZONE = "pdns.homelab.internal";
var NS_NAME = "ns." + ZONE + ".";
var SOA_RECORD = SOA("@", NS_NAME, "hostmaster." + ZONE + ".", 7200, 900, 1209600, 300, TTL(300));

D(ZONE, REG_NONE, DnsProvider(PDNS),
  DefaultTTL(300),
  SOA_RECORD,
  NAMESERVER(NS_NAME),
  A("ns", "10.10.0.100"),
  NS("k8s", NS_NAME)
);

D("k8s." + ZONE, REG_NONE, DnsProvider(PDNS),
  DefaultTTL(300),
  SOA_RECORD,
  NAMESERVER(NS_NAME),
  // ExternalDNS owns A/AAAA/CNAME and its registry TXT records in this zone.
  IGNORE("", "A,AAAA,CNAME,TXT")
);
