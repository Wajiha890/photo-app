# Lumina

**Lumina** is a full-stack photo and video sharing web application built for the **Scalable Software Solutions** module at Ulster University. Users can upload, explore, rate, comment and react to images and videos. Creators manage content while consumers browse and interact.

---

## Live Application

| Component | URL |
|-----------|-----|
| Frontend | https://luminastore2026.z1.web.core.windows.net |
| Backend API | https://lumina-api.azurewebsites.net |

---

## Features

- Upload photos and videos with metadata (title, caption, location, people)
- Browse and search media by title, caption, location and people
- Rate media (1-5 stars) and leave comments
- React to posts (like, happy, love)
- Creator dashboard to manage uploads
- Admin dashboard to manage users and content
- JWT-based authentication with role-based access control (Creator / Consumer)
- Responsive UI with HTML, CSS and Vanilla JavaScript

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Flask, Gunicorn |
| Frontend | HTML, CSS, Vanilla JavaScript |
| Database | PostgreSQL (Azure Flexible Server) |
| Media Storage | Azure Blob Storage (private container + SAS URLs) |
| Authentication | JWT (JSON Web Tokens) |
| Containerisation | Docker, Docker Compose |
| Container Registry | Azure Container Registry (ACR) |
| Hosting | Azure App Service (Linux, B1) |
| Frontend Hosting | Azure Blob Storage (Static Website) |

---

## Azure Architecture

```
Browser
   │
   ├── Frontend (Static HTML/JS/CSS)
   │       └── Azure Blob Storage ($web container)
   │               https://luminastore2026.z1.web.core.windows.net
   │
   └── Backend API (Flask + Gunicorn in Docker)
           └── Azure App Service
                   https://lumina-api.azurewebsites.net
                   │
                   ├── Azure PostgreSQL Flexible Server
                   │       (users, images, comments, ratings, reactions)
                   │
                   └── Azure Blob Storage (media container)
                           (uploaded photos and videos via private SAS URLs)
```

---

## Media Storage

Uploaded photos and videos are stored in a **private Azure Blob Storage container** (`media`). Each file is assigned a unique UUID filename and a **SAS (Shared Access Signature) URL** is generated at upload time — valid for 5 years. This URL is stored in the database and used by the frontend to display media without requiring public blob access.

---

## Database Schema

| Table | Key Fields |
|-------|-----------|
| `user` | id, username, password, role, created_at |
| `image` | id, title, caption, location, people, image_url, media_type, created_at |
| `comment` | id, image_id, user_id, text, created_at |
| `rating` | id, image_id, user_id, value (1-5), created_at |
| `reaction` | id, image_id, user_id, reaction_type, created_at |

---

## Local Development

### Prerequisites
- Docker Desktop
- Git

### Setup

1. Clone the repository:
```bash
git clone https://github.com/Mujeeb117/pix-app.git
cd pix-app
```

2. Create a `.env` file in the root directory:
```env
AZURE_STORAGE_CONNECTION_STRING=your_azure_storage_connection_string
```

3. Start the app with Docker Compose:
```bash
docker compose up --build
```

4. Open in browser:
- Frontend: http://127.0.0.1:5500
- Backend API: http://127.0.0.1:5001

> The local backend connects to Azure Blob Storage using the connection string in `.env`.
> A local PostgreSQL container is used for the database in dev.

---

## Deployment to Azure

### Azure Resources Required

| Resource | Name | Region |
|----------|------|--------|
| Resource Group | lumina-rg | Norway East |
| Container Registry | luminaacr | Norway East |
| PostgreSQL Flexible Server | lumina-db | Norway East |
| App Service Plan | lumina-plan | Sweden Central |
| App Service | lumina-api | Sweden Central |
| Storage Account | luminastore2026 | Norway East |

### Deploy Backend

```bash
# Login to Azure and ACR
az login
az acr login --name luminaacr

# Build and push Docker image
docker build -t luminaacr.azurecr.io/lumina-backend:latest ./backend
docker push luminaacr.azurecr.io/lumina-backend:latest

# Restart App Service to pull new image
az webapp restart --name lumina-api --resource-group lumina-rg
```

### Deploy Frontend

```bash
az storage blob upload-batch \
  --account-name luminastore2026 \
  --source ./frontend \
  --destination '$web' \
  --overwrite
```

### Required App Service Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Azure PostgreSQL connection string |
| `SECRET_KEY` | JWT signing key |
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Blob Storage connection string |
| `CORS_ORIGINS` | Allowed frontend origins |
| `PORT` | App port (8000) |

---

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Production — deployed to Azure |
| `dev` | Development — tested locally before merging |

---

## Viewing Data in Azure

**Media files (photos/videos):**
> Azure Portal → luminastore2026 → Containers → media

**Database metadata (titles, comments, ratings):**
> Azure Portal → lumina-db → Connect → run SQL queries against `lumina` database

---

## MSc Module

**Module:** Scalable Software Solutions
**University:** Ulster University
