# 🚀 ISP AI Support - Production Deployment Guide

## 📋 Prerequisites

1. **Server Requirements:**
   - VPS/Cloud server with:
     - Ubuntu 20.04+ or similar Linux
     - Minimum 2GB RAM, 2 CPU cores
     - 20GB storage
     - Public IP address
   - Docker & Docker Compose installed

2. **Credentials Needed:**
   - OpenAI API Key
   - Qiscus App ID, Secret Key, Webhook Secret
   - Ticketing System API credentials (optional)
   - Domain name (recommended)

---

## 🛠️ Installation Steps

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Logout and login again for docker group to take effect
```

### 2. Deploy Application

```bash
# Create application directory
mkdir -p /opt/isp-ai-support
cd /opt/isp-ai-support

# Upload all files to this directory
# Or clone from git repository

# Create logs directory
mkdir -p logs logs/nginx

# Set permissions
chmod +x *.sh
```

### 3. Configuration

```bash
# Copy environment template
cp .env.production .env

# Edit with your credentials
nano .env
```

**Fill in these values:**
```bash
# OpenAI
OPENAI_API_KEY=sk-proj-your-real-key

# Qiscus
QISCUS_APP_ID=xwtmp-x50lgehxirp1uwd
QISCUS_SECRET_KEY=your-secret-key
QISCUS_SECRET=your-webhook-secret

# Ticketing (optional)
TICKETING_API_URL=https://your-system.com/api/v1
TICKETING_API_KEY=your-api-key

# Redis (optional password)
REDIS_PASSWORD=strong-redis-password
```

### 4. Start Services

```bash
# Build and start
docker-compose up -d --build

# Check status
docker-compose ps

# View logs
docker-compose logs -f api
```

### 5. Verify Deployment

```bash
# Check health
curl http://localhost:8000/health

# Should return:
# {"status": "healthy", "components": {...}}
```

---

## 🌐 Domain & SSL Setup

### Option A: With Domain (Recommended)

1. **Point Domain to Server:**
   - Add A record: `ai-support.yourdomain.com` → Your server IP

2. **Get SSL Certificate (Let's Encrypt):**
```bash
# Install Certbot
sudo apt install certbot

# Get certificate
sudo certbot certonly --standalone -d ai-support.yourdomain.com

# Copy certificates
sudo mkdir -p ssl
sudo cp /etc/letsencrypt/live/ai-support.yourdomain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/ai-support.yourdomain.com/privkey.pem ssl/key.pem
sudo chown $USER:$USER ssl/*.pem
```

3. **Update nginx.conf:**
```bash
nano nginx.conf

# Change server_name to your domain
# Uncomment HTTPS section
```

4. **Restart:**
```bash
docker-compose restart nginx
```

### Option B: Without Domain (IP Only)

Use Ngrok for testing or keep HTTP only:

```bash
# Remove nginx service from docker-compose.yml
# Or keep it on port 80 only
```

---

## 🔗 Setup Qiscus Webhook

1. **Get Webhook URL:**
   - With domain: `https://ai-support.yourdomain.com/webhook/qiscus`
   - Without domain: `http://your-server-ip:8000/webhook/qiscus`

2. **Configure in Qiscus:**
   - Login to Qiscus Dashboard
   - Settings > Webhooks
   - Add webhook URL
   - Enable event: `post_comment_mobile`
   - Save

3. **Test:**
   - Send message from WhatsApp to Qiscus number
   - Check logs: `docker-compose logs -f api`
   - Should see message processing and AI response

---

## 📊 Monitoring & Maintenance

### Check Logs

```bash
# API logs
docker-compose logs -f api

# All services
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100 api

# Nginx logs
tail -f logs/nginx/access.log
tail -f logs/nginx/error.log
```

### View Statistics

```bash
# System stats
curl http://localhost:8000/stats

# Active sessions
curl http://localhost:8000/sessions

# Health check
curl http://localhost:8000/health
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart api

# Full rebuild
docker-compose down
docker-compose up -d --build
```

### Update Application

```bash
# Pull latest code
git pull  # or upload new files

# Rebuild and restart
docker-compose down
docker-compose up -d --build
```

---

## 🔒 Security Best Practices

1. **Firewall Configuration:**
```bash
# Allow only necessary ports
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

2. **Regular Updates:**
```bash
# Update system weekly
sudo apt update && sudo apt upgrade -y

# Update Docker images monthly
docker-compose pull
docker-compose up -d
```

3. **Backup Redis Data:**
```bash
# Backup script
docker exec isp-ai-redis-prod redis-cli SAVE
docker cp isp-ai-redis-prod:/data/dump.rdb ./backup/redis-$(date +%Y%m%d).rdb
```

4. **Monitor Resources:**
```bash
# Check resource usage
docker stats

# Check disk space
df -h

# Check logs size
du -sh logs/
```

---

## 🐛 Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs api

# Check port conflicts
sudo netstat -tulpn | grep 8000

# Rebuild from scratch
docker-compose down -v
docker-compose up -d --build
```

### High Memory Usage

```bash
# Restart services
docker-compose restart

# Check memory limits in docker-compose.yml
# Adjust if needed
```

### AI Response Slow

```bash
# Check OpenAI API status
curl https://status.openai.com/api/v2/status.json

# Check Redis connection
docker-compose logs redis

# Consider upgrading OpenAI model or server specs
```

### No Response from Qiscus

```bash
# Verify credentials in .env
cat .env | grep QISCUS

# Test manually
curl -X POST "http://localhost:8000/test/message?customer_id=test&message=hello"

# Check Qiscus webhook configuration
```

---

## 📈 Scaling for Production

### For Higher Traffic (500+ chats/day):

1. **Increase Workers:**
```yaml
# In docker-compose.yml, change:
command: gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

2. **Add Load Balancer:**
   - Use multiple API containers
   - Nginx upstream load balancing

3. **Use External Redis:**
   - Managed Redis (AWS ElastiCache, Redis Cloud)
   - Better reliability and performance

4. **Add Monitoring:**
   - Prometheus + Grafana
   - Sentry for error tracking
   - Uptime monitoring (UptimeRobot)

---

## 💰 Cost Estimation

**Monthly costs for 200 chats/day:**

- VPS (DigitalOcean, Linode): $12-24/month
- OpenAI API: $24/month (full AI responses)
- Domain: $12/year
- SSL: Free (Let's Encrypt)

**Total: ~$40/month**

---

## 📞 Support Checklist

Before going live:

- [ ] All credentials configured in `.env`
- [ ] Health check returns "healthy"
- [ ] Test message works via `/test/message`
- [ ] Qiscus webhook configured
- [ ] SSL certificate installed (if using domain)
- [ ] Firewall configured
- [ ] Backup script setup
- [ ] Monitoring alerts configured
- [ ] Team trained on viewing logs

---

## 🎉 You're Ready!

Your AI support system is now running in production.

**Test it:**
1. Send WhatsApp message to Qiscus number
2. AI should respond automatically
3. Check logs to verify processing
4. Monitor for 24 hours to ensure stability

**Need help?** Check logs first, then contact support.
