# 🚀 SignalCraft Deployment Guide - Contabo VPS

Complete step-by-step guide to deploy SignalCraft with PostgreSQL on Contabo VPS.

---

## 📋 Prerequisites

- Contabo VPS (Ubuntu 22.04 or later)
- SSH access to your VPS
- Domain name (optional, for HTTPS)
- Local SignalCraft development setup

---

## 📦 Part 1: Local Setup (Before Deployment)

### Step 1: Start PostgreSQL Locally

```bash
cd /Users/sanim/Downloads/sunny/Python/AIML/Pybankers/Pytrader

# Start PostgreSQL with Docker
docker-compose up -d postgres

# Check it's running
docker ps | grep signalcraft-db
```

### Step 2: Migrate from SQLite to PostgreSQL

```bash
# Run database initialization
python3 backend/scripts/migrate_db.py

# Create admin user
python3 backend/scripts/create_admin.py
```

### Step 3: Test Locally

```bash
# Update .env.db
DB_TYPE=postgres

# Start backend
cd backend
uvicorn app.main:app --reload --port 8001

# In another terminal, start frontend
cd frontend
npm run dev
```

Visit `http://localhost:3000` and test everything works.

---

## 🖥️ Part 2: VPS Setup (Contabo)

### Step 1: Connect to VPS

```bash
ssh root@your-vps-ip
```

### Step 2: Install Dependencies

```bash
# Update system
apt update && apt upgrade -y

# Install essential tools
apt install -y curl git wget vim ufw

# Install Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs

# Install Python 3.10
apt install -y python3 python3-pip python3-venv

# Install PostgreSQL client (for migration)
apt install -y postgresql-client

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
usermod -aG docker $USER

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Exit and reconnect for Docker group to take effect
exit
```

Reconnect: `ssh root@your-vps-ip`

### Step 3: Clone Your Project

**Option A: Git Repository (Recommended)**
```bash
cd /home
git clone https://github.com/yourusername/Pytrader.git signalcraft
cd signalcraft
```

**Option B: SCP Transfer**
```bash
# On your local machine
cd /Users/sanim/Downloads/sunny/Python/AIML/Pybankers/Pytrader
tar -czf signalcraft.tar.gz \
  --exclude='node_modules' \
  --exclude='.next' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  .

scp signalcraft.tar.gz root@your-vps-ip:/home/

# On VPS
cd /home
tar -xzf signalcraft.tar.gz -C signalcraft
cd signalcraft
```

### Step 4: Configure Environment

```bash
cd /home/signalcraft

# Copy environment files
cp .env.db.example .env.db
cp .env.example .env  # If you have one

# Edit .env.db
vim .env.db
```

Update `.env.db`:
```env
DB_TYPE=postgres
DB_HOST=localhost
DB_PORT=5432
DB_USER=signalcraft
DB_PASSWORD=YOUR_STRONG_PASSWORD_HERE
DB_NAME=signalcraft
```

### Step 5: Start PostgreSQL

```bash
# Start PostgreSQL container
docker-compose up -d postgres

# Wait for it to be ready
sleep 10

# Check it's running
docker ps | grep signalcraft-db
```

### Step 6: Import Your Database

**Option A: Import from Local Backup**

On your local machine:
```bash
# Export local database
python3 backend/scripts/export_db.py

# Copy to VPS
scp backups/signalcraft_backup_*.sql root@your-vps-ip:/home/signalcraft/backups/
```

On VPS:
```bash
cd /home/signalcraft

# Import database
python3 backend/scripts/import_db.py backups/signalcraft_backup_*.sql
```

**Option B: Create Fresh Database**

```bash
# Run migrations
python3 backend/scripts/migrate_db.py

# Create admin user
python3 backend/scripts/create_admin.py
```

### Step 7: Setup Backend

```bash
cd /home/signalcraft/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt  # If you have requirements.txt
# Or install manually:
pip install fastapi uvicorn python-dotenv psycopg2-binary python-jose[cryptography] passlib

# Test backend
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Test: `http://your-vps-ip:8001/health`

### Step 8: Setup Backend as Systemd Service

