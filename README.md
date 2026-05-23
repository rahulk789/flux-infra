# Infrastructure Engineer — Live Interview Exercise

## Overview

This is a hands-on interview where we'll work through a real infrastructure migration problem together. The interview will take approximately **90 minutes**.

Please read the architecture section below, look through the `flux-repo/` directory, and complete all the setup steps before the interview. **You do not need to prepare a solution** — we'll work through everything together.

---

## Architecture

We run a GPU inference platform that handles millions of requests per day. Our control plane runs on GKE and manages workload scheduling across an external GPU fleet.

We currently run a **single-zone GKE cluster** (`us-central1-a`) and want to migrate to a **regional GKE cluster** (`us-central1`) for control plane high availability.

### Cluster

- **GKE cluster**: `production-ctrl`, single-zone in `us-central1-a`
- **Node pools**: `system-pool` (e2-standard-4, 3 nodes), `workload-pool` (e2-standard-8, 5 nodes)
- **Kubernetes version**: 1.29
- **GitOps**: All cluster resources are managed by FluxCD v2

### Services

Two internal services run on this cluster:

1. **Gateway** — Receives inbound inference requests from end users, asks the operator for a GPU instance with the right workload, proxies the request to the instance, and returns the instance to the operator when done. Stateless. Runs as a Deployment.

2. **Operator** — Manages GPU workload scheduling across the external GPU fleet. Maintains scheduling state in PostgreSQL. Runs as a Deployment.

Both services connect to:
- **Cloud SQL (PostgreSQL)** — Private IP, accessible via VPC peering.
- **Memorystore (Redis)** — Private IP, same VPC.

### Networking

- **Ingress**: nginx ingress controller with a `LoadBalancer` Service holding a **static external IP**. This is the public entry point for all API traffic.
- **DNS**: `api.platform.example.com` points to the static IP. Managed by **external-dns** running in-cluster, syncing to a **Cloud DNS** managed zone.
- **Operator → GPU fleet**: Operators communicate with the external GPU fleet over a **Tailscale network**. A Tailscale subnet router advertises the cluster's pod CIDR to the tailnet so operators can reach GPU nodes directly.

### FluxCD Structure

The `flux-repo/` directory contains a simplified version of the production GitOps repo. Flux manages deployments from this repo. Take a look through the manifests before the interview.

---

## Prerequisites

- Docker
- [kind](https://kind.sigs.k8s.io/)
- kubectl
- [Flux CLI](https://fluxcd.io/flux/installation/#install-the-flux-cli)
- git
- A GitHub account with a [personal access token](https://github.com/settings/tokens) (classic token with `repo` scope is sufficient)

---

## Setup (complete before the interview)

Please work through these steps and make sure everything is running before we start. The whole process should take about 15 minutes.

### 1. Fork and clone

Fork this repository to your own GitHub account, then clone your fork:

```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
```

### 2. Build mock service images

```bash
./prep.sh
```

Verify:
```bash
docker images | grep mock-
```

You should see `mock-gateway:latest` and `mock-operator:latest`.

### 3. Create the Docker network

Both clusters will communicate through this shared network.

```bash
docker network create migration-net
```

### 4. Create the cluster

```bash
cat <<EOF | kind create cluster --name old-cluster --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  podSubnet: "10.244.0.0/16"
  serviceSubnet: "10.96.0.0/16"
nodes:
  - role: control-plane
  - role: worker
EOF

docker network connect migration-net old-cluster-control-plane
docker network connect migration-net old-cluster-worker
```

### 5. Load the mock service images

```bash
kind load docker-image mock-gateway:latest --name old-cluster
kind load docker-image mock-operator:latest --name old-cluster
```

### 6. Bootstrap FluxCD

This installs Flux and points it at your forked repo. Flux will deploy nginx ingress, gateway, and operator automatically.

```bash
export GITHUB_USER=<your-github-username>
export GITHUB_TOKEN=<your-personal-access-token>
export GITHUB_REPO=<repo-name>

flux bootstrap github \
  --owner=$GITHUB_USER \
  --repository=$GITHUB_REPO \
  --path=clusters/production \
  --branch=main \
  --personal \
  --interval=30s
```

Watch everything come up:

```bash
flux get kustomizations --watch
```

Wait until both `infrastructure` and `apps` show as `Ready`. The nginx ingress HelmRelease can take a couple of minutes to pull the chart.

```bash
kubectl get pods -A
```

All pods should be running.

### 7. Start the load balancer

This simulates the production load balancer / static IP entry point.

```bash
docker run -d \
  --name api-lb \
  --network migration-net \
  -p 8080:80 \
  -v $(pwd)/load-balancer/nginx.conf:/etc/nginx/nginx.conf:ro \
  nginx:1.29.6
```

### 8. Verify

```bash
curl http://localhost:8080/inference
curl http://localhost:8080/discovery
```

Both should return successful JSON responses. The inference response should include `"cluster": "old-cluster"`.

### 9. Start the traffic generator

In a separate terminal:

```bash
cd <repo-name>
./traffic/send-traffic.sh
```

You should see green lines with `[old-cluster]` in every request.

---

## Checklist

Come to the interview with all of the following:

- [ ] Docker running
- [ ] `old-cluster` kind cluster running with Flux, gateway, and operator deployed
- [ ] `api-lb` load balancer running
- [ ] Traffic script running in a separate terminal, showing green
- [ ] Your fork cloned locally and ready to edit and push

If anything isn't working, reach out and we'll help you debug before the interview.

**You do not need to prepare any solution yet.** We'll work through everything together.# flux-infra
