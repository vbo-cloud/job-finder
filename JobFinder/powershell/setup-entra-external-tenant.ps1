# ==============================================================================
# Setup — Microsoft Entra External ID tenant + App Registration FastAPI
# Crée le tenant CIAM "jobfinderapp" via ARM (Microsoft.AzureActiveDirectory/
# ciamDirectories), l'app registration FastAPI, le scope access_as_user,
# le user flow susi et le Google Identity Provider via Microsoft Graph.
#
# Prérequis : az login avec un compte Owner sur la subscription, autorisé
#             à créer des tenants Entra External ID.
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

$domainName  = "jobfinderapp"
$displayName = "jobfinderapp"
$countryCode = "FR"
$appName     = "fastapi-jobfinder"
$spaAppName  = "spa-jobfinder"

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

    # La création de tenant est asynchrone — polling toutes les 10s jusqu'à disponibilité du tenantId
    $maxAttempts      = 18  # 3 minutes max
    $attempt          = 0
    $externalTenantId = $null
    while ($attempt -lt $maxAttempts -and $null -eq $externalTenantId) {
        $attempt++
        Write-Host "Attente de la propagation du tenant ($attempt/$maxAttempts)..."
        Start-Sleep -Seconds 10
        $polledTenant = az rest --method GET --url $ciamUrl 2>$null | ConvertFrom-Json
        if ($null -ne $polledTenant -and $null -ne $polledTenant.properties.tenantId) {
            $externalTenantId = $polledTenant.properties.tenantId
        }
    }
    if ($null -eq $externalTenantId) {
        Write-Error "Tenant '$domainName' non disponible après $maxAttempts tentatives — relancer le script."
        exit 1
    }
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
# 4. Client secret (idempotent — génère uniquement si aucun secret valide n'existe)
# ==============================================================================

Write-Host "Vérification des secrets existants..."
$now         = [datetime]::UtcNow
$credentials = az ad app credential list --id $appObjId | ConvertFrom-Json
$validSecret = @($credentials | Where-Object { [datetime]$_.endDateTime -gt $now })

if ($validSecret.Count -gt 0) {
    Write-Host "Secret valide existant (expire le $($validSecret[0].endDateTime)) — génération ignorée."
    Write-Host "⚠️  La valeur n'est pas récupérable — utiliser le secret déjà stocké dans kv-jf-dev-frc."
    $clientSecret = "<secret existant — voir kv-jf-dev-frc : entra-external-client-secret>"
} else {
    Write-Host "Aucun secret valide — génération d'un client secret (valable 2 ans)..."
    $secretResult = az ad app credential reset `
        --id     $appObjId `
        --years  2 `
        --append `
        | ConvertFrom-Json
    $clientSecret = $secretResult.password
    Write-Host "Client secret généré."
}

# ==============================================================================
# 5. Scope access_as_user (idempotent)
# PATCH Graph — ajoute le scope custom uniquement s'il n'existe pas déjà.
# ==============================================================================

