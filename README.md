# Assign Role to Identity - PowerShell Script

## Overview

`AssignRoletoIdentity.ps1` is a PowerShell script that grants Microsoft Graph Application permissions to Azure Managed Identities (Service Principals). This script automates the process of assigning app roles that a managed identity needs to interact with Microsoft Graph API.

## Purpose

This script is commonly used in certificate rotation workflows where a managed identity needs permissions to:
- Read and write applications in Azure AD
- Manage application credentials
- Update certificates for service principals
- Perform administrative operations on behalf of a service principal

## Prerequisites

- **PowerShell 5.1+** (or PowerShell Core 7.x)
- **Azure subscription** with appropriate permissions
- **User credentials** with Global Administrator or Application Administrator role
- **Internet connection** (to install modules and connect to Microsoft Graph)

## Installation & Setup

### 1. Install Required Modules

The script automatically installs required modules, but you can pre-install them manually:

```powershell
Install-Module Microsoft.Graph.Authentication -Scope CurrentUser -Force
Install-Module Microsoft.Graph.Applications -Scope CurrentUser -Force
```

### 2. Grant Execution Permission (if needed)

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Usage

### Basic Syntax

```powershell
.\AssignRoletoIdentity.ps1 -ManagedIdentityObjectId "<Managed-Identity-Object-ID>"
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `ManagedIdentityObjectId` | String | Yes | - | The Object ID of the Managed Identity or Service Principal to assign roles to |
| `Permissions` | String[] | No | `@("Application.ReadWrite.All")` | Array of Microsoft Graph App Roles to assign |

## Examples

### Example 1: Basic Usage (Default Permission)

Assign the default `Application.ReadWrite.All` permission to a managed identity:

```powershell
.\AssignRoletoIdentity.ps1 -ManagedIdentityObjectId "85a0ace0-a4e9-4cad-8be0-0790bf65a423"
```

**What this does:**
- Installs Microsoft Graph modules (if not already installed)
- Connects to Microsoft Graph with admin scopes
- Assigns `Application.ReadWrite.All` permission to the specified managed identity
- Verifies the assignment was successful

### Example 2: Multiple Custom Permissions

Assign multiple Microsoft Graph permissions:

```powershell
$permissions = @(
    "Application.ReadWrite.All",
    "Application.Read.All",
    "AppRoleAssignment.ReadWrite.All"
)

.\AssignRoletoIdentity.ps1 `
    -ManagedIdentityObjectId "85a0ace0-a4e9-4cad-8be0-0790bf65a423" `
    -Permissions $permissions
```

### Example 3: For Certificate Rotation Scenario

In a certificate rotation workflow where you need to update certificates programmatically:

```powershell
# First, get your managed identity object ID
$managedIdentityObjectId = (Get-AzADServicePrincipal -DisplayName "CertRotate").Id

# Assign the required permission for certificate operations
.\AssignRoletoIdentity.ps1 -ManagedIdentityObjectId $managedIdentityObjectId
```

### Example 4: Running from a Function App

When running as part of a certificate rotation function app deployment:

```powershell
# In your deployment script
$mi = Get-AzUserAssignedIdentity -ResourceGroupName "rg-cert-rotation" -Name "mi-cert-rotate"
.\AssignRoletoIdentity.ps1 -ManagedIdentityObjectId $mi.PrincipalId
```

## Finding the Managed Identity Object ID

### Option 1: Using Azure Portal
1. Navigate to **Managed Identities** or **Service Principals**
2. Find your identity by name
3. Copy the **Object ID**

### Option 2: Using Azure CLI

```bash
# For User-Assigned Managed Identity
az identity list --query "[?name=='<your-identity-name>'].principalId" -o tsv

# For System-Assigned Managed Identity (attached to resource)
az resource show --resource-group <rg> --name <resource-name> --resource-type <type> --query "identity.principalId" -o tsv
```

### Option 3: Using PowerShell

```powershell
# Get User-Assigned Identity
(Get-AzUserAssignedIdentity -ResourceGroupName "rg-name" -Name "identity-name").PrincipalId

