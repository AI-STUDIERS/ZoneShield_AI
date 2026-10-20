# ZoneShield AI - Automatic Teardown & Cost Guard (PowerShell)
Write-Host "=== ZoneShield AI Cloud Teardown & Cost Guard ===" -ForegroundColor Cyan
Write-Host "Tearing down AWS infrastructure to prevent accidental credit expenditure..."

if (Test-Path "infra/terraform") {
    Push-Location "infra/terraform"
    if (Test-Path "terraform.tfstate") {
        Write-Host "Destroying Terraform resources..." -ForegroundColor Yellow
        terraform destroy -auto-approve
    } else {
        Write-Host "No active Terraform state found."
    }
    Pop-Location
}

Write-Host "Stopping local Docker containers..."
docker compose down -v --remove-orphans 2>$null

Write-Host "=== Teardown Complete. Cloud resources cleared. ===" -ForegroundColor Green