Write-Host "Vérification du scope 'access_as_user'..."
$appDetails     = az rest --method GET `
    --url      "https://graph.microsoft.com/v1.0/applications/$appObjId" `
    --resource "https://graph.microsoft.com" `
    | ConvertFrom-Json
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

    $tmpFile = [System.IO.Path]::GetTempFileName() + ".json"
    [System.IO.File]::WriteAllText($tmpFile, $body, (New-Object System.Text.UTF8Encoding $false))
    az rest --method PATCH `
        --url      "https://graph.microsoft.com/v1.0/applications/$appObjId" `
        --body     "@$tmpFile" `
        --headers  "Content-Type=application/json" `
        --resource "https://graph.microsoft.com"
    Remove-Item $tmpFile
    Write-Host "Scope 'access_as_user' créé (ID : $scopeId)."
}

# ==============================================================================
# 6. User flow susi (idempotent)
# ==============================================================================

Write-Host "Vérification du user flow 'susi'..."
$flowsResult  = az rest --method GET `
    --url      "https://graph.microsoft.com/beta/identity/authenticationEventsFlows?`$filter=displayName eq 'susi'" `
    --resource "https://graph.microsoft.com" `
    | ConvertFrom-Json

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

    $tmpFile = [System.IO.Path]::GetTempFileName() + ".json"
    [System.IO.File]::WriteAllText($tmpFile, $body, (New-Object System.Text.UTF8Encoding $false))
    $flowResult = az rest --method POST `
        --url      "https://graph.microsoft.com/beta/identity/authenticationEventsFlows" `
        --body     "@$tmpFile" `
        --headers  "Content-Type=application/json" `
        --resource "https://graph.microsoft.com" `
        | ConvertFrom-Json
    Remove-Item $tmpFile
    $flowId = $flowResult.id
    Write-Host "User flow 'susi' créé."
}

Write-Host "Flow ID : $flowId"

# ==============================================================================
# 7. Association fastapi-jobfinder ↔ user flow susi (idempotent)
# ==============================================================================

Write-Host "Vérification de l'association '$appName' ↔ user flow 'susi'..."
$appsInFlowUrl  = "https://graph.microsoft.com/beta/identity/authenticationEventsFlows/$flowId/conditions/applications/includeApplications"
$appsInFlow     = az rest --method GET --url $appsInFlowUrl --resource "https://graph.microsoft.com" | ConvertFrom-Json
$appAlreadyLinked = $appsInFlow.value | Where-Object { $_.appId -eq $appId }

if ($null -ne $appAlreadyLinked) {
    Write-Host "App '$appName' déjà associée au user flow 'susi' — ignorée."
} else {
    Write-Host "Association de '$appName' au user flow 'susi'..."
    $body    = @{ appId = $appId } | ConvertTo-Json
    $tmpFile = [System.IO.Path]::GetTempFileName() + ".json"
    [System.IO.File]::WriteAllText($tmpFile, $body, (New-Object System.Text.UTF8Encoding $false))
    az rest --method POST `
        --url      $appsInFlowUrl `
        --body     "@$tmpFile" `
        --headers  "Content-Type=application/json" `
        --resource "https://graph.microsoft.com"
    Remove-Item $tmpFile
    Write-Host "App '$appName' associée au user flow 'susi'."
}

# ==============================================================================
# 8. Google Identity Provider (idempotent)
# ==============================================================================

Write-Host "Vérification du Google Identity Provider..."
$idpListUrl = "https://graph.microsoft.com/v1.0/identity/identityProviders"
$existingIdPs = az rest --method GET --url $idpListUrl --resource "https://graph.microsoft.com" | ConvertFrom-Json
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
    } | ConvertTo-Json

    $tmpFile = [System.IO.Path]::GetTempFileName() + ".json"
    [System.IO.File]::WriteAllText($tmpFile, $body, (New-Object System.Text.UTF8Encoding $false))
    $googleResult = az rest --method POST `
        --url      $idpListUrl `
        --body     "@$tmpFile" `
        --headers  "Content-Type=application/json" `
        --resource "https://graph.microsoft.com" `
        | ConvertFrom-Json
    Remove-Item $tmpFile
    $googleIdPId = $googleResult.id
    Write-Host "Google Identity Provider créé (ID : $googleIdPId)."
}

# Ajout de Google au user flow susi (idempotent)
Write-Host "Vérification de Google dans le user flow 'susi'..."
$flowDetail    = az rest --method GET `
    --url      "https://graph.microsoft.com/beta/identity/authenticationEventsFlows/$flowId" `
    --resource "https://graph.microsoft.com" `
    | ConvertFrom-Json
$currentIdPs   = $flowDetail.onAuthenticationMethodLoadStart.identityProviders
$googleInFlow  = $currentIdPs | Where-Object { $_.id -eq $googleIdPId }

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

    $tmpFile = [System.IO.Path]::GetTempFileName() + ".json"
    [System.IO.File]::WriteAllText($tmpFile, $body, (New-Object System.Text.UTF8Encoding $false))
    az rest --method PATCH `
        --url      "https://graph.microsoft.com/beta/identity/authenticationEventsFlows/$flowId" `
        --body     "@$tmpFile" `
        --headers  "Content-Type=application/json" `
        --resource "https://graph.microsoft.com"
    Remove-Item $tmpFile
    Write-Host "Google ajouté au user flow 'susi'."
}

# ==============================================================================
# 9. App Registration SPA (spa-jobfinder) — client public, sans secret (idempotent)
# Carte applicative dédiée au frontend Next.js, distincte de l'API
# fastapi-jobfinder. Aucun client secret : l'auth navigateur utilise
# Authorization Code + PKCE (client public). Authentifié contre le tenant CIAM
# via le az login de la section 2.
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
    $spaAppObjId = $spaApp.id
    $spaAppId    = $spaApp.appId
    Write-Host "App Registration '$spaAppName' créée."
}

Write-Host "SPA Client ID (NEXT_PUBLIC_ENTRA_CLIENT_ID) : $spaAppId"

# ==============================================================================
# 10. Plateforme SPA — redirect URIs (idempotent)
# Les URIs sont enregistrées dans la propriété `spa` (et NON `web`) : c'est ce
# qui active le flux Authorization Code + PKCE attendu par MSAL dans le
# navigateur. Ajout additif — les URIs déjà présentes sont conservées.
# ==============================================================================

Write-Host "Vérification des redirect URIs de la plateforme SPA..."
$spaDetails     = az rest --method GET `
    --url      "https://graph.microsoft.com/v1.0/applications/$spaAppObjId" `
    --resource "https://graph.microsoft.com" `
    | ConvertFrom-Json
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

    $tmpFile = [System.IO.Path]::GetTempFileName() + ".json"
    [System.IO.File]::WriteAllText($tmpFile, $body, (New-Object System.Text.UTF8Encoding $false))
    az rest --method PATCH `
        --url      "https://graph.microsoft.com/v1.0/applications/$spaAppObjId" `
        --body     "@$tmpFile" `
        --headers  "Content-Type=application/json" `
        --resource "https://graph.microsoft.com"
    Remove-Item $tmpFile
    Write-Host "Redirect URIs SPA enregistrées : $($mergedUris -join ', ')."
}

