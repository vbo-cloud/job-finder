# ==============================================================================
# Setup — Microsoft Entra External ID tenant + App Registration FastAPI + SPA
# Crée le tenant CIAM "jobfinderapp" via ARM (Microsoft.AzureActiveDirectory/
# ciamDirectories), l'app registration FastAPI, le scope access_as_user,
# le user flow susi et le Google Identity Provider via Microsoft Graph.
#
# Prérequis :
#   1. az login avec un compte Owner sur la subscription (sections ARM).
#   2. setup-sp-jf-ciam-setup.ps1 exécuté au préalable — crée sp-jf-ciam-setup
#      avec les permissions Graph applicatives et écrit ses credentials dans KV.
#
# Idempotent — peut être relancé sans risque si une étape a échoué.
# ==============================================================================

# Valeurs disponibles dans : portail Azure → Subscriptions /
# Google credentials : console.developers.google.com → Credentials
param(
    [Parameter(Mandatory)][string]$subscriptionId,
    [Parameter(Mandatory)][string]$tenantId,
    [Parameter(Mandatory)][string]$resourceGroupName,
    [Parameter(Mandatory)][string]$googleClientId,
    [Parameter(Mandatory)][string]$googleClientSecret,
    # Redirect URIs de la plateforme SPA (frontend Next.js). Paramétrable pour
    # ajouter l'URL du Container App plus tard sans modifier le script.
    [string[]]$spaRedirectUris = @("http://localhost:3000")
)

$domainName   = "jobfinderapp"
$displayName  = "jobfinderapp"
$countryCode  = "FR"
$appName      = "fastapi-jobfinder"
$spaAppName   = "spa-jobfinder"
$keyVaultName = "kv-jf-dev-frc"

az account set --subscription $subscriptionId

# ==============================================================================
# Fonction utilitaire — appels Microsoft Graph avec fail-fast
# Toutes les erreurs (code retour non nul, champ .error, .@odata.error)
# lèvent une exception immédiatement. Stderr est capturé pour inclusion dans
# le message d'erreur afin de faciliter le diagnostic.
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
    if (-not $raw) { return $null }  # 204 No Content (PATCH sur applications)
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
# 1. Tenant Microsoft Entra External ID (idempotent)
# ==============================================================================

# Nom de ressource ARM du tenant CIAM : Azure nomme la ressource d'après le
# domaine initial complet ("$domainName.onmicrosoft.com"), PAS d'après
# $domainName seul. $domainName reste "jobfinderapp" pour l'autorité ciamlogin
# (jobfinderapp.ciamlogin.com) — seule la résolution de la ressource ARM ajoute
# le suffixe ".onmicrosoft.com".
$ciamDomain = "$domainName.onmicrosoft.com"
$emptyGuid  = "00000000-0000-0000-0000-000000000000"

$ciamResourceUrl = "https://management.azure.com/subscriptions/$subscriptionId" +
                   "/resourceGroups/$resourceGroupName" +
                   "/providers/Microsoft.AzureActiveDirectory/ciamDirectories/$ciamDomain" +
                   "?api-version=2023-05-17-preview"
$ciamListUrl     = "https://management.azure.com/subscriptions/$subscriptionId" +
                   "/resourceGroups/$resourceGroupName" +
                   "/providers/Microsoft.AzureActiveDirectory/ciamDirectories" +
                   "?api-version=2023-05-17-preview"

# Détection robuste : on LISTE les ciamDirectories du resource group et on
# retrouve l'existant via properties.domainName. Un GET direct sur un nom de
# ressource supposé ("$domainName" sans suffixe) renvoyait 404 sur le tenant
# réel ("$domainName.onmicrosoft.com"), faisant entrer le script en création
# et dupliquant le tenant.
Write-Host "Vérification du tenant '$ciamDomain' dans '$resourceGroupName'..."
$ciamList       = az rest --method GET --url $ciamListUrl 2>$null | ConvertFrom-Json
$existingTenant = $ciamList.value | Where-Object { $_.properties.domainName -eq $ciamDomain } | Select-Object -First 1

