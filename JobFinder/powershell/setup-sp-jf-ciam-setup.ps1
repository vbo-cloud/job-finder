# ==============================================================================
# Setup — sp-jf-ciam-setup
# Service principal dédié aux appels Microsoft Graph sur le tenant Entra
# External ID depuis setup-entra-external-tenant.ps1.
#
# Permissions Graph applicatives accordées :
#   Application.ReadWrite.All    — app registrations + PATCH /applications
#   IdentityProvider.ReadWrite.All — identity providers (Google)
#   EventListener.ReadWrite.All  — user flows et associations
#
# Prérequis : az login avec un compte Global Admin sur le tenant Entra External
#             ID et un accès Owner/Contributor sur la subscription (pour le KV).
#
# Idempotent — peut être relancé sans risque si une étape a échoué.
# ==============================================================================

param(
    [Parameter(Mandatory)][string]$externalTenantId,
    [Parameter(Mandatory)][string]$subscriptionId,
    [Parameter(Mandatory)][string]$tenantId,
    [string]$keyVaultName = "kv-jf-dev-frc"
)

$setupAppName        = "sp-jf-ciam-setup"
$graphAppId          = "00000003-0000-0000-c000-000000000000"
$requiredPermissions = @(
    "Application.ReadWrite.All",
    "IdentityProvider.ReadWrite.All",
    "EventListener.ReadWrite.All"
)

# ==============================================================================
# Fonction utilitaire — appels Microsoft Graph avec fail-fast
# ==============================================================================

