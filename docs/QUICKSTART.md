# 🚀 Quick Start Guide

## Setup dalam 5 Menit

### 1. Install Docker (jika belum punya)

**Linux:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

**macOS:**
Download Docker Desktop dari: https://www.docker.com/products/docker-desktop

**Windows:**
Download Docker Desktop dari: https://www.docker.com/products/docker-desktop

### 2. Setup Project

```bash
# Copy all files ke folder project kamu
cd /path/to/your/project

# Copy environment variables
cp .env.example .env

# Edit .env dan isi OpenAI API key
nano .env
```

**IMPORTANT**: Minimal isi ini di `.env`:
```
OPENAI_API_KEY=sk-proj-YOUR-KEY-HERE
```

### 3. Start Services

```bash
docker-compose up -d
```

Tunggu beberapa detik sampai services ready.

### 4. Check Health

```bash
curl http://localhost:8000/health
```

Jika return JSON dengan `"status": "healthy"`, berarti **READY!** ✅

### 5. Test Conversation

```bash
./test.sh
```

Atau test manual:
```bash
curl -X POST "http://localhost:8000/test/message?customer_id=628115987778&message=Internet%20saya%20mati&customer_name=Vincent"
```

---

## Troubleshooting

### Error: "Port 8000 already in use"
```bash
# Change port di docker-compose.yml
# Edit line:
    - "8001:8000"  # Use 8001 instead of 8000
```

### Error: "Redis connection failed"
```bash
# Restart Docker
docker-compose down
docker-compose up -d

# Check logs
docker-compose logs redis
```

### Error: "OpenAI API error"
- Check API key di `.env`
- Check balance: https://platform.openai.com/usage
- Minimum balance: $5

---

## Next: Connect ke Qiscus

1. Deploy ke server (VPS/Cloud)
2. Setup domain/subdomain
3. Add webhook URL di Qiscus Dashboard:
   ```
   https://your-domain.com/webhook/qiscus
   ```
4. Test dengan kirim chat dari WhatsApp

---

## Monitoring

**Check logs:**
```bash
docker-compose logs -f api
```

**Stop services:**
```bash
docker-compose down
```

**Restart:**
```bash
docker-compose restart
```

---

**Done! System siap dipakai.** 🎉
