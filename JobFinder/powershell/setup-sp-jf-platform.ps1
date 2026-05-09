# ==============================================================================
# Setup — sp-jf-platform
# Service principal dédié à la gouvernance des landing zones.
# Droits : RBAC Administrator (conditionné aux rôles non-privilégiés) +
#          Resource Policy Contributor + Blob Data Contributor sur lz-tfstates.
#
# Idempotent — peut être relancé sans risque si une étape a échoué.
# ==============================================================================

$subscriptionId = "58ccbf27-c35f-42ea-838b-3dbe9ce60fc6"
$tenantId       = "0cca9098-1181-4b2e-bd1a-cba23f4f314b"
$appName        = "sp-jf-platform"
$repoFullName   = "vbo-cloud/job-finder"
$rgTfstate      = "rg-jf-tfstate-frc"
$storageAccount = "stjftfstatefrc"
$lzContainer    = "lz-tfstates"

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

Write-Host "Client ID (AZURE_PLATFORM_CLIENT_ID) : $appId"
Write-Host "SP Object ID                          : $spObjId"

# ==============================================================================
# 2. Federated Credentials OIDC (idempotent)
# PowerShell mange le JSON si on le pipe directement — passage par fichier temporaire.
# ==============================================================================

$existingCreds = az ad app federated-credential list --id $appObjId | ConvertFrom-Json
$credNames     = $existingCreds | ForEach-Object { $_.name }

# plan — déclenché par pull_request, pas d'environnement GitHub
if ($credNames -notcontains "github-pr") {
    $tmpFile = [System.IO.Path]::GetTempFileName() + ".json"
    @{ name = "github-pr"; issuer = "https://token.actions.githubusercontent.com"; subject = "repo:${repoFullName}:pull_request"; audiences = @("api://AzureADTokenExchange") } | ConvertTo-Json | Set-Content $tmpFile
    az ad app federated-credential create --id $appObjId --parameters "@$tmpFile"
    Remove-Item $tmpFile
    Write-Host "Federated credential 'github-pr' créé."
} else {
    Write-Host "Federated credential 'github-pr' existe déjà — ignoré."
}

# apply lz_dev — environnement GitHub "dev"
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
# 3. Role Assignments
# az role assignment create est idempotent — ignoré si le rôle existe déjà.
# ==============================================================================

# Storage Blob Data Contributor — container lz-tfstates uniquement (pas app-tfstates)
$containerScope = "/subscriptions/$subscriptionId" +
    "/resourceGroups/$rgTfstate" +
    "/providers/Microsoft.Storage/storageAccounts/$storageAccount" +
    "/blobServices/default/containers/$lzContainer"

az role assignment create `
    --assignee $spObjId `
    --role     "Storage Blob Data Contributor" `
    --scope    $containerScope

# RBAC Administrator (subscription) — conditionné aux rôles non-privilégiés.
# Passé via az rest + fichier JSON pour contourner les limitations de quoting PowerShell + CLI az.
# Exclut Owner (8e3af657), User Access Administrator (18d7d88d)
# et Role Based Access Control Administrator (f58310d9) des actions write et delete.
$rbacAdminRoleId  = "f58310d9-a9f6-439a-9e8d-f62e7b41a168"
$roleAssignmentId = [System.Guid]::NewGuid().ToString()
$raUrl = "https://management.azure.com/subscriptions/$subscriptionId/providers/Microsoft.Authorization/roleAssignments/${roleAssignmentId}?api-version=2022-04-01"

$condition = "((!(ActionMatches{'Microsoft.Authorization/roleAssignments/write'})) OR (@Request[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAllValues:GuidNotEquals {8e3af657-a8ff-443c-a75c-2fe8c4bcb635, 18d7d88d-d35e-4fb5-a5c3-7773c20a72d9, f58310d9-a9f6-439a-9e8d-f62e7b41a168})) AND ((!(ActionMatches{'Microsoft.Authorization/roleAssignments/delete'})) OR (@Resource[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAllValues:GuidNotEquals {8e3af657-a8ff-443c-a75c-2fe8c4bcb635, 18d7d88d-d35e-4fb5-a5c3-7773c20a72d9, f58310d9-a9f6-439a-9e8d-f62e7b41a168}))"

$raBodyJson = @{
    properties = @{
        roleDefinitionId = "/subscriptions/$subscriptionId/providers/Microsoft.Authorization/roleDefinitions/$rbacAdminRoleId"
        principalId      = $spObjId
        principalType    = "ServicePrincipal"
        conditionVersion = "2.0"
        condition        = $condition
    }
} | ConvertTo-Json -Depth 5

$tmpFile = [System.IO.Path]::GetTempFileName() + ".json"
# UTF8 sans BOM — Set-Content -Encoding UTF8 ajoute un BOM en PowerShell 5 ce qui casse az rest
[System.IO.File]::WriteAllText($tmpFile, $raBodyJson, (New-Object System.Text.UTF8Encoding $false))
az rest --method PUT --url $raUrl --body "@$tmpFile" --headers "Content-Type=application/json"
Remove-Item $tmpFile

# Resource Policy Contributor (subscription) — création et assignation de policies Azure
az role assignment create `
    --assignee $spObjId `
    --role     "Resource Policy Contributor" `
    --scope    "/subscriptions/$subscriptionId"

# ==============================================================================
# 4. Résumé
# ==============================================================================

Write-Host ""
Write-Host "sp-jf-platform configuré."
Write-Host ""
Write-Host "Valeurs Azure à conserver :"
Write-Host "  Subscription ID : $subscriptionId"
Write-Host "  Tenant ID       : $tenantId"
Write-Host "  Client ID       : $appId"
Write-Host "  SP Object ID    : $spObjId"
Write-Host ""
Write-Host "Ajouter dans les variables GitHub du dépôt (Settings > Secrets and variables > Actions) :"
Write-Host "  AZURE_PLATFORM_CLIENT_ID = $appId"
Write-Host "  AZURE_TENANT_ID          = $tenantId          (si pas déjà présent)"
Write-Host "  AZURE_SUBSCRIPTION_ID    = $subscriptionId    (si pas déjà présent)"
