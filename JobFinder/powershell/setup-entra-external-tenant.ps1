# ==============================================================================
# Setup — Microsoft Entra External ID tenant + App Registration FastAPI
# Crée le tenant CIAM "jobfinderapp" via ARM (Microsoft.AzureActiveDirectory/
# ciamDirectories) et l'app registration FastAPI dans ce tenant via Graph.
#
# Prérequis : az login avec un compte Owner sur la subscription, autorisé
#             à créer des tenants Entra External ID.
#
# Idempotent — peut être relancé sans risque si une étape a échoué.
# ==============================================================================

# Valeurs disponibles dans : portail Azure → Subscriptions /
param(
    [Parameter(Mandatory)][string]$subscriptionId,
    [Parameter(Mandatory)][string]$tenantId,
    [Parameter(Mandatory)][string]$resourceGroupName
)

$domainName  = "jobfinderapp"
$displayName = "jobfinderapp"
$countryCode = "FR"
$appName     = "fastapi-jobfinder"

az account set --subscription $subscriptionId

# ==============================================================================
# 1. Tenant Microsoft Entra External ID (idempotent)
# ==============================================================================

$ciamUrl = "https://management.azure.com/subscriptions/$subscriptionId" +
           "/resourceGroups/$resourceGroupName" +
           "/providers/Microsoft.AzureActiveDirectory/ciamDirectories/${domainName}" +
           "?api-version=2023-05-17-preview"

Write-Host "Vérification du tenant '$domainName'..."
$existingTenant = az rest --method GET --url $ciamUrl 2>$null | ConvertFrom-Json

if ($null -ne $existingTenant -and $null -ne $existingTenant.properties.tenantId) {
    Write-Host "Tenant '$domainName' existe déjà — récupération du Tenant ID."
    $externalTenantId = $existingTenant.properties.tenantId
} else {
    Write-Host "Création du tenant '$domainName'..."

    $body = @{
        location   = "Europe"
        sku        = @{ name = "PremiumP1"; tier = "A0" }
        properties = @{
            createTenantProperties = @{
                displayName = $displayName
                countryCode = $countryCode
            }
        }
    } | ConvertTo-Json -Depth 5

    $tmpFile = [System.IO.Path]::GetTempFileName() + ".json"
    # UTF8 sans BOM — Set-Content -Encoding UTF8 ajoute un BOM en PowerShell 5 ce qui casse az rest
    [System.IO.File]::WriteAllText($tmpFile, $body, (New-Object System.Text.UTF8Encoding $false))
    az rest --method PUT --url $ciamUrl --body "@$tmpFile" --headers "Content-Type=application/json"
    Remove-Item $tmpFile

    # La création de tenant est asynchrone côté Azure — attendre avant de lire le tenantId
    Write-Host "Tenant en cours de création. Attente de la propagation (60s)..."
    Start-Sleep -Seconds 60

    $createdTenant    = az rest --method GET --url $ciamUrl | ConvertFrom-Json
    $externalTenantId = $createdTenant.properties.tenantId
    Write-Host "Tenant créé."
}

Write-Host "External Tenant ID (ENTRA_EXTERNAL_TENANT_ID) : $externalTenantId"

# ==============================================================================
# 2. App Registration FastAPI dans le tenant Entra External ID (idempotent)
# Requiert une authentification contre le tenant jobfinderapp — az login
# ouvre une fenêtre de connexion interactive.
# ==============================================================================

Write-Host ""
Write-Host "Authentification contre le tenant Entra External ID ($externalTenantId)..."
az login --tenant $externalTenantId --allow-no-subscriptions

$existingApp = az ad app list --display-name $appName --query "[0]" | ConvertFrom-Json
if ($null -ne $existingApp) {
    Write-Host "App Registration '$appName' existe déjà — récupération des IDs."
    $appObjId = $existingApp.id
    $appId    = $existingApp.appId
} else {
    Write-Host "Création de l'App Registration '$appName'..."
    $app      = az ad app create `
        --display-name     $appName `
        --sign-in-audience AzureADMyOrg `
        | ConvertFrom-Json
    $appObjId = $app.id
    $appId    = $app.appId
    Write-Host "App Registration '$appName' créée."
}

Write-Host "Client ID (ENTRA_EXTERNAL_CLIENT_ID) : $appId"

# ==============================================================================
# 3. Scopes openid / profile / email
# Built-in dans toute App Registration Entra — aucune configuration requise.
# ==============================================================================

Write-Host "Scopes openid / profile / email : built-in OIDC, aucune action requise."

# ==============================================================================
# 4. Client secret
# --append : ajoute un nouveau secret sans invalider les secrets existants.
# Chaque exécution génère un secret supplémentaire — stocker la valeur immédiatement.
# ==============================================================================

Write-Host "Génération d'un client secret (valable 2 ans)..."
$secretResult = az ad app credential reset `
    --id     $appObjId `
    --years  2 `
    --append `
    | ConvertFrom-Json
$clientSecret = $secretResult.password
Write-Host "Client secret généré."

# ==============================================================================
# 5. Résumé — valeurs à stocker dans Key Vault (kv-jf-dev-frc)
# ==============================================================================

Write-Host ""
Write-Host "Entra External ID configuré."
Write-Host ""
Write-Host "Stocker dans kv-jf-dev-frc :"
Write-Host "  entra-external-tenant-id     = $externalTenantId"
Write-Host "  entra-external-client-id     = $appId"
Write-Host "  entra-external-client-secret = $clientSecret"
Write-Host ""
Write-Host "Variables d'environnement correspondantes :"
Write-Host "  ENTRA_EXTERNAL_TENANT_ID     = $externalTenantId"
Write-Host "  ENTRA_EXTERNAL_CLIENT_ID     = $appId"
Write-Host "  ENTRA_EXTERNAL_CLIENT_SECRET = $clientSecret"
