// @ts-check
/// <reference path="types-dnscontrol.d.ts" />

var REG_NONE = NewRegistrar("none");
var PDNS = NewDnsProvider("powerdns");
var NS_NAME = "ns.homelab.internal.";
var DEFAULT_TTL = 300;

var CLUSTER_NODES = [
  { name: "exarch-01", ip: "10.10.0.101", controlPlane: true },
  { name: "exarch-02", ip: "10.10.0.102", controlPlane: true },
  { name: "exarch-03", ip: "10.10.0.103", controlPlane: true }
];

/** @param {string} domain */
function zoneSOA(domain) {
  return SOA(
    "@",
    NS_NAME,
    "hostmaster." + domain + ".",
    7200,    // refresh
    900,     // retry
    1209600, // expire
    300,     // negative cache TTL
    TTL(300)
  );
}

/**
 * @param {string} endpointName
 * @param {Array<{name: string, ip: string, controlPlane: boolean}>} nodes
 * @returns {Array<DomainModifier>}
 */
function clusterRecords(endpointName, nodes) {
  var records = [];
  for (var i = 0; i < nodes.length; i++) {
    var node = nodes[i];
    records.push(A(node.name, node.ip));
    if (node.controlPlane) {
      records.push(A(endpointName, node.ip));
    }
  }
  return records;
}

// Internal infrastructure zone.
D("homelab.internal", REG_NONE, DnsProvider(PDNS),
  DefaultTTL(DEFAULT_TTL),
  zoneSOA("homelab.internal"),
  NAMESERVER(NS_NAME),
  A("ns", "10.10.0.100"),

  // LAN hosts and appliances.
  A("esxi", "10.0.0.10"),
  A("zigbee", "10.10.0.20"),
  A("nas", "10.10.0.100"),
  A("unifi", "10.10.0.200"),
  A("studio", "10.10.0.210"),

  // Node addresses and the shared Kubernetes API endpoint.
  clusterRecords("k8s", CLUSTER_NODES)
);

// Internal DNS view of the public domain.
D("noirprime.com", REG_NONE, DnsProvider(PDNS),
  DefaultTTL(DEFAULT_TTL),
  zoneSOA("noirprime.com"),
  NAMESERVER(NS_NAME),

  IGNORE_EXTERNAL_DNS("k8s-int."),
  A("derp", "10.10.0.254"),

  // Mirror Cloudflare's public apex mail records for internal clients.
  MX("@", 73, "route2.mx.cloudflare.net."),
  MX("@", 79, "route3.mx.cloudflare.net."),
  MX("@", 81, "route1.mx.cloudflare.net."),
  TXT("@", "v=spf1 include:_spf.mx.cloudflare.net ~all")
);