if ($null -eq $existingTenant) {
    Write-Host "Aucun tenant '$ciamDomain' trouvé — création..."

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
    az rest --method PUT --url $ciamResourceUrl --body "@$tmpFile" --headers "Content-Type=application/json"
    Remove-Item $tmpFile
} else {
    Write-Host "Tenant '$ciamDomain' existe déjà — récupération du Tenant ID."
}

# Récupération du tenantId — polling robuste (re-list + match sur domainName).
# La création est asynchrone et, pendant le provisioning, l'API renvoie le GUID
# tout-à-zéro ($emptyGuid) : on le considère comme « pas prêt » et on continue
# le polling jusqu'à un vrai GUID. Pour un tenant déjà prêt (existant), la 1re
# itération retourne immédiatement le bon tenantId, sans attente.
$externalTenantId = $null
$maxAttempts      = 18  # 3 minutes max
$attempt          = 0
while ($attempt -lt $maxAttempts -and $null -eq $externalTenantId) {
    $attempt++
    $polledList  = az rest --method GET --url $ciamListUrl 2>$null | ConvertFrom-Json
    $polledMatch = $polledList.value | Where-Object { $_.properties.domainName -eq $ciamDomain } | Select-Object -First 1
    $polledId    = $polledMatch.properties.tenantId
    if (-not [string]::IsNullOrEmpty($polledId) -and $polledId -ne $emptyGuid) {
        $externalTenantId = $polledId
    } else {
        Write-Host "Attente de la propagation du tenant ($attempt/$maxAttempts)..."
        Start-Sleep -Seconds 10
    }
}
if ($null -eq $externalTenantId) {
    Write-Error "Tenant '$ciamDomain' : aucun tenantId valide après $maxAttempts tentatives — relancer le script."
    exit 1
}

Write-Host "External Tenant ID (ENTRA_EXTERNAL_TENANT_ID) : $externalTenantId"

# ==============================================================================
# 1-bis. Authentification SP Graph contre le tenant CIAM
# sp-jf-ciam-setup porte les permissions Graph applicatives
# (Application.ReadWrite.All, IdentityProvider.ReadWrite.All,
# EventListener.ReadWrite.All) nécessaires aux sections 2–12.
# Prérequis : setup-sp-jf-ciam-setup.ps1 exécuté au préalable.
# ==============================================================================

Write-Host ""
Write-Host "Lecture des credentials sp-jf-ciam-setup depuis '$keyVaultName'..."
$ciamSpClientId = az keyvault secret show --vault-name $keyVaultName `
    --name "ciam-setup-sp-client-id" --query "value" -o tsv 2>$null
$ciamSpSecret   = az keyvault secret show --vault-name $keyVaultName `
    --name "ciam-setup-sp-secret" --query "value" -o tsv 2>$null

if ([string]::IsNullOrEmpty($ciamSpClientId) -or [string]::IsNullOrEmpty($ciamSpSecret)) {
    Write-Error @"
Credentials sp-jf-ciam-setup introuvables dans '$keyVaultName'.
Prérequis : exécuter d'abord setup-sp-jf-ciam-setup.ps1 :
  ./setup-sp-jf-ciam-setup.ps1 ``
      -externalTenantId $externalTenantId ``
      -subscriptionId $subscriptionId ``
      -tenantId $tenantId
"@
    exit 1
}

Write-Host "Authentification contre le tenant CIAM via sp-jf-ciam-setup ($ciamSpClientId)..."
az login --service-principal `
    --username $ciamSpClientId `
    --password $ciamSpSecret `
    --tenant   $externalTenantId `
    --allow-no-subscriptions
if ($LASTEXITCODE -ne 0) {
    Write-Error "Authentification SP échouée — vérifier les credentials dans '$keyVaultName' (ciam-setup-sp-secret)."
    exit 1
}

# ==============================================================================
# 2. App Registration FastAPI dans le tenant Entra External ID (idempotent)
# ==============================================================================

