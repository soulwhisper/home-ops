// @ts-check
/// <reference path="types-dnscontrol.d.ts" />

var REG_NONE = NewRegistrar("none");
var DSP_ADGUARDHOME = NewDnsProvider("adguard_home");

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

D(
  "homelab.internal",
  REG_NONE,
  DnsProvider(DSP_ADGUARDHOME),
  A("esxi", "10.0.0.10"),
  A("zigbee", "10.10.0.20"),
  A("nas", "10.10.0.100"),
  A("unifi", "10.10.0.200"),
  ...generateClusterRecords("k8s", CLUSTER_NODES)
);