function Invoke-GraphRequest {
    param(
        [Parameter(Mandatory, Position = 0)][ValidateSet("GET","POST","PATCH","PUT","DELETE")][string]$Method,
        [Parameter(Mandatory, Position = 1)][string]$Url,
        [string]$Body = $null
    )
    $errFile = [System.IO.Path]::GetTempFileName()
    $raw     = $null
    try {
        if ($Body) {
            $bodyFile = [System.IO.Path]::GetTempFileName() + ".json"
            try {
                [System.IO.File]::WriteAllText($bodyFile, $Body, (New-Object System.Text.UTF8Encoding $false))
                $raw = az rest --method $Method --url $Url `
                    --body "@$bodyFile" --headers "Content-Type=application/json" `
                    --resource "https://graph.microsoft.com" 2>$errFile
            } finally {
                Remove-Item $bodyFile -ErrorAction SilentlyContinue
            }
        } else {
            $raw = az rest --method $Method --url $Url `
                --resource "https://graph.microsoft.com" 2>$errFile
        }
        if ($LASTEXITCODE -ne 0) {
            $errDetail = Get-Content $errFile -Raw -ErrorAction SilentlyContinue
            throw "Échec Graph $Method $Url (code $LASTEXITCODE) : $errDetail"
        }
    } finally {
        Remove-Item $errFile -ErrorAction SilentlyContinue
    }
    if (-not $raw) { return $null }  # 204 No Content
    $parsed = $raw | ConvertFrom-Json
    if ($parsed.error) {
        throw "Erreur Graph $Method $Url — $($parsed.error.code) : $($parsed.error.message)"
    }
    if ($null -ne $parsed.'@odata.error') {
        throw "Erreur Graph $Method $Url — $($parsed.'@odata.error'.code) : $($parsed.'@odata.error'.message.value)"
    }
    return $parsed
}

# ==============================================================================
# 0. Contexte subscription + vérification KV (avant de changer de tenant)
# ==============================================================================

Write-Host "Sélection de la subscription ($subscriptionId)..."
az account set --subscription $subscriptionId
if ($LASTEXITCODE -ne 0) {
    Write-Error "Impossible de sélectionner la subscription $subscriptionId — az login requis."
    exit 1
}

Write-Host "Vérification du secret dans Key Vault '$keyVaultName'..."
az keyvault secret show --vault-name $keyVaultName --name "ciam-setup-sp-secret" `
    --query "value" 2>$null | Out-Null
$kvSecretExists = ($LASTEXITCODE -eq 0)

# ==============================================================================
# 1. Authentification contre le tenant CIAM (Global Admin interactif)
# ==============================================================================

Write-Host ""
Write-Host "Authentification contre le tenant CIAM ($externalTenantId)..."
az login --tenant $externalTenantId --allow-no-subscriptions
if ($LASTEXITCODE -ne 0) {
    Write-Error "Authentification CIAM échouée."
    exit 1
}

# ==============================================================================
# 2. App registration sp-jf-ciam-setup (idempotent)
# ==============================================================================

Write-Host "Vérification de l'app registration '$setupAppName'..."
$existingApp = az ad app list --display-name $setupAppName --query "[0]" | ConvertFrom-Json
if ($null -ne $existingApp) {
    Write-Host "App '$setupAppName' existe déjà — récupération des IDs."
    $setupAppObjId = $existingApp.id
    $setupClientId = $existingApp.appId
} else {
    Write-Host "Création de l'app registration '$setupAppName'..."
    $setupApp = az ad app create --display-name $setupAppName --sign-in-audience AzureADMyOrg | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { Write-Error "Échec az ad app create '$setupAppName'." ; exit 1 }
    $setupAppObjId = $setupApp.id
    $setupClientId = $setupApp.appId
    Write-Host "App '$setupAppName' créée."
}

Write-Host "Client ID : $setupClientId"

# Service principal (idempotent — bloc séparé de la création de l'app pour
# garantir l'existence du SP même si l'app existait déjà sans SP)
Write-Host "Vérification du service principal '$setupAppName'..."
$existingSetupSP = az ad sp list --filter "appId eq '$setupClientId'" --query "[0]" | ConvertFrom-Json
if ($null -eq $existingSetupSP) {
    Write-Host "Création du service principal '$setupAppName'..."
    $setupSPResult = az ad sp create --id $setupClientId | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { Write-Error "Échec az ad sp create '$setupAppName'." ; exit 1 }
    $setupSPObjId = $setupSPResult.id
    Write-Host "Service principal créé."
} else {
    Write-Host "Service principal '$setupAppName' existe déjà — ignoré."
    $setupSPObjId = $existingSetupSP.id
}

Write-Host "SP Object ID : $setupSPObjId"

# ==============================================================================
# 3. Permissions Graph applicatives — admin consent (idempotent par permission)
# ==============================================================================

Write-Host "Récupération du service principal Microsoft Graph dans le tenant CIAM..."
$graphSPResult = Invoke-GraphRequest GET "https://graph.microsoft.com/v1.0/servicePrincipals?`$filter=appId eq '$graphAppId'"
if ($null -eq $graphSPResult -or $graphSPResult.value.Count -eq 0) {
    Write-Error "Service principal Microsoft Graph introuvable dans le tenant CIAM."
    exit 1
}
$graphSPObjId  = $graphSPResult.value[0].id
$graphAppRoles = $graphSPResult.value[0].appRoles

Write-Host "Récupération des assignations existantes de '$setupAppName'..."
$existingAssignments = Invoke-GraphRequest GET "https://graph.microsoft.com/v1.0/servicePrincipals/$setupSPObjId/appRoleAssignments"

foreach ($permName in $requiredPermissions) {
    $roleId = ($graphAppRoles | Where-Object {
        $_.value -eq $permName -and $_.allowedMemberTypes -contains "Application"
    }).id
    if ([string]::IsNullOrEmpty($roleId)) {
        Write-Error "Permission '$permName' introuvable dans les appRoles du SP Graph."
        exit 1
    }

    $alreadyAssigned = $existingAssignments.value | Where-Object {
        $_.appRoleId -eq $roleId -and $_.resourceId -eq $graphSPObjId
    }
    if ($null -ne $alreadyAssigned) {
        Write-Host "Permission '$permName' déjà accordée — ignorée."
        continue
    }

    Write-Host "Accord de la permission '$permName'..."
    # objet simple (trois propriétés) — ConvertTo-Json fiable ici
    $assignBody = @{
        principalId = $setupSPObjId
        resourceId  = $graphSPObjId
        appRoleId   = $roleId
    } | ConvertTo-Json

    try {
        Invoke-GraphRequest POST "https://graph.microsoft.com/v1.0/servicePrincipals/$setupSPObjId/appRoleAssignments" -Body $assignBody
        Write-Host "Permission '$permName' accordée."
    } catch {
        Write-Error @"
Échec admin consent pour '$permName'. Détail : $($_.Exception.Message)

L'admin consent via API nécessite AppRoleAssignment.ReadWrite.All dans le token.
Consentement manuel requis :
  1. Portail Azure : https://entra.microsoft.com (changer de tenant → $externalTenantId)
  2. Applications d'entreprise → $setupAppName → Autorisations
  3. Accorder le consentement administrateur pour $externalTenantId
  4. Relancer ce script.
"@
        exit 1
    }
}

# ==============================================================================
# 4. Client secret + écriture dans Key Vault (idempotent — skip si KV présent)
# ==============================================================================

if ($kvSecretExists) {
    Write-Host "Secret déjà présent dans '$keyVaultName' (ciam-setup-sp-secret) — génération ignorée."
    Write-Host "Pour régénérer : supprimer le secret KV 'ciam-setup-sp-secret' et relancer ce script."
} else {
    Write-Host "Génération d'un client secret (valable 2 ans)..."
    $secretResult = az ad app credential reset --id $setupAppObjId --years 2 --append | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { Write-Error "Échec az ad app credential reset '$setupAppName'." ; exit 1 }
    $setupSecret = $secretResult.password

    Write-Host "Retour au contexte subscription pour écriture dans Key Vault..."
    az account set --subscription $subscriptionId 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "az account set a échoué — re-login tenant home ($tenantId)..."
        az login --tenant $tenantId --allow-no-subscriptions
        az account set --subscription $subscriptionId
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Impossible de revenir au contexte subscription $subscriptionId."
            Write-Warning "Secret généré mais non écrit dans KV. Écrire manuellement :"
            Write-Warning "  az keyvault secret set --vault-name $keyVaultName --name ciam-setup-sp-client-id --value $setupClientId"
            Write-Warning "  az keyvault secret set --vault-name $keyVaultName --name ciam-setup-sp-secret --value '<secret>'"
            exit 1
        }
    }

    Write-Host "Écriture dans '$keyVaultName'..."
    az keyvault secret set --vault-name $keyVaultName --name "ciam-setup-sp-client-id" `
        --value $setupClientId --output none
    if ($LASTEXITCODE -ne 0) { Write-Error "Échec écriture 'ciam-setup-sp-client-id'." ; exit 1 }
    az keyvault secret set --vault-name $keyVaultName --name "ciam-setup-sp-secret" `
        --value $setupSecret --output none
    if ($LASTEXITCODE -ne 0) { Write-Error "Échec écriture 'ciam-setup-sp-secret'." ; exit 1 }
    Write-Host "Credentials écrits dans '$keyVaultName'."
}

# ==============================================================================
# 5. Résumé
# ==============================================================================

Write-Host ""
Write-Host "sp-jf-ciam-setup configuré."
Write-Host "  External Tenant ID : $externalTenantId"
Write-Host "  Client ID          : $setupClientId"
Write-Host "  Secret             : dans $keyVaultName (ciam-setup-sp-secret) — non affiché"
Write-Host "  Permissions Graph  : $($requiredPermissions -join ', ')"
Write-Host ""
Write-Host "Prochaine étape :"
Write-Host "  ./setup-entra-external-tenant.ps1 -subscriptionId <id> -tenantId <id> -resourceGroupName <rg> ``"
Write-Host "      -googleClientId <id> -googleClientSecret <secret>"
