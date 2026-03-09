# SignalCraft (Zenalys) - Agent Instructions

## 🚨 CRITICAL: Project Hosting Context

**This project is hosted on a VPS using Docker.**

- **All code changes MUST be committed and pushed to Git**
- **The user deploys by pulling Git and rebuilding Docker containers on VPS**
- **NEVER make changes directly on VPS - always commit to Git first**

## 📋 Development Workflow (MUST FOLLOW)

### For ANY Code Changes:

1. **Make changes to the codebase**
2. **Test locally** (optional, if user requests): `docker-compose up -d --build`
3. **Commit to Git:**
   ```bash
   git add -A
   git commit -m "description of changes"
   git push origin main
   ```
4. **Inform user to deploy on VPS:**
   ```bash
   cd /home/signalcraft && git pull origin main && docker compose up -d --build
   ```

## ⚠️ Important Rules

- **DO NOT** assume the agent can directly access or restart services on the VPS
- **DO NOT** run `docker` commands locally unless explicitly asked
- **ALWAYS** remind the user to pull and deploy on VPS after making changes
- **NEVER** suggest editing files directly on VPS via SSH
- Frontend builds happen inside Docker container during `docker compose up -d --build`

## 🔧 VPS Environment Details

| Component | Location | Port |
|-----------|----------|------|
| Working Directory | `/home/signalcraft` | - |
| Frontend (Next.js) | `frontend/` | 3000 |
| Backend (FastAPI) | `backend/` | 8001 |
| PostgreSQL | Docker container | 5432 (internal) |
| Redis | Docker container | 6379 (internal) |
| Nginx Config | `/etc/nginx/sites-available/zenalys.com` | 80/443 |

**Production Domain:** zenalys.com

## 📁 Project Structure

```
/home/signalcraft/
├── frontend/          # Next.js application
├── backend/           # FastAPI application
├── data/              # Historical candle data
├── docker-compose.yml # Docker orchestration
├── nginx-mobile.conf  # Nginx configuration (mobile-responsive)
└── .env               # Backend environment variables
```

## 🐛 Debugging Guidelines

When investigating issues:

1. **Check Docker logs:**
   ```bash
   docker logs signalcraft-frontend --tail 50
   docker logs signalcraft-backend --tail 50
   ```

2. **Check container status:**
   ```bash
   docker-compose ps
   ```

3. **Check relevant config files, code, AND logs** before drawing conclusions

## 🎯 Architecture Overview

```
User → Nginx (SSL/Reverse Proxy) → Frontend (Next.js:3000)
                              ↓
                          Backend (FastAPI:8001)
                              ↓
                    PostgreSQL + Redis + Data Files
```

- **Frontend:** Next.js 14 (static export, served by Nginx)
- **Backend:** FastAPI with PostgreSQL + Redis
- **Mobile-responsive design** (no PWA features)
- **CORS:** Backend allows requests from frontend domain
