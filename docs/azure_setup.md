# Azure Setup Guide

This guide covers setting up Azure services for the ML DevOps Intelligence Platform.

## Prerequisites

- Azure Subscription
- Azure CLI installed (`az`)
- Python 3.9+

## Services Used

| Service | Purpose | Required |
|---------|---------|----------|
| Azure OpenAI | LLM inference (GPT-4) | Optional |
| Azure Blob Storage | Data lake storage | Optional |
| Azure Synapse Analytics | SQL analytics | Optional |
| Azure AD | Authentication | Recommended |

## Step 1: Install Azure CLI

```bash
# macOS
brew install azure-cli

# Windows
winget install Microsoft.AzureCLI

# Linux
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

## Step 2: Authenticate

### Option A: Azure CLI (Recommended for Development)

```bash
az login
```

### Option B: Service Principal (Recommended for CI/CD)

```bash
az ad sp create-for-rbac --name "devops-ml-sp" --role contributor
```

Save the output and set environment variables:
```bash
export AZURE_CLIENT_ID=<appId>
export AZURE_CLIENT_SECRET=<password>
export AZURE_TENANT_ID=<tenant>
```

## Step 3: Set Up Azure OpenAI

### 3.1 Create Azure OpenAI Resource

```bash
# Create resource group
az group create --name devops-ml-rg --location eastus

# Create OpenAI resource
az cognitiveservices account create \
    --name devops-ml-openai \
    --resource-group devops-ml-rg \
    --kind OpenAI \
    --sku S0 \
    --location eastus
```

### 3.2 Deploy GPT-4 Model

```bash
# Deploy GPT-4 model
az cognitiveservices account deployment create \
    --name devops-ml-openai \
    --resource-group devops-ml-rg \
    --deployment-name gpt-4 \
    --model-name gpt-4 \
    --model-version "0613" \
    --model-format OpenAI \
    --sku-capacity 10 \
    --sku-name Standard
```

### 3.3 Get Endpoint and Key

```bash
# Get endpoint
az cognitiveservices account show \
    --name devops-ml-openai \
    --resource-group devops-ml-rg \
    --query "properties.endpoint" -o tsv

# Get key
az cognitiveservices account keys list \
    --name devops-ml-openai \
    --resource-group devops-ml-rg \
    --query "key1" -o tsv
```

### 3.4 Configure Environment

```bash
export AZURE_OPENAI_ENDPOINT=https://devops-ml-openai.openai.azure.com/
export AZURE_OPENAI_API_KEY=your-api-key
export AZURE_OPENAI_DEPLOYMENT=gpt-4
export LLM_PROVIDER=azure_openai
```

## Step 4: Set Up Azure Blob Storage

### 4.1 Create Storage Account

```bash
# Create storage account (name must be globally unique)
az storage account create \
    --name devopsmlstorage123 \
    --resource-group devops-ml-rg \
    --location eastus \
    --sku Standard_LRS \
    --kind StorageV2 \
    --hierarchical-namespace true  # Enable ADLS Gen2
```

### 4.2 Create Container

```bash
# Get connection string
CONNECTION_STRING=$(az storage account show-connection-string \
    --name devopsmlstorage123 \
    --resource-group devops-ml-rg \
    --query connectionString -o tsv)

# Create container
az storage container create \
    --name assessments \
    --connection-string "$CONNECTION_STRING"
```

### 4.3 Configure Environment

**Option A: Connection String**
```bash
export AZURE_STORAGE_CONNECTION_STRING="$CONNECTION_STRING"
export STORAGE_PROVIDER=azure_blob
```

**Option B: Azure AD Auth (Recommended)**
```bash
export AZURE_STORAGE_ACCOUNT_URL=https://devopsmlstorage123.blob.core.windows.net
export AZURE_USE_AD=true
export STORAGE_PROVIDER=azure_blob

# Grant yourself access
az role assignment create \
    --role "Storage Blob Data Contributor" \
    --assignee $(az ad signed-in-user show --query id -o tsv) \
    --scope /subscriptions/<sub-id>/resourceGroups/devops-ml-rg/providers/Microsoft.Storage/storageAccounts/devopsmlstorage123
```

## Step 5: Set Up Azure Synapse Analytics

### 5.1 Create Synapse Workspace

```bash
# Create Data Lake storage for Synapse
az storage account create \
    --name synapsedatalake123 \
    --resource-group devops-ml-rg \
    --location eastus \
    --sku Standard_LRS \
    --kind StorageV2 \
    --hierarchical-namespace true

# Create file system
az storage fs create \
    --name synapsefs \
    --account-name synapsedatalake123