# Get Service Principal by name
(Get-AzADServicePrincipal -DisplayName "service-principal-name").Id
```

## Common Microsoft Graph App Roles

Here are commonly used permissions for certificate rotation and app management:

| Permission | Description |
|-----------|-------------|
| `Application.ReadWrite.All` | Read and write all applications (includes certificate management) |
| `Application.Read.All` | Read all applications |
| `AppRoleAssignment.ReadWrite.All` | Manage app role assignments |
| `Directory.Read.All` | Read all directory data |
| `Directory.ReadWrite.All` | Read and write all directory data |

## Script Workflow

The script executes the following steps:

```
1. Ensure NuGet Provider
   ↓
2. Install/Check Required Modules
   ├─ Microsoft.Graph.Authentication
   └─ Microsoft.Graph.Applications
   ↓
3. Import Modules
   ↓
4. Connect to Microsoft Graph
   (Prompts for authentication)
   ↓
5. Retrieve Microsoft Graph Service Principal
   ↓
6. For Each Permission:
   ├─ Find App Role by name
   ├─ Check if already assigned
   └─ Assign permission if needed
   ↓
7. Verify All Assignments
   ↓
8. Completion
```

## Output Example

```
==== GRAPH PERMISSION ASSIGNMENT START ====
Connecting to Microsoft Graph...

Connected as: user@contoso.com
Tenant: 12345678-1234-1234-1234-123456789012
Scopes: Application.ReadWrite.All, AppRoleAssignment.ReadWrite.All

Retrieving Microsoft Graph Service Principal...

Processing permission: Application.ReadWrite.All
Assigning permission: Application.ReadWrite.All...
Assigned: Application.ReadWrite.All

Verifying assignments...
✔ Assigned Role ID: 9a6f8cc9-4040-45c1-9fe4-98d0ff05b9f2

==== COMPLETED SUCCESSFULLY ====
```

## Troubleshooting

### Error: "Microsoft Graph Service Principal not found"
- Ensure you're connected to the correct Azure tenant
- Verify your account has proper permissions

### Error: "Permission not found in Graph AppRoles"
- Double-check the permission name spelling
- Verify the permission exists in Microsoft Graph
- Use `Get-MgServicePrincipal` to list available roles

### Error: "Not authenticated. Connect using Connect-MgGraph"
- The script will prompt for authentication if not already connected
- Ensure you have Global Administrator or Application Administrator role

### Error: Module Installation Fails
- Check your internet connection
- Verify you have permission to install modules in the specified scope
- Try manual installation: `Install-Module Microsoft.Graph.Authentication -Force -Scope CurrentUser`

## Best Practices

1. **Principle of Least Privilege**: Only assign permissions the managed identity actually needs
2. **Verify Before Running**: Review what permissions will be assigned
3. **Test in Development**: Always test with a dev managed identity first
4. **Document Assignments**: Keep track of which permissions are assigned to which identities
5. **Periodic Review**: Regularly review and audit permissions granted to managed identities

## Integration Examples

### Certificate Rotation Pipeline
```powershell
# Deploy managed identity
$mi = New-AzUserAssignedIdentity -ResourceGroupName "rg-certs" -Name "mi-cert-rotate"

# Assign required permissions
.\AssignRoletoIdentity.ps1 -ManagedIdentityObjectId $mi.PrincipalId

# Deploy function app with this identity
New-AzFunctionApp -ResourceGroupName "rg-certs" -UserAssignedIdentity @($mi.Id) ...
```

### Batch Assignment
```powershell
$identities = @(
    "85a0ace0-a4e9-4cad-8be0-0790bf65a423",
    "95b1bdf0-b5fa-4dbe-8cf1-0891dg76b534"
)

