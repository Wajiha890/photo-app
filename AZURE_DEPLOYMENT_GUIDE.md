# PixShare — Azure Deployment Guide
## MSc Scalable Software Solutions — Complete Step-by-Step Documentation

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Prerequisites](#3-prerequisites)
4. [Local Setup & Testing](#4-local-setup--testing)
5. [Azure CLI Setup](#5-azure-cli-setup)
6. [Create Azure Resources](#6-create-azure-resources)
7. [Build & Push Docker Image](#7-build--push-docker-image)
8. [Configure App Service](#8-configure-app-service)
9. [Deploy Frontend](#9-deploy-frontend)
10. [CI/CD Pipeline](#10-cicd-pipeline)
11. [Verify Deployment](#11-verify-deployment)
12. [Troubleshooting](#12-troubleshooting)
13. [Resource Summary](#13-resource-summary)

---

## 1. Project Overview

**PixShare** is a cloud-native photo-sharing web application (similar to Instagram) built for the MSc Scalable Software Solutions module.

### Tech Stack
| Layer | Technology |
|---|---|
| Frontend | Static HTML, CSS, JavaScript (8 pages) |
| Backend | Python Flask + Gunicorn (REST API) |
| Database | PostgreSQL (SQLAlchemy ORM) |
| Container | Docker |
| Cloud | Microsoft Azure |
| CI/CD | GitHub Actions |

### User Roles
- **Creator** — Can upload photos, set metadata (title, caption, location, people), manage users, view stats
- **Consumer** — Can browse, search, comment, rate, and react to photos

### Default Creator Account
- **Username:** `Admin Mujeeb`
- **Password:** `Mujeeb123`

---

## 2. Architecture

```
┌─────────────────────────────────────────────────┐
│              GitHub Repository                   │
│          (Mujeeb117/pix-app)                    │
└──────────────┬──────────────────────────────────┘
               │  git push to main
               │
       ┌───────┴────────┐
       │                │
       ▼                ▼
  backend/**        frontend/**
  changed?          changed?
       │                │
       ▼                ▼
 Pipeline 1        Pipeline 2
 (Backend)         (Frontend)
       │                │
       ▼                ▼
Build Docker       Upload files to
image → ACR        Blob Storage
       │                │
       ▼                ▼
 App Service      Storage Static
 (Flask API)      Website (CDN)
       │                │
       └───────┬────────┘
               │
               ▼
     ┌─────────────────┐
     │ Azure PostgreSQL │
     │   (Database)    │
     └─────────────────┘
```

### Azure Resources Used
| Resource | Name | Purpose | Region | Cost/month |
|---|---|---|---|---|
| Resource Group | `pixshare-rg` | Logical container for all resources | uksouth | Free |
| Container Registry | `pixshareacr` | Stores Docker images | norwayeast | ~£4 |
| PostgreSQL Flexible Server | `pixshare-db` | Cloud database | norwayeast | ~£12 |
| App Service Plan | `pixshare-plan` | Hosts backend (Linux B1) | swedencentral | ~£10 |
| App Service | `pixshare-api` | Runs Flask Docker container | swedencentral | Included |
| Storage Account | `pixsharestore2026` | Hosts static frontend files | norwayeast | ~£1 |

**Total estimated cost: ~£27/month**

### Live URLs
| Service | URL |
|---|---|
| Frontend | https://pixsharestore2026.z1.web.core.windows.net |
| Backend API | https://pixshare-api.azurewebsites.net |

---

## 3. Prerequisites

### Tools Required
| Tool | Version | Purpose |
|---|---|---|
| Docker Desktop | Latest | Build & run containers locally |
| Python | 3.14+ | Backend development |
| Azure CLI | 2.x | Manage Azure resources |
| Git | Any | Source control |

### Install Docker Desktop
1. Download from: https://www.docker.com/products/docker-desktop/
2. Run installer as Administrator
3. Enable WSL 2 when prompted
4. Restart PC after installation

**Fix ownership error if encountered:**
```powershell
# Run PowerShell as Administrator
takeown /F "C:\ProgramData\DockerDesktop" /R /D Y
icacls "C:\ProgramData\DockerDesktop" /grant Administrators:F /T
Remove-Item -Path "C:\ProgramData\DockerDesktop" -Recurse -Force
# Then reinstall Docker Desktop from official website (not Microsoft Store)
```

### Install Python
1. Download from: https://www.python.org/downloads/
2. Run installer as Administrator
3. ⚠️ CRITICAL: Tick **"Add python.exe to PATH"** before clicking Install

**Verify installation:**
```powershell
python --version
python -m pip --version
```

### Install Azure CLI
1. Download from: https://aka.ms/installazurecliwindows
2. Run the `.msi` installer
3. Verify:
```powershell
az --version
```

---

## 4. Local Setup & Testing

### Clone the Repository
```powershell
git clone https://github.com/Mujeeb117/pix-app.git
cd pix-app
```

### Project Structure
```
pix-app/
├── .github/
│   └── workflows/
│       └── azure-backend-container.yml   # CI/CD pipeline
├── azure/
│   └── DEPLOY.txt                        # Deployment notes
├── backend/
│   ├── app.py                            # Flask application
│   ├── config.py                         # Configuration
│   ├── models.py                         # Database models
│   ├── requirements.txt                  # Python dependencies
│   ├── Dockerfile                        # Container definition
│   └── .dockerignore
├── frontend/
│   ├── index.html                        # Home page
│   ├── Login.html                        # Login/Signup
│   ├── Creator.html                      # Creator dashboard
│   ├── Gallery.html                      # Photo gallery
│   ├── manage-users.html                 # User management
│   ├── Auth.js                           # Authentication helper
│   ├── config.js                         # API base URL config
│   ├── style.css                         # Stylesheet
│   └── staticwebapp.config.json
├── docker-compose.yml                    # Local development
└── README.md
```

### Run Locally with Docker
```powershell
# Start Docker Desktop first, then:
cd E:\mujeeb\pix-app
docker compose up --build
```

This starts 3 services:
- **PostgreSQL** on port 5432
- **Backend API** on http://localhost:5001
- **Frontend** on http://localhost:5500

**Test locally:**
- Frontend: http://localhost:5500
- API health: http://localhost:5001

**Stop containers:**
```powershell
docker compose down
```

---

## 5. Azure CLI Setup

### Login to Azure
```powershell
az login
```
- Browser opens automatically
- Select **"Azure for Students"** (subscription #3)
- Enter number `3` and press Enter

### Set the Correct Subscription
```powershell
az account set --subscription "7b33acf8-28ff-42f4-b876-f7c45ca8a918"
```

### Verify Active Account
```powershell
az account show
```
Should show: `"name": "Azure for Students"`

### Allowed Regions (Ulster University Policy)
The university Azure policy restricts deployments to these regions only:
```
swedencentral, norwayeast, italynorth, spaincentral, francecentral
```

---

## 6. Create Azure Resources

### Step 1 — Create Resource Group
```powershell
az group create --name pixshare-rg --location uksouth
```

### Step 2 — Register Required Providers
```powershell
# Register Container Registry provider
az provider register --namespace Microsoft.ContainerRegistry

# Check registration status (wait for "Registered")
az provider show --namespace Microsoft.ContainerRegistry --query "registrationState"

# Register PostgreSQL provider
az provider register --namespace Microsoft.DBforPostgreSQL

# Check registration status
az provider show --namespace Microsoft.DBforPostgreSQL --query "registrationState"
```

### Step 3 — Create Azure Container Registry (ACR)
```powershell
az acr create `
  --resource-group pixshare-rg `
  --name pixshareacr `
  --sku Basic `
  --admin-enabled true `
  --location norwayeast
```

**Key output:**
- Login server: `pixshareacr.azurecr.io`

### Step 4 — Create PostgreSQL Flexible Server
```powershell
az postgres flexible-server create `
  --resource-group pixshare-rg `
  --name pixshare-db `
  --location norwayeast `
  --admin-user pixshareuser `
  --admin-password "PixShare@123" `
  --sku-name Standard_B1ms `
  --tier Burstable `
  --storage-size 32 `
  --version 16 `
  --yes
```

**Key output:**
- Host: `pixshare-db.postgres.database.azure.com`
- Username: `pixshareuser`
- Password: `PixShare@123`

### Step 5 — Create PixShare Database
```powershell
az postgres flexible-server db create `
  --resource-group pixshare-rg `
  --server-name pixshare-db `
  --database-name pixshare
```

### Step 6 — Allow Azure Services to Access Database
```powershell
az postgres flexible-server firewall-rule create `
  --resource-group pixshare-rg `
  --name pixshare-db `
  --rule-name AllowAzureServices `
  --start-ip-address 0.0.0.0 `
  --end-ip-address 0.0.0.0
```

### Step 7 — Create App Service Plan
```powershell
# Note: swedencentral used because norwayeast had no B1 capacity
az appservice plan create `
  --name pixshare-plan `
  --resource-group pixshare-rg `
  --location swedencentral `
  --is-linux `
  --sku B1
```

### Step 8 — Create Web App (Backend)
```powershell
az webapp create `
  --resource-group pixshare-rg `
  --plan pixshare-plan `
  --name pixshare-api `
  --deployment-container-image-name mcr.microsoft.com/appsvc/staticsite:latest
```

**Key output:**
- Default hostname: `pixshare-api.azurewebsites.net`

---

## 7. Build & Push Docker Image

### Step 1 — Start Docker Desktop
Open Docker Desktop and wait for it to fully start (whale icon steady in taskbar).

### Step 2 — Login to ACR
```powershell
az acr login --name pixshareacr
```

### Step 3 — Build Docker Image
```powershell
cd E:\mujeeb\pix-app
docker build -t pixshareacr.azurecr.io/pixshare-backend:latest ./backend
```

### Step 4 — Push Image to ACR
```powershell
docker push pixshareacr.azurecr.io/pixshare-backend:latest
```

### Step 5 — Get ACR Credentials
```powershell
az acr credential show --name pixshareacr
```
Note the username and password1 from the output.

### Step 6 — Connect App Service to ACR Image
```powershell
az webapp config container set `
  --name pixshare-api `
  --resource-group pixshare-rg `
  --container-image-name pixshareacr.azurecr.io/pixshare-backend:latest `
  --container-registry-url https://pixshareacr.azurecr.io `
  --container-registry-user pixshareacr `
  --container-registry-password <YOUR_ACR_PASSWORD>
```

---

## 8. Configure App Service

### Set Environment Variables
Go to **Azure Portal → pixshare-api → Settings → Environment variables** and add:

| Name | Value |
|---|---|
| `DATABASE_URL` | `postgresql://pixshareuser:PixShare%40123@pixshare-db.postgres.database.azure.com/pixshare?sslmode=require` |
| `SECRET_KEY` | `pixshare-ultra-secret-key-2026` |
| `CORS_ORIGINS` | `https://pixsharestore2026.z1.web.core.windows.net` |
| `PORT` | `8080` |

> ⚠️ **Important:** The `@` in the password must be encoded as `%40` in the DATABASE_URL.
> Use `PixShare%40123` NOT `PixShare@123`

Click **Apply** → **Confirm** to save.

### Restart App Service
```powershell
az webapp restart --name pixshare-api --resource-group pixshare-rg
```

### Test Backend API
```powershell
curl https://pixshare-api.azurewebsites.net
```
Expected response: `{"message":"PixShare API Running ✨"}`

---

## 9. Deploy Frontend

### Step 1 — Update config.js with Live API URL
Edit `frontend/config.js`:
```javascript
window.__PX_API_BASE__ = "https://pixshare-api.azurewebsites.net";
```

### Step 2 — Create Storage Account
```powershell
az storage account create `
  --name pixsharestore2026 `
  --resource-group pixshare-rg `
  --location norwayeast `
  --sku Standard_LRS `
  --kind StorageV2
```

### Step 3 — Enable Static Website Hosting
```powershell
az storage blob service-properties update `
  --account-name pixsharestore2026 `
  --static-website `
  --index-document index.html `
  --404-document index.html
```

### Step 4 — Upload Frontend Files
```powershell
az storage blob upload-batch `
  --account-name pixsharestore2026 `
  --source E:\mujeeb\pix-app\frontend `
  --destination '$web' `
  --overwrite
```

### Step 5 — Get Website URL
```powershell
az storage account show `
  --name pixsharestore2026 `
  --resource-group pixshare-rg `
  --query "primaryEndpoints.web" `
  --output tsv
```
URL: `https://pixsharestore2026.z1.web.core.windows.net/`

### Step 6 — Update CORS to Allow Frontend URL
In **Azure Portal → pixshare-api → Environment variables**, update `CORS_ORIGINS` to:
```
https://pixsharestore2026.z1.web.core.windows.net
```
Then restart the App Service.

---

## 10. CI/CD Pipeline

### Backend Pipeline (.github/workflows/azure-backend-container.yml)
Triggers automatically on push to `main` branch when backend files change.

```yaml
name: Azure backend (container)

on:
  push:
    branches: [main]
    paths:
      - 'backend/**'
  workflow_dispatch:

env:
  IMAGE_NAME: pixshare-backend

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Log in to Azure
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Log in to Azure Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ secrets.AZURE_REGISTRY }}
          username: ${{ secrets.AZURE_REGISTRY_USERNAME }}
          password: ${{ secrets.AZURE_REGISTRY_PASSWORD }}

      - name: Build and push image
        uses: docker/build-push-action@v6
        with:
          context: ./backend
          push: true
          tags: ${{ secrets.AZURE_REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}

      - name: Deploy to Azure Web App
        uses: azure/webapps-deploy@v3
        with:
          app-name: ${{ secrets.AZURE_WEBAPP_NAME }}
          slot-name: production
          images: ${{ secrets.AZURE_REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
```

### Required GitHub Secrets
Go to **GitHub → pix-app repo → Settings → Secrets and variables → Actions** and add:

| Secret Name | Value |
|---|---|
| `AZURE_CREDENTIALS` | Output of `az ad sp create-for-rbac --sdk-auth` |
| `AZURE_RESOURCE_GROUP` | `pixshare-rg` |
| `AZURE_WEBAPP_NAME` | `pixshare-api` |
| `AZURE_REGISTRY` | `pixshareacr.azurecr.io` |
| `AZURE_REGISTRY_USERNAME` | `pixshareacr` |
| `AZURE_REGISTRY_PASSWORD` | ACR password from `az acr credential show` |

### Generate Azure Credentials for GitHub
```powershell
az ad sp create-for-rbac `
  --name "pixshare-github-actions" `
  --role contributor `
  --scopes /subscriptions/7b33acf8-28ff-42f4-b876-f7c45ca8a918/resourceGroups/pixshare-rg `
  --sdk-auth
```
Copy the entire JSON output and paste as `AZURE_CREDENTIALS` secret.

### Frontend Redeployment (Manual)
To redeploy frontend after changes:
```powershell
az storage blob upload-batch `
  --account-name pixsharestore2026 `
  --source E:\mujeeb\pix-app\frontend `
  --destination '$web' `
  --overwrite
```

---

## 11. Verify Deployment

### Backend Health Check
```powershell
curl https://pixshare-api.azurewebsites.net
# Expected: {"message":"PixShare API Running ✨"}
```

### Frontend Check
Open in browser: https://pixsharestore2026.z1.web.core.windows.net

### Full App Test Checklist
- [ ] Home page loads
- [ ] Login page loads
- [ ] Sign up as consumer user works
- [ ] Login as creator (Admin Mujeeb / Mujeeb123) works
- [ ] Creator can upload image with title/caption/location
- [ ] Consumer can browse gallery
- [ ] Consumer can search images
- [ ] Consumer can comment on images
- [ ] Consumer can rate images (1-5 stars)
- [ ] Consumer can react (like/happy/love)
- [ ] Creator can view image stats
- [ ] Creator can manage/delete consumer users

---

## 12. Troubleshooting

### Container exits with code 3
**Cause:** `@` symbol in password not URL-encoded in DATABASE_URL
**Fix:** Use `PixShare%40123` instead of `PixShare@123` in DATABASE_URL

### 503 Service Unavailable
**Cause:** Container still starting or crashed
**Fix:**
```powershell
az webapp log tail --name pixshare-api --resource-group pixshare-rg
az webapp restart --name pixshare-api --resource-group pixshare-rg
```

### "Cannot reach API" on frontend
**Cause:** CORS_ORIGINS not set to frontend URL
**Fix:** Update CORS_ORIGINS in App Service environment variables

### Provider not registered
```powershell
az provider register --namespace Microsoft.ContainerRegistry
az provider register --namespace Microsoft.DBforPostgreSQL
az provider register --namespace Microsoft.Web
az provider register --namespace Microsoft.Storage
```

### Region policy error (RequestDisallowedByAzure)
**Allowed regions:** `swedencentral`, `norwayeast`, `italynorth`, `spaincentral`, `francecentral`
Use one of these for all resource creation commands.

### Docker not found
Start Docker Desktop from the Start menu and wait for it to fully load before running docker commands.

### Azure subscription not found after GitHub login
```powershell
az login
az account set --subscription "7b33acf8-28ff-42f4-b876-f7c45ca8a918"
```

---

## 13. Resource Summary

### All Azure Resources Created
| Resource Type | Name | Location | Status |
|---|---|---|---|
| Resource Group | `pixshare-rg` | uksouth | ✅ Active |
| Container Registry | `pixshareacr` | norwayeast | ✅ Active |
| PostgreSQL Server | `pixshare-db` | norwayeast | ✅ Active |
| App Service Plan | `pixshare-plan` | swedencentral | ✅ Active |
| App Service | `pixshare-api` | swedencentral | ✅ Active |
| Storage Account | `pixsharestore2026` | norwayeast | ✅ Active |

### Connection Strings & Credentials
| Item | Value |
|---|---|
| Backend API URL | https://pixshare-api.azurewebsites.net |
| Frontend URL | https://pixsharestore2026.z1.web.core.windows.net |
| ACR Login Server | pixshareacr.azurecr.io |
| DB Host | pixshare-db.postgres.database.azure.com |
| DB Name | pixshare |
| DB User | pixshareuser |
| Creator Login | Admin Mujeeb / Mujeeb123 |

### Cost Estimate
| Resource | Monthly Cost |
|---|---|
| Container Registry (Basic) | ~£4 |
| PostgreSQL (B1ms Burstable) | ~£12 |
| App Service Plan (B1) | ~£10 |
| Storage Account | ~£1 |
| **Total** | **~£27/month** |

> 💡 **Tip:** Delete or stop resources after submission to save your Azure for Students credit (£70 total).

### To Delete All Resources After Submission
```powershell
az group delete --name pixshare-rg --yes --no-wait
```
⚠️ This permanently deletes everything. Only run after submission.

---

*Document prepared for MSc Scalable Software Solutions — Ulster University*
*Deployment completed: May 2026*
*App: PixShare — Cloud-native photo sharing platform*
