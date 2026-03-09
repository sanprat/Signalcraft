# Agent Memory: Project Deployment Context

## 🚨 CRITICAL: VPS Docker Deployment

**This project (Pytrader/SignalCraft/Zenalys) is hosted on a VPS using Docker.**

### Deployment Workflow (MUST FOLLOW FOR ALL CHANGES)

1. **Make code changes** to the project
2. **Commit to Git:**
   ```bash
   git add -A
   git commit -m "meaningful commit message"
   git push origin main
   ```
3. **Inform user to deploy on VPS:**
   ```bash
   cd /home/signalcraft && git pull origin main && docker compose up -d --build
   ```

### Key Rules

- **NEVER** make changes directly on VPS - always commit to Git first
- **ALWAYS** push changes to Git after making modifications
- **DO NOT** assume agent can directly access VPS services
- **DO NOT** run docker commands locally unless explicitly requested
- Frontend builds happen inside Docker container during deployment

### VPS Environment

| Component | Path/Port |
|-----------|-----------|
| Working Directory | `/home/signalcraft` |
| Frontend | `frontend/` (port 3000) |
| Backend | `backend/` (port 8001) |
| Domain | zenalys.com |
| Nginx Config | `/etc/nginx/sites-available/zenalys.com` |

### Files to Reference

- `QWEN.md` - Qwen-specific memories and guidelines
- `AGENTS.md` - General agent instructions
- `DEPLOYMENT.md` - Detailed deployment guide
- `docker-compose.yml` - Docker orchestration