foreach ($id in $identities) {
    .\AssignRoletoIdentity.ps1 -ManagedIdentityObjectId $id
}
```

## Additional Resources

- [Microsoft Graph App Roles](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [Azure Managed Identities](https://learn.microsoft.com/en-us/azure/active-directory/managed-identities-azure-resources/)
- [Microsoft.Graph PowerShell Module](https://learn.microsoft.com/en-us/powershell/microsoftgraph/)

## License

For licensing information, refer to your organization's policies.

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review Microsoft Graph documentation
3. Contact your Azure administrator

---

# CertRotate Function App - Automated Certificate Rotation

## Overview

The **CertRotate Azure Function App** (`function_app.py`) is a serverless, event-driven certificate rotation solution that automatically:

1. **Detects** when certificates are updated in Azure Key Vault (via Event Grid)
2. **Extracts** certificates from Key Vault (supports both PFX and PEM formats)
3. **Updates** Azure AD Application Registration with the new certificate
4. **Exports** the certificate in PFX format with a secure password
5. **Pushes** certificate credentials to GitHub Actions secrets for CI/CD pipelines
6. **Logs** all operations for audit and compliance

This is critical for organizations using GitHub Actions to deploy applications that require certificate authentication to Azure services.

## What It Does in Detail

### Workflow Process

```
1. Event Grid Trigger
   ├─ Certificate added/updated in Key Vault
   └─ Event Grid sends notification to Function App
      ↓
