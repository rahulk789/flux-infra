#!/usr/bin/env bash
set -euo pipefail

echo "=== Building mock service images ==="
docker build -t mock-gateway:latest ./mock-services/gateway/
docker build -t mock-operator:latest ./mock-services/operator/

echo ""
echo "=== Done ==="
echo "Images built: mock-gateway:latest, mock-operator:latest"