```bash
# Create service file
cat > /etc/systemd/system/signalcraft-backend.service << EOF
[Unit]
Description=SignalCraft Backend API
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/home/signalcraft/backend
Environment="PATH=/home/signalcraft/backend/venv/bin"
ExecStart=/home/signalcraft/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable signalcraft-backend
systemctl start signalcraft-backend

# Check status
systemctl status signalcraft-backend
```

### Step 9: Setup Frontend

```bash
cd /home/signalcraft/frontend

# Install dependencies
npm install

# Build for production
npm run build

# Install PM2 for process management
npm install -g pm2

# Start Next.js production server
pm2 start npm --name "signalcraft-frontend" -- start

# Save PM2 configuration
pm2 save

# Setup PM2 to start on boot
pm2 startup systemd
```

### Step 10: Setup Nginx (Reverse Proxy)

```bash
# Install Nginx
apt install -y nginx

# Create Nginx config
cat > /etc/nginx/sites-available/signalcraft << EOF
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain or VPS IP

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header Host \$http_host;
    }

    # Admin API
    location /admin/ {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
    }
}
EOF

# Enable site
ln -s /etc/nginx/sites-available/signalcraft /etc/nginx/sites-enabled/

# Test and reload Nginx
nginx -t
systemctl restart nginx
```

### Step 11: Setup Firewall

```bash
# Allow SSH, HTTP, HTTPS
ufw allow OpenSSH
ufw allow 'Nginx Full'

# Enable firewall
ufw enable

# Check status
ufw status
```

### Step 12: Setup SSL (Optional but Recommended)

```bash
# Install Certbot
apt install -y certbot python3-certbot-nginx

# Get SSL certificate
certbot --nginx -d your-domain.com

# Auto-renewal is setup automatically
# Test renewal
certbot renew --dry-run
```

---

## ✅ Part 3: Verify Deployment

### Check All Services

```bash
# Backend
systemctl status signalcraft-backend

# Frontend
pm2 status

# PostgreSQL
docker ps | grep signalcraft-db

# Nginx
systemctl status nginx
```

### Test URLs

- **Frontend:** `http://your-vps-ip` or `https://your-domain.com`
- **Backend:** `http://your-vps-ip:8001/health`
- **Admin Panel:** `http://your-vps-ip/admin/login`

---

## 🔄 Part 4: Deployment Workflow (Future Updates)

### Deploy New Changes

```bash
# On VPS
cd /home/signalcraft

# Pull latest changes
git pull origin main

# Restart backend
systemctl restart signalcraft-backend

# Rebuild and restart frontend
cd frontend
npm run build
pm2 restart signalcraft-frontend
```

### Backup Database

```bash
cd /home/signalcraft

# Export database
python3 backend/scripts/export_db.py

# Copy to local machine
scp backups/signalcraft_backup_*.sql your-local-machine:/backups/
```

---

## 🛠️ Troubleshooting

### Backend Not Starting

```bash
# Check logs
journalctl -u signalcraft-backend -f

# Check if port is in use
netstat -tulpn | grep 8001
```

### Frontend Not Accessible

```bash
# Check PM2 logs
pm2 logs signalcraft-frontend

# Restart frontend
pm2 restart signalcraft-frontend
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker ps | grep signalcraft-db

# Check logs
docker logs signalcraft-db

# Restart PostgreSQL
docker-compose restart postgres
```

### Nginx Issues

```bash
# Test configuration
nginx -t

# Check error logs
tail -f /var/log/nginx/error.log

# Restart Nginx
systemctl restart nginx
```

---

## 📊 Monitoring

### Setup Basic Monitoring

```bash
# Install htop for resource monitoring
apt install -y htop

# Check disk usage
df -h

# Check memory
free -h

# Monitor logs
tail -f /var/log/nginx/access.log
```

---

## 🔐 Security Checklist

- [ ] Changed default database password
- [ ] Setup firewall (UFW)
- [ ] Enabled SSL/HTTPS
- [ ] Changed JWT secret in .env
- [ ] Regular backups configured
- [ ] SSH key authentication (disable password login)
- [ ] Fail2ban installed (optional)

---

## 📞 Support

If you encounter issues:
1. Check logs (`journalctl`, `pm2 logs`, `docker logs`)
2. Verify all services are running
3. Check firewall rules
4. Review Nginx configuration

---

**🎉 Congratulations! Your SignalCraft platform is now live on Contabo VPS!**