Write-Host ""
$existingApp = az ad app list --display-name $appName --query "[0]" | ConvertFrom-Json
if ($null -ne $existingApp) {
    Write-Host "App Registration '$appName' existe déjà — récupération des IDs."
    $appObjId = $existingApp.id
    $appId    = $existingApp.appId
} else {
    Write-Host "Création de l'App Registration '$appName'..."
    $app = az ad app create `
        --display-name     $appName `
        --sign-in-audience AzureADMyOrg `
        | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { Write-Error "Échec az ad app create '$appName'." ; exit 1 }
    $appObjId = $app.id
    $appId    = $app.appId
    Write-Host "App Registration '$appName' créée."
}

# Service principal (idempotent — bloc séparé de la création de l'app pour
# garantir l'existence du SP même si l'app existait déjà sans SP)
Write-Host "Vérification du service principal '$appName'..."
$existingAppSP = az ad sp list --filter "appId eq '$appId'" --query "[0]" | ConvertFrom-Json
if ($null -eq $existingAppSP) {
    Write-Host "Création du service principal '$appName'..."
    az ad sp create --id $appId | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error "Échec az ad sp create '$appName'." ; exit 1 }
    Write-Host "Service principal '$appName' créé."
} else {
    Write-Host "Service principal '$appName' existe déjà — ignoré."
}

Write-Host "Client ID (ENTRA_EXTERNAL_CLIENT_ID) : $appId"

# ==============================================================================
# 3. Scopes openid / profile / email
# Built-in dans toute App Registration Entra — aucune configuration requise.
# ==============================================================================

Write-Host "Scopes openid / profile / email : built-in OIDC, aucune action requise."

# ==============================================================================
# 4. Client secret (idempotent — génère uniquement si aucun secret valide n'existe)
# ==============================================================================

Write-Host "Vérification des secrets existants..."
$now         = [datetime]::UtcNow
$credentials = az ad app credential list --id $appObjId | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { Write-Error "Échec az ad app credential list '$appName'." ; exit 1 }
$validSecret = @($credentials | Where-Object { [datetime]$_.endDateTime -gt $now })

if ($validSecret.Count -gt 0) {
    Write-Host "Secret valide existant (expire le $($validSecret[0].endDateTime)) — génération ignorée."
    Write-Host "⚠️  La valeur n'est pas récupérable — utiliser le secret déjà stocké dans $keyVaultName."
    $clientSecret = "<secret existant — voir $keyVaultName : entra-external-client-secret>"
} else {
    Write-Host "Aucun secret valide — génération d'un client secret (valable 2 ans)..."
    $secretResult = az ad app credential reset `
        --id     $appObjId `
        --years  2 `
        --append `
        | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { Write-Error "Échec az ad app credential reset '$appName'." ; exit 1 }
    $clientSecret = $secretResult.password
    Write-Host "Client secret généré."
}

# ==============================================================================
# 5. Scope access_as_user (idempotent)
# PATCH Graph — ajoute le scope custom uniquement s'il n'existe pas déjà.
# ==============================================================================

Write-Host "Vérification du scope 'access_as_user'..."
$appDetails     = Invoke-GraphRequest GET "https://graph.microsoft.com/v1.0/applications/$appObjId"
$existingScopes = $appDetails.api.oauth2PermissionScopes
$scopeExists    = $existingScopes | Where-Object { $_.value -eq "access_as_user" }

if ($null -ne $scopeExists) {
    Write-Host "Scope 'access_as_user' existe déjà — ignoré."
} else {
    Write-Host "Création du scope 'access_as_user'..."
    $scopeId = [System.Guid]::NewGuid().ToString()
    $body = @{
        api = @{
            oauth2PermissionScopes = @(@{
                id                      = $scopeId
                adminConsentDescription = "Allows the app to access job-finder on behalf of the signed-in user"
                adminConsentDisplayName = "Access job-finder as user"
                userConsentDescription  = "Allows the app to access job-finder on behalf of the signed-in user"
                userConsentDisplayName  = "Access job-finder as user"
                isEnabled               = $true
                type                    = "User"
                value                   = "access_as_user"
            })
        }
    } | ConvertTo-Json -Depth 5
    Invoke-GraphRequest PATCH "https://graph.microsoft.com/v1.0/applications/$appObjId" -Body $body
    Write-Host "Scope 'access_as_user' créé (ID : $scopeId)."
}

# ==============================================================================
# 6. User flow susi (idempotent)
# ==============================================================================

Write-Host "Vérification du user flow 'susi'..."
$flowsResult = Invoke-GraphRequest GET "https://graph.microsoft.com/beta/identity/authenticationEventsFlows?`$filter=displayName eq 'susi'"

if ($flowsResult.value.Count -gt 0) {
    Write-Host "User flow 'susi' existe déjà — récupération de l'ID."
    $flowId = $flowsResult.value[0].id
} else {
    Write-Host "Création du user flow 'susi'..."
    $body = @{
        "@odata.type" = "#microsoft.graph.externalUsersSelfServiceSignUpEventsFlow"
        displayName   = "susi"
        onAuthenticationMethodLoadStart = @{
            "@odata.type"     = "#microsoft.graph.onAuthenticationMethodLoadStartExternalUsersSelfServiceSignUp"
            identityProviders = @(@{ id = "EmailPassword-OAUTH" })
        }
        onInteractiveAuthFlowStart = @{
            "@odata.type"   = "#microsoft.graph.onInteractiveAuthFlowStartExternalUsersSelfServiceSignUp"
            isSignUpAllowed = $true
        }
        onAttributeCollection = @{
            "@odata.type" = "#microsoft.graph.onAttributeCollectionExternalUsersSelfServiceSignUp"
            attributes    = @(@{ id = "email" }, @{ id = "displayName" })
        }
    } | ConvertTo-Json -Depth 6
    $flowResult = Invoke-GraphRequest POST "https://graph.microsoft.com/beta/identity/authenticationEventsFlows" -Body $body
    $flowId = $flowResult.id
    if ([string]::IsNullOrEmpty($flowId)) {
        throw "User flow 'susi' : création sans ID retourné — relancer le script."
    }
    Write-Host "User flow 'susi' créé."
}

Write-Host "Flow ID : $flowId"

# ==============================================================================
# 7. Association fastapi-jobfinder ↔ user flow susi (idempotent)
# ==============================================================================

Write-Host "Vérification de l'association '$appName' ↔ user flow 'susi'..."
$appsInFlowUrl    = "https://graph.microsoft.com/beta/identity/authenticationEventsFlows/$flowId/conditions/applications/includeApplications"
$appsInFlow       = Invoke-GraphRequest GET $appsInFlowUrl
$appAlreadyLinked = $appsInFlow.value | Where-Object { $_.appId -eq $appId }

if ($null -ne $appAlreadyLinked) {
    Write-Host "App '$appName' déjà associée au user flow 'susi' — ignorée."
} else {
    Write-Host "Association de '$appName' au user flow 'susi'..."
    # @odata.type obligatoire : l'API Graph rejette le body sans ce champ
    # ("application id is invalid") même si appId est correct.
    $body = @{
        "@odata.type" = "#microsoft.graph.authenticationConditionApplication"
        appId         = $appId
    } | ConvertTo-Json  # objet simple (deux propriétés) — ConvertTo-Json fiable ici
    Invoke-GraphRequest POST $appsInFlowUrl -Body $body
    Write-Host "App '$appName' associée au user flow 'susi'."
}

# ==============================================================================
# 8. Google Identity Provider (idempotent)
# ==============================================================================

Write-Host "Vérification du Google Identity Provider..."
$idpListUrl   = "https://graph.microsoft.com/v1.0/identity/identityProviders"
$existingIdPs = Invoke-GraphRequest GET $idpListUrl
$googleIdP    = $existingIdPs.value | Where-Object { $_.identityProviderType -eq "Google" }

if ($null -ne $googleIdP) {
    Write-Host "Google Identity Provider existe déjà — récupération de l'ID."
    $googleIdPId = $googleIdP.id
} else {
    Write-Host "Création du Google Identity Provider..."
    $body = @{
        "@odata.type"        = "#microsoft.graph.socialIdentityProvider"
        displayName          = "Google"
        identityProviderType = "Google"
        clientId             = $googleClientId
        clientSecret         = $googleClientSecret
    } | ConvertTo-Json  # objet simple — ConvertTo-Json fiable ici
    $googleResult = Invoke-GraphRequest POST $idpListUrl -Body $body
    $googleIdPId  = $googleResult.id
    if ([string]::IsNullOrEmpty($googleIdPId)) {
        throw "Google Identity Provider : création sans ID retourné — relancer le script."
    }
    Write-Host "Google Identity Provider créé (ID : $googleIdPId)."
}

# Ajout de Google au user flow susi (idempotent)
Write-Host "Vérification de Google dans le user flow 'susi'..."
$flowDetail   = Invoke-GraphRequest GET "https://graph.microsoft.com/beta/identity/authenticationEventsFlows/$flowId"
$currentIdPs  = $flowDetail.onAuthenticationMethodLoadStart.identityProviders
$googleInFlow = $currentIdPs | Where-Object { $_.id -eq $googleIdPId }

if ($null -ne $googleInFlow) {
    Write-Host "Google déjà présent dans le user flow 'susi' — ignoré."
} else {
    Write-Host "Ajout de Google au user flow 'susi'..."
    $updatedIdPs = @($currentIdPs | ForEach-Object { @{ id = $_.id } }) + @(@{ id = $googleIdPId })
    $body = @{
        onAuthenticationMethodLoadStart = @{
            "@odata.type"     = "#microsoft.graph.onAuthenticationMethodLoadStartExternalUsersSelfServiceSignUp"
            identityProviders = $updatedIdPs
        }
    } | ConvertTo-Json -Depth 5
    Invoke-GraphRequest PATCH "https://graph.microsoft.com/beta/identity/authenticationEventsFlows/$flowId" -Body $body
    Write-Host "Google ajouté au user flow 'susi'."
}

# ==============================================================================
# 9. App Registration SPA (spa-jobfinder) — client public, sans secret (idempotent)
# Carte applicative dédiée au frontend Next.js, distincte de l'API
# fastapi-jobfinder. Aucun client secret : l'auth navigateur utilise
# Authorization Code + PKCE (client public).
# ==============================================================================

Write-Host ""
Write-Host "Vérification de l'App Registration SPA '$spaAppName'..."
$existingSpaApp = az ad app list --display-name $spaAppName --query "[0]" | ConvertFrom-Json
if ($null -ne $existingSpaApp) {
    Write-Host "App Registration '$spaAppName' existe déjà — récupération des IDs."
    $spaAppObjId = $existingSpaApp.id
    $spaAppId    = $existingSpaApp.appId
} else {
    Write-Host "Création de l'App Registration '$spaAppName'..."
    $spaApp = az ad app create `
        --display-name     $spaAppName `
        --sign-in-audience AzureADMyOrg `
        | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { Write-Error "Échec az ad app create '$spaAppName'." ; exit 1 }
    $spaAppObjId = $spaApp.id
    $spaAppId    = $spaApp.appId
    Write-Host "App Registration '$spaAppName' créée."
}

# Service principal (idempotent — même logique que la section 2 pour fastapi-jobfinder)
Write-Host "Vérification du service principal '$spaAppName'..."
$existingSpaSP = az ad sp list --filter "appId eq '$spaAppId'" --query "[0]" | ConvertFrom-Json
if ($null -eq $existingSpaSP) {
    Write-Host "Création du service principal '$spaAppName'..."
    az ad sp create --id $spaAppId | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error "Échec az ad sp create '$spaAppName'." ; exit 1 }
    Write-Host "Service principal '$spaAppName' créé."
} else {
    Write-Host "Service principal '$spaAppName' existe déjà — ignoré."
}

Write-Host "SPA Client ID (NEXT_PUBLIC_ENTRA_CLIENT_ID) : $spaAppId"

# ==============================================================================
# 10. Plateforme SPA — redirect URIs (idempotent)
# Les URIs sont enregistrées dans la propriété `spa` (et NON `web`) : c'est ce
# qui active le flux Authorization Code + PKCE attendu par MSAL dans le
# navigateur. Ajout additif — les URIs déjà présentes sont conservées.
# ==============================================================================

Write-Host "Vérification des redirect URIs de la plateforme SPA..."
$spaDetails     = Invoke-GraphRequest GET "https://graph.microsoft.com/v1.0/applications/$spaAppObjId"
# Where-Object { $_ } : sur une app fraîchement créée, .spa.redirectUris vaut
# $null et @($null) produirait un tableau contenant un élément vide.
$currentSpaUris = @($spaDetails.spa.redirectUris | Where-Object { $_ })
$missingUris    = @($spaRedirectUris | Where-Object { $currentSpaUris -notcontains $_ })

if ($missingUris.Count -eq 0) {
    Write-Host "Redirect URIs SPA déjà à jour ($($currentSpaUris -join ', ')) — ignoré."
} else {
    $mergedUris = @($currentSpaUris + $missingUris | Select-Object -Unique)
    Write-Host "Enregistrement des redirect URIs SPA : $($mergedUris -join ', ')..."
    # JSON construit manuellement : ConvertTo-Json désérialise un tableau
    # mono-élément en scalaire sous PowerShell 5.1, ce que Graph rejette pour
    # spa.redirectUris (Collection(String)).
    $urisJson = '[' + (($mergedUris | ForEach-Object { '"' + $_ + '"' }) -join ',') + ']'
    $body     = '{"spa":{"redirectUris":' + $urisJson + '}}'
    Invoke-GraphRequest PATCH "https://graph.microsoft.com/v1.0/applications/$spaAppObjId" -Body $body
    Write-Host "Redirect URIs SPA enregistrées : $($mergedUris -join ', ')."
}

# ==============================================================================
# 11. Permission API déléguée — spa-jobfinder → fastapi-jobfinder/access_as_user
# Réutilise l'id du scope access_as_user créé en section 5 (ne le recrée pas).
# ==============================================================================

Write-Host "Récupération de l'id du scope 'access_as_user' de '$appName'..."
$apiAppDetails       = Invoke-GraphRequest GET "https://graph.microsoft.com/v1.0/applications/$appObjId"
$accessAsUserScope   = $apiAppDetails.api.oauth2PermissionScopes | Where-Object { $_.value -eq "access_as_user" }
$accessAsUserScopeId = $accessAsUserScope.id

if ($null -eq $accessAsUserScopeId) {
    Write-Error "Scope 'access_as_user' introuvable sur '$appName' — exécuter d'abord la section 5."
    exit 1
}

Write-Host "Vérification de la permission API déléguée de '$spaAppName'..."
$spaPermissionDetails = Invoke-GraphRequest GET "https://graph.microsoft.com/v1.0/applications/$spaAppObjId"
$apiAccessGranted = $false
foreach ($resource in @($spaPermissionDetails.requiredResourceAccess)) {
    if ($resource.resourceAppId -eq $appId) {
        $scopeGranted = @($resource.resourceAccess) | Where-Object { $_.id -eq $accessAsUserScopeId -and $_.type -eq "Scope" }
        if ($null -ne $scopeGranted) { $apiAccessGranted = $true }
    }
}

if ($apiAccessGranted) {
    Write-Host "Permission déléguée 'access_as_user' déjà accordée à '$spaAppName' — ignorée."
} else {
    Write-Host "Ajout de la permission déléguée 'access_as_user' à '$spaAppName'..."
    # Lire-fusionner-écrire (même logique additive que les redirect URIs en
    # section 10) : on repart du requiredResourceAccess courant pour ne pas
    # écraser d'éventuelles autres permissions déjà enregistrées.
    # JSON manuel pour garantir des tableaux (cf. note section 10).
    $resourceEntries = @()
    $apiEntryHandled = $false
    foreach ($resource in @($spaPermissionDetails.requiredResourceAccess)) {
        $accessItems = @($resource.resourceAccess | ForEach-Object {
                '{"id":"' + $_.id + '","type":"' + $_.type + '"}'
            })
        if ($resource.resourceAppId -eq $appId) {
            # Entrée fastapi-jobfinder déjà présente : ajouter le scope manquant
            # sans dupliquer ni toucher aux autres resourceAccess de l'entrée.
            if (-not (@($resource.resourceAccess) | Where-Object { $_.id -eq $accessAsUserScopeId -and $_.type -eq "Scope" })) {
                $accessItems += '{"id":"' + $accessAsUserScopeId + '","type":"Scope"}'
            }
            $apiEntryHandled = $true
        }
        $resourceEntries += '{"resourceAppId":"' + $resource.resourceAppId + '","resourceAccess":[' + ($accessItems -join ',') + ']}'
    }
    if (-not $apiEntryHandled) {
        # fastapi-jobfinder absent du requiredResourceAccess courant — l'ajouter
        # aux entrées existantes.
        $resourceEntries += '{"resourceAppId":"' + $appId + '","resourceAccess":[{"id":"' + $accessAsUserScopeId + '","type":"Scope"}]}'
    }
    $body = '{"requiredResourceAccess":[' + ($resourceEntries -join ',') + ']}'
    Invoke-GraphRequest PATCH "https://graph.microsoft.com/v1.0/applications/$spaAppObjId" -Body $body
    Write-Host "Permission déléguée 'access_as_user' accordée à '$spaAppName'."
}

# ==============================================================================
# 12. Association spa-jobfinder ↔ user flow susi (idempotent)
# Même pattern que la section 7 — la SPA hérite d'Email + Google via susi.
# ==============================================================================

Write-Host "Vérification de l'association '$spaAppName' ↔ user flow 'susi'..."
$spaInFlow        = Invoke-GraphRequest GET $appsInFlowUrl
$spaAlreadyLinked = $spaInFlow.value | Where-Object { $_.appId -eq $spaAppId }

if ($null -ne $spaAlreadyLinked) {
    Write-Host "App '$spaAppName' déjà associée au user flow 'susi' — ignorée."
} else {
    Write-Host "Association de '$spaAppName' au user flow 'susi'..."
    # @odata.type obligatoire : même contrainte que la section 7.
    # objet simple (deux propriétés) — ConvertTo-Json fiable ici
    $body = @{
        "@odata.type" = "#microsoft.graph.authenticationConditionApplication"
        appId         = $spaAppId
    } | ConvertTo-Json
    Invoke-GraphRequest POST $appsInFlowUrl -Body $body
    Write-Host "App '$spaAppName' associée au user flow 'susi'."
}

# ==============================================================================
# 13. Résumé — valeurs à stocker dans Key Vault (kv-jf-dev-frc)
# ⚠️  Script manuel uniquement — ne pas exécuter en CI/CD : les secrets
#     apparaîtraient en clair dans les logs du runner.
# ==============================================================================

Write-Host ""
Write-Host "Entra External ID configuré."
Write-Host ""
Write-Host "Stocker dans $keyVaultName :"
Write-Host "  entra-external-tenant-id     = $externalTenantId"
Write-Host "  entra-external-client-id     = $appId"
Write-Host "  entra-external-client-secret = $clientSecret"
Write-Host "  google-oauth-client-id       = $googleClientId"
Write-Host "  google-oauth-client-secret   = $googleClientSecret"
Write-Host ""
Write-Host "Variables d'environnement correspondantes :"
Write-Host "  ENTRA_EXTERNAL_TENANT_ID     = $externalTenantId"
Write-Host "  ENTRA_EXTERNAL_CLIENT_ID     = $appId"
Write-Host "  ENTRA_EXTERNAL_CLIENT_SECRET = $clientSecret"
Write-Host "  GOOGLE_OAUTH_CLIENT_ID       = $googleClientId"
Write-Host "  GOOGLE_OAUTH_CLIENT_SECRET   = $googleClientSecret"
Write-Host ""
Write-Host "À coller dans JobFinder/frontend/.env.local (frontend Next.js / MSAL) :"
Write-Host "  NEXT_PUBLIC_ENTRA_CLIENT_ID      = $spaAppId"
Write-Host "  NEXT_PUBLIC_ENTRA_AUTHORITY      = https://$domainName.ciamlogin.com/$externalTenantId"
Write-Host "  NEXT_PUBLIC_ENTRA_KNOWN_AUTHORITY = $domainName.ciamlogin.com"
Write-Host "  NEXT_PUBLIC_ENTRA_API_SCOPE      = api://$appId/access_as_user"
# affiche uniquement la 1re URI (localhost dev) — les autres sont enregistrées mais pas reprises dans le hint
Write-Host "  NEXT_PUBLIC_REDIRECT_URI         = $($spaRedirectUris[0])"
Write-Host ""
Write-Host "Exécution (prérequis : setup-sp-jf-ciam-setup.ps1 + az login Owner sur la subscription) :"
Write-Host "  ./setup-entra-external-tenant.ps1 ``"
Write-Host "      -subscriptionId <id> -tenantId <id> -resourceGroupName <rg> ``"
Write-Host "      -googleClientId <id> -googleClientSecret <secret> ``"
Write-Host "      [-spaRedirectUris @('http://localhost:3000','https://<frontend>.azurecontainerapps.io')]"
Write-Host ""
Write-Host "Ré-exécutable sans effet de bord : tout l'existant est détecté et préservé."