2. Extract Certificate Information
   ├─ Retrieve cert from Key Vault
   ├─ Support PFX (PKCS#12) or PEM formats
   └─ Extract private key and certificate chain
      ↓
3. Update App Registration
   ├─ Connect to Microsoft Graph API
   ├─ Add public certificate to app registration
   └─ Include metadata (thumbprint, expiry, dates)
      ↓
4. Generate Secure Export
   ├─ Create password-protected PFX
   ├─ Generate random secure password
   └─ Base64 encode for storage
      ↓
5. Push to GitHub Secrets
   ├─ Encrypt secrets using GitHub public key
   ├─ Update GitHub Actions secrets:
   │  ├─ CERT_BASE64 (password-protected PFX)
   │  ├─ CERT_PASSWORD (for PFX decryption)
   │  ├─ CERT_THUMBPRINT (certificate fingerprint)
   │  └─ AZURE_CLIENT_ID (app registration ID)
   └─ Enable GitHub Actions to use cert for auth
      ↓
6. Logging & Audit
   └─ All steps logged for compliance
```

## Prerequisites

### Azure Resources
- **Azure Subscription** with appropriate permissions
- **Azure Key Vault** containing certificates (PFX or PEM format)
- **App Registration** in Azure AD that the certificate will be assigned to
- **Azure Storage Account** (for Function App storage)
- **Event Grid** configured to monitor Key Vault

### Function App Environment
- **Python 3.9+** runtime
- **Managed Identity** (User-Assigned recommended) with permissions to:
  - Read Key Vault secrets
  - Write to Microsoft Graph API (Application.ReadWrite.All)
- **System or User-Assigned Identity** for authentication

### GitHub
- **GitHub Personal Access Token** (PAT) with `repo` and `admin:org_hook` scopes
- **GitHub Repository** where secrets will be stored
- **GitHub Actions** enabled in the repository

### Permissions Required
- **Azure AD Application Administrator** role (to add certificates to app registrations)
- **Key Vault Secret Officer** role (on the managed identity)
- **Microsoft Graph Application.ReadWrite.All** permission (assigned via `AssignRoletoIdentity.ps1`)

## Azure Function App Configuration

### Step 1: Create Function App Environment Variables

Navigate to your Function App → **Configuration** → **Application settings** and add the following:

| Variable Name | Value | Description | Example |
|--------------|-------|-------------|---------|
| `APP_OBJECT_ID` | **Required** | Object ID of the target Azure AD Application Registration | `550e8400-e29b-41d4-a716-446655440000` |
| `GITHUB_TOKEN` | **Required** | GitHub Personal Access Token (PAT) with repo access | `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `GITHUB_REPO` | **Required** | GitHub repository in format `owner/repo` | `myorg/myrepo` |
| `AZURE_TENANT_ID` | Optional | Azure Tenant ID (auto-detected if not provided) | `12345678-1234-1234-1234-123456789012` |

### Step 2: Configure Managed Identity

1. Go to **Function App** → **Identity**
2. Enable **System-assigned** or assign **User-assigned** identity
3. Assign the following roles to the managed identity:
   - **Key Vault Secrets Officer** (on the Key Vault)
   - **Application Administrator** (on Azure AD)

### Step 3: Configure Event Grid Trigger

1. Go to your **Key Vault**
2. Navigate to **Events** → **+ Event Subscription**
3. **Filter to Event Types**: Certificate operations you want to trigger on:
   - `Microsoft.KeyVault.CertificateNearExpiry` (recommended for automation)
   - `Microsoft.KeyVault.CertificateExpired`
   - OR monitor the storage system directly
4. **Endpoint Type**: Azure Function
5. **Endpoint**: Select your CertRotate function app

### Step 4: Assign Microsoft Graph Permissions

Run the PowerShell script to assign permissions:

```powershell
# Get the Managed Identity Object ID
$mi = Get-AzUserAssignedIdentity -ResourceGroupName "your-rg" -Name "your-identity"

# OR for System-Assigned Identity
$mi = Get-AzFunctionApp -ResourceGroupName "your-rg" -Name "your-function-app"

# Assign permissions
.\AssignRoletoIdentity.ps1 -ManagedIdentityObjectId $mi.PrincipalId
```

## GitHub Configuration

### Step 1: Generate GitHub Personal Access Token (PAT)

1. Go to **GitHub Settings** → **Developer settings** → **Personal access tokens**
2. Click **Generate new token (classic)**
3. **Select scopes**:
   - ✅ `repo` (full control of private repositories)
   - ✅ `admin:org_hook` (if using organization repos)
   - ✅ `workflow` (for Actions workflows)
4. Copy the token (you'll only see it once)
5. Store it securely - this will be your `GITHUB_TOKEN`

### Step 2: Store GitHub Token in Azure

In your Function App → **Configuration** → **Application settings**:
- Add `GITHUB_TOKEN` = [Your PAT from Step 1]
- Add `GITHUB_REPO` = `owner/repository` (e.g., `myorg/myrepo`)

### Step 3: Create GitHub Secrets Manually (Optional Pre-Setup)

These will be auto-populated by the function, but you can pre-create them:

In **GitHub Repo** → **Settings** → **Secrets and variables** → **Actions secrets**:

| Secret Name | Current Value | Purpose |
|------------|---------------|---------|
| `CERT_BASE64` | `(will be auto-updated)` | Base64-encoded password-protected PFX |
| `CERT_PASSWORD` | `(will be auto-updated)` | Password for decrypting the PFX |
| `CERT_THUMBPRINT` | `(will be auto-updated)` | Certificate thumbprint (SHA-1 hash) |
| `AZURE_CLIENT_ID` | `(will be auto-updated)` | Azure AD App Registration Client ID |

### Step 4: Use Secrets in GitHub Actions

Example GitHub Actions workflow using the rotated certificate:

```yaml
name: Deploy with Certificate Auth

on: [push, workflow_dispatch]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Authenticate to Azure
        uses: azure/login@v1
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
          cert: ${{ secrets.CERT_BASE64 }}
          cert-password: ${{ secrets.CERT_PASSWORD }}
      
      - name: Your Deployment Step
        run: |
          # Your deployment commands here
```

## Important Things to Know

### Certificate Format Support

| Format | Support | Notes |
|--------|---------|-------|
| **PFX (PKCS#12)** | ✅ Full | Recommended - includes private key and chain |
| **PEM** | ✅ Full | Supports PEM with private key and chain |
| **Password-Protected** | ✅ Full | Both formats supported |
| **Without Chain** | ✅ Full | Works, but chain is optional |

### Security Considerations

1. **GitHub Token Permissions**: Limit PAT scopes to minimum required (`repo` + `workflow`)
2. **Certificate Password**: Randomly generated and never logged - only stored in GitHub Actions secrets
3. **No Plaintext Logging**: Certificate data is NOT logged - only metadata (thumbprint, dates)
4. **Encryption in Transit**: All API calls use HTTPS; GitHub secrets encrypted at rest
5. **Managed Identity**: Function uses managed identity - no stored credentials
6. **Least Privilege**: Assign minimum required permissions to managed identity

### Performance & Limits

- **Execution Time**: ~10-30 seconds depending on Key Vault and GitHub API latency
- **Concurrency**: Single event at a time (Event Grid default)
- **Retry Policy**: Event Grid retries up to 20 times over 24 hours
- **Rate Limiting**: GitHub API: 5,000 requests/hour per token

### Common Issues & Solutions

#### Issue: "APP_OBJECT_ID missing"
**Solution**: Add `APP_OBJECT_ID` environment variable to Function App configuration

#### Issue: "Failed to get public key" from GitHub
**Solution**: 
- Verify `GITHUB_TOKEN` is valid and not expired
- Check PAT has `repo` scope
- Verify `GITHUB_REPO` format is correct (`owner/repo`)

#### Issue: "Application.ReadWrite.All" permission denied
**Solution**:
- Run `AssignRoletoIdentity.ps1` with the managed identity Object ID
- Verify user running script has Global Administrator role
- Check that managed identity has "Application Administrator" role

#### Issue: "Key Vault secret not found"
**Solution**:
- Verify certificate name in Key Vault matches Event Grid payload
- Ensure managed identity has "Key Vault Secrets Officer" role
- Check that certificate exists and is not deleted

#### Issue: Certificate expired immediately after rotation
**Solution**:
- Verify certificate in Key Vault has future expiry date
- Check system time is correct on Function App

### Monitoring & Logging

1. **View Function Logs**:
   ```
   Function App → Monitor → Logs (KQL queries)
   ```

2. **Example KQL Query**:
   ```kusto
   AppServiceConsoleLogs
   | where Timestamp > ago(24h)
   | where ResultDescription contains "CERT ROTATION"
   ```

3. **GitHub Actions Workflow Logs**:
   - View in GitHub Actions when secrets are used
   - Certificate auth attempts logged by Azure login action

### Event Grid Trigger Limitations

- **Minimum Interval**: Events may not trigger immediately (typically < 1 minute)
- **Event Retention**: Only the most recent event state (not historical)
- **Dead Letter**: Configure dead-letter for failed events in Event Grid settings

### Supported Certificate Operations

The function can be triggered on these Key Vault events:

- Certificate created
- Certificate updated
- Certificate near expiry (recommended for automation)
- Certificate version created
- Certificate manual rotation

### Manual Testing

Test the function without Event Grid trigger:

```powershell
# PowerShell test payload
$payload = @{
    ObjectName = "MyCertificate"
    VaultName = "my-keyvault"
} | ConvertTo-Json

# Invoke function locally or via HTTP POST
$functionUrl = "https://your-function-app.azurewebsites.net/api/KeyVaultCertEventHandler"
Invoke-WebRequest -Uri $functionUrl -Method POST -Body $payload -ContentType "application/json"
```

## Deployment Steps

### Option 1: Deploy via Azure Portal

1. Create Azure Function App (Python 3.9+ runtime)
2. Add the code from `CertRotate/function_app.py`
3. Configure application settings (see Step 1 above)
4. Assign managed identity and permissions
5. Configure Event Grid trigger

### Option 2: Deploy via Azure CLI

```bash
# Create Function App
az functionapp create \
  --resource-group your-rg \
  --consumption-plan-location eastus \
  --runtime python \
  --runtime-version 3.9 \
  --functions-version 4 \
  --name your-cert-rotate-function

# Set environment variables
az functionapp config appsettings set \
  --name your-cert-rotate-function \
  --resource-group your-rg \
  --settings APP_OBJECT_ID="your-app-id" \
               GITHUB_TOKEN="your-token" \
               GITHUB_REPO="owner/repo"
```

### Option 3: Deploy via GitHub Actions (Recommended)

```yaml
- name: Deploy Function App
  uses: Azure/functions-action@v1
  with:
    app-name: your-cert-rotate-function
    package: ./CertRotate
    publish-profile: ${{ secrets.AZURE_FUNCTIONAPP_PUBLISH_PROFILE }}
```

## Additional Resources

- [Event Grid Documentation](https://learn.microsoft.com/en-us/azure/event-grid/)
- [Azure Function Python Developer Guide](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Microsoft Graph API Reference](https://learn.microsoft.com/en-us/graph/api/overview)
- [GitHub Actions Secrets Management](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [Azure Key Vault Best Practices](https://learn.microsoft.com/en-us/azure/key-vault/general/best-practices)

---

**Last Updated**: April 2026
**Function App Version**: 1.0
**Python Version**: 3.9+
**Status**: Production Ready
