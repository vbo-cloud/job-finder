# ==============================================================================
# Setup — sp-jf-github
# Service principal applicatif pour la CI/CD GitHub Actions (couche app).
# Les role assignments sont gérés par sp-jf-platform via lz_dev/rbac.tf.
# Exception : Storage Blob Data Contributor sur app-tfstates est posé ici
# comme bootstrap one-shot — sans lui, terraform init échoue sur dev avant
# que lz_dev/rbac.tf ait pu s'appliquer (dépendance circulaire).
# ==============================================================================

$subscriptionId = "58ccbf27-c35f-42ea-838b-3dbe9ce60fc6"
$tenantId       = "0cca9098-1181-4b2e-bd1a-cba23f4f314b"
$appName        = "sp-jf-github"
$repoFullName   = "vbo-cloud/job-finder"

az account set --subscription $subscriptionId

# ==============================================================================
# 1. App Registration + Service Principal (idempotent)
# ==============================================================================

$existingApp = az ad app list --display-name $appName --query "[0]" | ConvertFrom-Json
if ($null -ne $existingApp) {
    Write-Host "App Registration '$appName' existe déjà — récupération des IDs."
    $appObjId = $existingApp.id
    $appId    = $existingApp.appId
} else {
    $app      = az ad app create --display-name $appName | ConvertFrom-Json
    $appObjId = $app.id
    $appId    = $app.appId
    Write-Host "App Registration créée."
}

$existingSp = az ad sp list --filter "appId eq '$appId'" --query "[0]" | ConvertFrom-Json
if ($null -ne $existingSp) {
    Write-Host "Service Principal existe déjà — récupération de l'Object ID."
    $spObjId = $existingSp.id
} else {
    $sp      = az ad sp create --id $appId | ConvertFrom-Json
    $spObjId = $sp.id
    Write-Host "Service Principal créé."
}

Write-Host "Client ID (AZURE_CLIENT_ID) : $appId"
Write-Host "SP Object ID               : $spObjId"

# ==============================================================================
# 2. Federated Credentials OIDC (idempotent)
# PowerShell mange le JSON si on le pipe directement — passage par fichier temporaire.
# ==============================================================================

$existingCreds = az ad app federated-credential list --id $appObjId | ConvertFrom-Json
$credNames     = $existingCreds | ForEach-Object { $_.name }

# plan dev — job matrix sans environnement GitHub, déclenché par pull_request
if ($credNames -notcontains "github-pr") {
    $tmpFile = [System.IO.Path]::GetTempFileName() + ".json"
    @{ name = "github-pr"; issuer = "https://token.actions.githubusercontent.com"; subject = "repo:${repoFullName}:pull_request"; audiences = @("api://AzureADTokenExchange") } | ConvertTo-Json | Set-Content $tmpFile
    az ad app federated-credential create --id $appObjId --parameters "@$tmpFile"
    Remove-Item $tmpFile
    Write-Host "Federated credential 'github-pr' créé."
} else {
    Write-Host "Federated credential 'github-pr' existe déjà — ignoré."
}

# apply-dev — environnement GitHub "dev"
if ($credNames -notcontains "github-dev") {
    $tmpFile = [System.IO.Path]::GetTempFileName() + ".json"
    @{ name = "github-dev"; issuer = "https://token.actions.githubusercontent.com"; subject = "repo:${repoFullName}:environment:dev"; audiences = @("api://AzureADTokenExchange") } | ConvertTo-Json | Set-Content $tmpFile
    az ad app federated-credential create --id $appObjId --parameters "@$tmpFile"
    Remove-Item $tmpFile
    Write-Host "Federated credential 'github-dev' créé."
} else {
    Write-Host "Federated credential 'github-dev' existe déjà — ignoré."
}

# ==============================================================================
# 3. Bootstrap — rôles minimaux avant le premier apply lz_dev
# Sans ces rôles, terraform plan dev échoue (dépendance circulaire) :
# sp-jf-github a besoin de lire les ressources LZ, mais ses rôles viennent
# de lz_dev/rbac.tf qui n'est pas encore appliqué.
# Une fois lz_dev appliqué, rbac.tf gère tous ces rôles de façon permanente.
# ==============================================================================

# Storage Blob Data Contributor sur app-tfstates — permet terraform init (dev)
$appTfstateScope = "/subscriptions/$subscriptionId" +
    "/resourceGroups/rg-jf-tfstate-frc" +
    "/providers/Microsoft.Storage/storageAccounts/stjftfstatefrc" +
    "/blobServices/default/containers/app-tfstates"

az role assignment create `
    --assignee $spObjId `
    --role     "Storage Blob Data Contributor" `
    --scope    $appTfstateScope

# Contributor subscription — permet terraform plan dev (lecture des ressources LZ)
az role assignment create `
    --assignee $spObjId `
    --role     "Contributor" `
    --scope    "/subscriptions/$subscriptionId"

# ==============================================================================
# 4. Résumé
# ==============================================================================

Write-Host ""
Write-Host "sp-jf-github configuré (identité uniquement — rôles assignés par sp-jf-platform via lz_dev/rbac.tf)."
Write-Host ""
Write-Host "Valeurs Azure à conserver :"
Write-Host "  Subscription ID : $subscriptionId"
Write-Host "  Tenant ID       : $tenantId"
Write-Host "  Client ID       : $appId"
Write-Host "  SP Object ID    : $spObjId"
Write-Host ""
Write-Host "Ajouter dans les variables GitHub du dépôt (Settings > Secrets and variables > Actions) :"
Write-Host "  AZURE_CLIENT_ID      = $appId"
Write-Host "  SP_GITHUB_OBJECT_ID  = $spObjId"