# Create Synapse workspace
az synapse workspace create \
    --name devops-ml-synapse \
    --resource-group devops-ml-rg \
    --location eastus \
    --storage-account synapsedatalake123 \
    --file-system synapsefs \
    --sql-admin-login-user sqladmin \
    --sql-admin-login-password 'YourStrongP@ssw0rd!'
```

### 5.2 Get Serverless SQL Endpoint

```bash
az synapse workspace show \
    --name devops-ml-synapse \
    --resource-group devops-ml-rg \
    --query "connectivityEndpoints.sqlOnDemand" -o tsv
```

### 5.3 Configure Firewall

```bash
# Allow your IP
az synapse workspace firewall-rule create \
    --name allow-my-ip \
    --workspace-name devops-ml-synapse \
    --resource-group devops-ml-rg \
    --start-ip-address <your-ip> \
    --end-ip-address <your-ip>

# Allow Azure services
az synapse workspace firewall-rule create \
    --name allow-azure \
    --workspace-name devops-ml-synapse \
    --resource-group devops-ml-rg \
    --start-ip-address 0.0.0.0 \
    --end-ip-address 0.0.0.0
```

### 5.4 Set Up External Data Source

Connect to Synapse via Azure Data Studio or SSMS, then run:

```python
from providers.storage.synapse import SynapseProvider

provider = SynapseProvider()
print(provider.get_synapse_setup_sql())
```

Execute the generated SQL in your Synapse workspace.

### 5.5 Configure Environment

```bash
export SYNAPSE_SQL_ENDPOINT=devops-ml-synapse-ondemand.sql.azuresynapse.net
export SYNAPSE_DATABASE=devops_ml
export STORAGE_PROVIDER=synapse
```

## Step 6: Using Managed Identity (Production)

For production deployments on Azure, use Managed Identity:

### 6.1 Enable Managed Identity

```bash
# For App Service
az webapp identity assign \
    --name your-app-name \
    --resource-group devops-ml-rg

# For Container Instances
az container create \
    --name your-container \
    --resource-group devops-ml-rg \
    --assign-identity
```

### 6.2 Grant Access to Resources

```bash
IDENTITY_ID=$(az webapp identity show \
    --name your-app-name \
    --resource-group devops-ml-rg \
    --query principalId -o tsv)

# Storage access
az role assignment create \
    --role "Storage Blob Data Contributor" \
    --assignee $IDENTITY_ID \
    --scope /subscriptions/<sub-id>/resourceGroups/devops-ml-rg/providers/Microsoft.Storage/storageAccounts/devopsmlstorage123

# OpenAI access
az role assignment create \
    --role "Cognitive Services OpenAI User" \
    --assignee $IDENTITY_ID \
    --scope /subscriptions/<sub-id>/resourceGroups/devops-ml-rg/providers/Microsoft.CognitiveServices/accounts/devops-ml-openai
```

## Cost Optimization

### Azure OpenAI Pricing
- GPT-4 (8K context): ~$0.03 per 1K input tokens, ~$0.06 per 1K output tokens
- GPT-4-Turbo: ~$0.01 per 1K input tokens, ~$0.03 per 1K output tokens

**Tip**: Use local classifier for pre-screening to reduce LLM calls.

### Storage Pricing
- Hot tier: ~$0.0184/GB/month
- Cool tier: ~$0.01/GB/month (consider for historical data)

### Synapse Pricing
- Serverless SQL: ~$5 per TB processed
- **Tip**: Partition your data by date to reduce scan costs

## Troubleshooting

### "AuthenticationError" for Azure OpenAI

1. Verify endpoint URL ends with `/`
2. Check API key is correct
3. Verify deployment name matches

### "DefaultAzureCredential" Errors

1. Ensure `az login` is done
2. Check AZURE_* environment variables
3. For service principal, verify all three env vars are set

### Synapse Connection Errors

1. Check firewall rules allow your IP
2. Verify SQL admin credentials
3. Ensure serverless SQL pool is enabled

## Complete Configuration Example

```bash
# .env file for Azure setup
LLM_PROVIDER=azure_openai
STORAGE_PROVIDER=synapse

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://devops-ml-openai.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT=gpt-4

# Storage (Synapse uses blob storage underneath)
AZURE_STORAGE_ACCOUNT_URL=https://devopsmlstorage123.blob.core.windows.net
AZURE_STORAGE_CONTAINER=assessments
AZURE_USE_AD=true

# Synapse
SYNAPSE_SQL_ENDPOINT=devops-ml-synapse-ondemand.sql.azuresynapse.net
SYNAPSE_DATABASE=devops_ml
```

## Resource Cleanup

To avoid ongoing charges:

```bash
# Delete entire resource group (removes all resources)
az group delete --name devops-ml-rg --yes --no-wait
```
