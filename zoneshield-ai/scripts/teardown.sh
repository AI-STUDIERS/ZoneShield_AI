#!/bin/bash
# ZoneShield AI - Automatic Teardown and Cost Guard Script
set -e

echo "=== ZoneShield AI Cloud Teardown & Cost Guard ==="
echo "Tearing down AWS infrastructure to prevent accidental credit expenditure..."

if [ -d "infra/terraform" ]; then
    cd infra/terraform
    if [ -f "terraform.tfstate" ]; then
        echo "Destroying Terraform resources..."
        terraform destroy -auto-approve
    else
        echo "No active Terraform state found."
    fi
    cd ../..
fi

echo "Stopping any lingering local Docker containers..."
docker compose down -v --remove-orphans || true

echo "=== Teardown Complete. Cloud resources cleared. ==="
