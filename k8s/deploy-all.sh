#!/usr/bin/env bash
set -e

# Usage: ./k8s/deploy-all.sh <dockerhub-username> <dockerhub-token>
DOCKERHUB_USER="${1:-$DOCKERHUB_USER}"
DOCKERHUB_TOKEN="${2:-$DOCKERHUB_TOKEN}"

if [ -z "$DOCKERHUB_USER" ] || [ -z "$DOCKERHUB_TOKEN" ]; then
  echo "Usage: $0 <dockerhub-username> <dockerhub-token>"
  echo "Or set DOCKERHUB_USER and DOCKERHUB_TOKEN environment variables."
  exit 1
fi

export DOCKERHUB_USER

echo "====================================================="
echo " Deploying online-quiz-python across qa, stage, prod"
echo " Docker Hub User: $DOCKERHUB_USER"
echo "====================================================="

# Step 1: Create the three namespaces
echo "[Step 1] Creating namespaces (qa, stage, prod)..."
for ns in qa stage prod; do
  kubectl create namespace $ns --dry-run=client -o yaml | kubectl apply -f -
done

# Step 2: Create Docker Hub pull secrets in each namespace
echo "[Step 2] Creating Docker Hub pull secrets..."
for ns in qa stage prod; do
  kubectl create secret docker-registry dockerhub \
    --docker-username="$DOCKERHUB_USER" \
    --docker-password="$DOCKERHUB_TOKEN" \
    -n $ns --dry-run=client -o yaml | kubectl apply -f -
done

# Step 3: Deploy to each namespace with its respective tag
echo "[Step 3] Deploying manifests with respective tags..."
for pair in qa:qa stage:stage prod:prod; do
  ns=${pair%%:*}
  tag=${pair##*:}
  echo "  --> Applying to namespace '$ns' with tag ':$tag'..."
  kubectl apply -f k8s/postgres.yaml -n $ns
  kubectl apply -f k8s/redis.yaml -n $ns
  TAG=$tag envsubst < k8s/app.yaml | kubectl apply -n $ns -f -
done

echo ""
echo "====================================================="
echo " Deployment applied successfully!"
echo " Verifying QA status:"
echo " kubectl get pods,svc -n qa"
echo "====================================================="
