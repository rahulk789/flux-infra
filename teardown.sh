#!/usr/bin/env bash
set -euo pipefail

kind delete cluster --name old-cluster 2>/dev/null || true
kind delete cluster --name new-cluster 2>/dev/null || true
docker rm -f api-lb 2>/dev/null || true
docker network rm migration-net 2>/dev/null || true
rm -rf working-repo

echo "Cleaned up."
