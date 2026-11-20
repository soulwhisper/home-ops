// @ts-check
/// <reference path="types-dnscontrol.d.ts" />

// NOTE: dnscontrol's otto JS engine is ES5-only — no spread, no arrow functions.
var REG_NONE = NewRegistrar("none");
var PDNS = NewDnsProvider("powerdns");
var NS_NAME = "ns.homelab.internal.";

function zoneSOA(domain) {
  return SOA("@", NS_NAME, "hostmaster." + domain + ".", 7200, 900, 1209600, 300, TTL(300));
}

var CLUSTER_NODES = [
  { name: "exarch-01", ip: "10.10.0.101", type: "cp" },
  { name: "exarch-02", ip: "10.10.0.102", type: "cp" },
  { name: "exarch-03", ip: "10.10.0.103", type: "cp" },
];

/**
 * @param {string} endpointName
 * @param {Array<{name: string, ip: string, type: string}>} nodes
 * @returns {Array<DomainModifier>}
 */
function generateClusterRecords(endpointName, nodes) {
  var records = [];
  for (var i = 0; i < nodes.length; i++) {
    var node = nodes[i];
    records.push(A(node.name, node.ip));
    if (node.type === "cp") {
      records.push(A(endpointName, node.ip));
    }
  }
  return records;
}

var STATIC_RECORDS = [
  A("esxi", "10.0.0.10"),
  A("zigbee", "10.10.0.20"),
  A("nas", "10.10.0.100"),
  A("unifi", "10.10.0.200"),
  A("studio", "10.10.0.210"),
];

D.apply(
  null,
  ["homelab.internal", REG_NONE, DnsProvider(PDNS), DefaultTTL(300),
    zoneSOA("homelab.internal"), NAMESERVER(NS_NAME), A("ns", "10.10.0.100")].concat(
    STATIC_RECORDS,
    generateClusterRecords("k8s", CLUSTER_NODES)
  )
);

D("noirprime.com", REG_NONE, DnsProvider(PDNS),
  DefaultTTL(300),
  zoneSOA("noirprime.com"),
  NAMESERVER(NS_NAME),
  IGNORE_EXTERNAL_DNS("k8s-int."),
  A("derp", "10.10.0.254"),
  // Match Cloudflare's public apex mail records for clients using the internal view.
  MX("@", 73, "route2.mx.cloudflare.net."),
  MX("@", 79, "route3.mx.cloudflare.net."),
  MX("@", 81, "route1.mx.cloudflare.net."),
  TXT("@", "v=spf1 include:_spf.mx.cloudflare.net ~all")
);
