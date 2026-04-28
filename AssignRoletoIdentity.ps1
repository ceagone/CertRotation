<#
.SYNOPSIS
Grant Microsoft Graph Application permissions to a Managed Identity (Service Principal)

.DESCRIPTION
- Installs required Microsoft Graph modules
- Connects with required admin scopes
- Assigns Graph App Roles (Application permissions) to a Managed Identity
#>

param (
    [Parameter(Mandatory = $true)]
    [string]$ManagedIdentityObjectId,

    [string[]]$Permissions = @(
        "Application.ReadWrite.All"
    )
)

Write-Host "`n==== GRAPH PERMISSION ASSIGNMENT START ====" -ForegroundColor Cyan

# -----------------------------
# 1. Ensure NuGet provider
# -----------------------------
if (-not (Get-PackageProvider -Name NuGet -ErrorAction SilentlyContinue)) {
    Install-PackageProvider -Name NuGet -Force -Scope CurrentUser
}

# -----------------------------
# 2. Required modules
# -----------------------------
$modules = @(
    "Microsoft.Graph.Authentication",
    "Microsoft.Graph.Applications"
)

foreach ($module in $modules) {
    if (-not (Get-Module -ListAvailable -Name $module)) {
        Write-Host "Installing $module..." -ForegroundColor Yellow
        Install-Module $module -Scope CurrentUser -Force -AllowClobber
    }
}

# -----------------------------
# 3. Import modules
# -----------------------------
foreach ($module in $modules) {
    Import-Module $module -ErrorAction Stop
}

# -----------------------------
# 4. Connect to Graph
# -----------------------------
Write-Host "Connecting to Microsoft Graph..." -ForegroundColor Cyan

Connect-MgGraph -Scopes @(
    "Application.ReadWrite.All",
    "AppRoleAssignment.ReadWrite.All"
)

$context = Get-MgContext

Write-Host "`nConnected as: $($context.Account)"
Write-Host "Tenant: $($context.TenantId)"
Write-Host "Scopes: $($context.Scopes -join ', ')"

# -----------------------------
# 5. Get Microsoft Graph SPN
# -----------------------------
Write-Host "`nRetrieving Microsoft Graph Service Principal..." -ForegroundColor Yellow

$GraphSpn = Get-MgServicePrincipal -Filter "appId eq '00000003-0000-0000-c000-000000000000'"

if (-not $GraphSpn) {
    throw "Microsoft Graph Service Principal not found."
}

# -----------------------------
# 6. Assign permissions
# -----------------------------
foreach ($permission in $Permissions) {

    Write-Host "`nProcessing permission: $permission" -ForegroundColor Cyan

    $appRole = $GraphSpn.AppRoles | Where-Object {
        $_.Value -eq $permission -and $_.AllowedMemberTypes -contains "Application"
    }

    if (-not $appRole) {
        throw "Permission $permission not found in Graph AppRoles."
    }

    # Check if already assigned
    $existing = Get-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $ManagedIdentityObjectId |
        Where-Object { $_.AppRoleId -eq $appRole.Id }

    if ($existing) {
        Write-Host "Permission already assigned: $permission" -ForegroundColor Green
        continue
    }

    Write-Host "Assigning permission: $permission..." -ForegroundColor Yellow

    New-MgServicePrincipalAppRoleAssignment `
        -ServicePrincipalId $ManagedIdentityObjectId `
        -PrincipalId $ManagedIdentityObjectId `
        -ResourceId $GraphSpn.Id `
        -AppRoleId $appRole.Id

    Write-Host "Assigned: $permission" -ForegroundColor Green
}

# -----------------------------
# 7. Verification
# -----------------------------
Write-Host "`nVerifying assignments..." -ForegroundColor Cyan

$assignments = Get-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $ManagedIdentityObjectId

$assignments | ForEach-Object {
    $role = $GraphSpn.AppRoles | Where-Object { $_.Id -eq $_.AppRoleId }
    Write-Host "✔ Assigned Role ID: $($_.AppRoleId)"
}

Write-Host "`n==== COMPLETED SUCCESSFULLY ====" -ForegroundColor Green



# Install-Module -Name Microsoft.Graph.Applications   
# Connect-MgGraph -Scopes 'AppRoleAssignment.ReadWrite.All'   
# Connect-MgGraph -Scopes 'Application.Read.All'
# Get-MgServicePrincipal -Filter "displayName eq 'cert-test'" | Format-List Id, DisplayName, AppId, SignInAudience
# Get-MgServicePrincipal -Filter "appId eq '00000003-0000-0000-c000-000000000000'"