# ==============================================================================
# 11. Permission API déléguée — spa-jobfinder → fastapi-jobfinder/access_as_user
# Réutilise l'id du scope access_as_user créé en section 5 (ne le recrée pas).
# ==============================================================================

Write-Host "Récupération de l'id du scope 'access_as_user' de '$appName'..."
$apiAppDetails       = az rest --method GET `
    --url      "https://graph.microsoft.com/v1.0/applications/$appObjId" `
    --resource "https://graph.microsoft.com" `
    | ConvertFrom-Json
$accessAsUserScope   = $apiAppDetails.api.oauth2PermissionScopes | Where-Object { $_.value -eq "access_as_user" }
$accessAsUserScopeId = $accessAsUserScope.id

if ($null -eq $accessAsUserScopeId) {
    Write-Error "Scope 'access_as_user' introuvable sur '$appName' — exécuter d'abord la section 5."
    exit 1
}

Write-Host "Vérification de la permission API déléguée de '$spaAppName'..."
$spaPermissionDetails = az rest --method GET `
    --url      "https://graph.microsoft.com/v1.0/applications/$spaAppObjId" `
    --resource "https://graph.microsoft.com" `
    | ConvertFrom-Json
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
    # La SPA n'a qu'une dépendance API (fastapi-jobfinder) ; on positionne
    # requiredResourceAccess sur cette unique entrée. JSON manuel pour garantir
    # des tableaux (cf. note section 10).
    $body = '{"requiredResourceAccess":[{"resourceAppId":"' + $appId + '",' +
            '"resourceAccess":[{"id":"' + $accessAsUserScopeId + '","type":"Scope"}]}]}'

    $tmpFile = [System.IO.Path]::GetTempFileName() + ".json"
    [System.IO.File]::WriteAllText($tmpFile, $body, (New-Object System.Text.UTF8Encoding $false))
    az rest --method PATCH `
        --url      "https://graph.microsoft.com/v1.0/applications/$spaAppObjId" `
        --body     "@$tmpFile" `
        --headers  "Content-Type=application/json" `
        --resource "https://graph.microsoft.com"
    Remove-Item $tmpFile
    Write-Host "Permission déléguée 'access_as_user' accordée à '$spaAppName'."
}

# ==============================================================================
# 12. Association spa-jobfinder ↔ user flow susi (idempotent)
# Même pattern que la section 7 — la SPA hérite d'Email + Google via susi.
# ==============================================================================

Write-Host "Vérification de l'association '$spaAppName' ↔ user flow 'susi'..."
$spaInFlow          = az rest --method GET --url $appsInFlowUrl --resource "https://graph.microsoft.com" | ConvertFrom-Json
$spaAlreadyLinked   = $spaInFlow.value | Where-Object { $_.appId -eq $spaAppId }

if ($null -ne $spaAlreadyLinked) {
    Write-Host "App '$spaAppName' déjà associée au user flow 'susi' — ignorée."
} else {
    Write-Host "Association de '$spaAppName' au user flow 'susi'..."
    $body    = @{ appId = $spaAppId } | ConvertTo-Json
    $tmpFile = [System.IO.Path]::GetTempFileName() + ".json"
    [System.IO.File]::WriteAllText($tmpFile, $body, (New-Object System.Text.UTF8Encoding $false))
    az rest --method POST `
        --url      $appsInFlowUrl `
        --body     "@$tmpFile" `
        --headers  "Content-Type=application/json" `
        --resource "https://graph.microsoft.com"
    Remove-Item $tmpFile
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
Write-Host "Stocker dans kv-jf-dev-frc :"
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
Write-Host "  NEXT_PUBLIC_REDIRECT_URI         = $($spaRedirectUris[0])"
Write-Host ""
Write-Host "Exécution (script manuel — un az login interactif sur le tenant CIAM est requis, géré en section 2) :"
Write-Host "  ./setup-entra-external-tenant.ps1 ``"
Write-Host "      -subscriptionId <id> -tenantId <id> -resourceGroupName <rg> ``"
Write-Host "      -googleClientId <id> -googleClientSecret <secret> ``"
Write-Host "      [-spaRedirectUris @('http://localhost:3000','https://<frontend>.azurecontainerapps.io')]"
Write-Host ""
Write-Host "Ré-exécutable sans effet de bord : tout l'existant est détecté et préservé."
