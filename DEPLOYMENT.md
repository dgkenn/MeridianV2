# 🚀 CODEX v2 Deployment Guide

## Quick Options (Recommended)

### 1. **Railway** (Free tier, easiest)
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```
- ✅ Free tier available
- ✅ Automatic HTTPS
- ✅ Custom domains
- ✅ Database persistence

### 2. **Render** (Free tier)
1. Go to [render.com](https://render.com)
2. Connect your GitHub repo
3. Use `render.yaml` (already created)
4. Auto-deploys on git push

### 3. **DigitalOcean App Platform** (Paid)
```bash
doctl apps create --spec render.yaml
```
- Professional hosting
- Built-in monitoring
- Scalable

## Manual VPS Deployment

### On Ubuntu/Debian server:
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python
sudo apt install python3 python3-pip python3-venv nginx -y

# Clone your repo
git clone <your-repo-url>
cd codex-v2

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python init_simple.py

# Run with Gunicorn
gunicorn app_simple:app --bind 0.0.0.0:8084 --daemon
```

### Configure Nginx reverse proxy:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8084;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Environment Variables

Set these for production:
```bash
export FLASK_ENV=production
export SECRET_KEY=your-secret-key-here
```

## Files Added for Deployment

- ✅ `Procfile` - Heroku/Railway deployment
- ✅ `render.yaml` - Render deployment
- ✅ `Dockerfile` - Docker deployment
- ✅ `runtime.txt` - Python version
- ✅ `requirements.txt` - Updated with gunicorn

## Database Considerations

Your DuckDB database will work on all platforms but:
- For production, consider PostgreSQL for better concurrency
- Current setup saves to local file system
- Railway/Render provide persistent storage

## Custom Domain Setup

Most platforms offer:
1. Free subdomain (yourapp.railway.app)
2. Custom domain support ($)
3. Automatic SSL certificates

## Monitoring & Logs

Access logs via platform dashboards or:
```bash
# View application logs
heroku logs --tail           # Heroku
railway logs --follow        # Railway
```

## Security Notes

- Bug reports save to local file in current implementation
- For production email, configure SMTP properly
- Consider adding authentication for sensitive medical data
- Use environment variables for sensitive config

## Cost Estimates

| Platform | Free Tier | Paid Plans |
|----------|-----------|------------|
| Railway | 500 hours/month | $5/month |
| Render | 750 hours/month | $7/month |
| Heroku | None | $7/month |
| DigitalOcean | None | $12/month |

## Quick Start (Railway - Recommended)

1. Push your code to GitHub
2. Go to railway.app
3. "Deploy from GitHub repo"
4. Select your repo
5. Railway auto-detects Python and uses Procfile
6. Get live URL in ~2 minutes!

Your CODEX v2 app is now ready for the web! 🎉