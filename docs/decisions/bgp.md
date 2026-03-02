## ADR - 01 - BGP/BFD solution

**Context:**
Current Cilium lacks native BFD support. To ensure sub-second failure detection and route convergence with Core Switches, an external BGP/BFD solution is required.

**Decision:**
I have decided to adopt **FRR-K8s** effectively decoupling the routing control plane from the CNI, rather than cascading BGP via a localhost BIRD2 instance.

**Rationale & Comparison:**

**1. Why FRR-K8s (Selected):**

- **Cloud-Native Operations:** Configuration is managed entirely via Kubernetes CRDs (Custom Resource Definitions), allowing for a GitOps-friendly workflow without touching host-level configuration files.
- **Architecture Decoupling:** Decouples the routing advertisement from the Cilium agent. Upgrades or issues with the CNI datapath do not directly destabilize the BGP session structure.
- **Standardized BFD:** Provides mature, industry-standard BFD implementation compatible with mainstream switch vendors.

**2. Why BIRD2 Localhost Cascade (Rejected):**

- **High Operational Complexity:** Requires managing `bird.conf` files on every node, increasing maintenance burden.
- **Complex Troubleshooting:** The chained architecture (Cilium -> Localhost BIRD -> Switch) introduces an extra hop, making root cause analysis more difficult during connectivity issues.
- **Resource Conflicts:** Potential port conflicts (TCP 179) on the host network.

**Known Risks / Mitigation for FRR-K8s:**

- **Risk:** Routing updates rely on the K8s API Server latency.
- **Mitigation:** Ensure high availability of the Control Plane and configure strict `readinessProbes` for workloads to prevent blackholing traffic during Pod instability.

### Example configs

- frr-k8s

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas.noirprime.com/frrk8s.metallb.io/frrconfiguration_v1beta1.json
apiVersion: frrk8s.metallb.io/v1beta1
kind: FRRConfiguration
metadata:
  name: frr-k8s
  namespace: kube-system
spec:
  bgp:
    routers:
      - asn: 65100
        neighbors:
          - address: "10.10.0.1" # Switch eBGP
            asn: 65000
            port: 179
            bfdProfile: default
            ebgpMultiHop: false
            enableGracefulRestart: false # bfd instead
            toAdvertise:
              allowed:
                mode: all
        prefixes:
          - "10.100.0.0/17" # Pod
          - "10.10.0.192/27" # LoadBalancer
    bfdProfiles:
      - name: default
        receiveInterval: 400
        transmitInterval: 400
        detectMultiplier: 5
        echoInterval: 50
        echoMode: false
        passiveMode: false
        minimumTtl: 1
```

- bird2 extension since talos v1.12.0

```yaml
---
apiVersion: v1alpha1
kind: ExtensionServiceConfig
name: bird2
configFiles:
  - mountPath: /usr/local/etc/bird.conf
    content: |
      define FABRIC_AS = 65000;
      define NODE_AS = 65100;
      define CILIUM_AS = 65110;

      log stderr all;
      debug protocols all;

      router id from "dummy0";

      protocol device {
        scan time 10;
      }

      protocol direct loopback {
        interface "dummy0";
        ipv4 {
          import all;
          export none;
        };
      }

      protocol bfd {
        interface "bond0" {
          interval 400 ms;
          multiplier 5;
        };
      }

      protocol kernel {
        merge paths on;
        learn off;
        ipv4 {
          export filter {
            if proto = "cilium" then reject;
            if proto = "loopback" then reject;
            accept;
          };
          import none;
        };
      }

      protocol bgp fabric_bond0 {
        local as NODE_AS;
        neighbor 10.10.0.1 as FABRIC_AS; # switch
        interface "bond0";
        bfd on;
        hold time 180;
        keepalive time 60;
        ipv4 {
          import all;
          export all;
          next hop self;
        };
      };

      protocol bgp cilium {
        passive on;
        multihop 2;  # bypass bird statup check for localhost IP address
        local as NODE_AS;
        neighbor 127.0.0.1 as CILIUM_AS;
        ipv4 {
          import all;
          export none;
        };
      };
```

- cilium config for bird2, with `bgpControlPlane.enabled: true`;

```yaml
---
# yaml-language-server: $schema=https://kubernetes-schemas.noirprime.com/cilium.io/ciliumbgpadvertisement_v2.json
apiVersion: cilium.io/v2
kind: CiliumBGPAdvertisement
metadata:
  name: cilium-bird2-nodelocal
  labels:
    bgp: cilium-bird2-nodelocal
spec:
  advertisements:
    # - advertisementType: PodCIDR
    - advertisementType: Service
      service:
        addresses:
          - LoadBalancerIP
      selector:
        matchExpressions:
          - {
              key: config.home-ops.io/bgp,
              operator: NotIn,
              values: ["disabled"],
            }
---
# yaml-language-server: $schema=https://kubernetes-schemas.noirprime.com/cilium.io/ciliumbgpclusterconfig_v2.json
apiVersion: cilium.io/v2
kind: CiliumBGPClusterConfig
metadata:
  name: cilium-bird2-nodelocal
spec:
  nodeSelector: {}
  bgpInstances:
    - name: cilium-bird2-nodelocal-65110
      localASN: 65110
      peers:
        - name: cilium-bird2-nodelocal
          peerASN: 65100
          peerAddress: 127.0.0.1
          peerConfigRef:
            name: cilium-bird2-nodelocal
---
# yaml-language-server: $schema=https://kubernetes-schemas.noirprime.com/cilium.io/ciliumbgppeerconfig_v2.json
apiVersion: cilium.io/v2
kind: CiliumBGPPeerConfig
metadata:
  name: cilium-bird2-nodelocal
spec:
  families:
    - afi: ipv4
      safi: unicast
      advertisements:
        matchLabels:
          bgp: cilium-bird2-nodelocal
```
