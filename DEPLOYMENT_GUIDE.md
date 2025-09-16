# Codex v2 Deployment Guide

Complete step-by-step guide for deploying Codex v2 from scratch.

## Prerequisites

- Python 3.9 or higher
- Git (optional, for version control)
- 4GB+ RAM
- 10GB+ disk space
- Internet connection (for PubMed API access)

## Quick Start (5 minutes)

```bash
# 1. Navigate to codex-v2 directory
cd "C:\Users\Dean\Documents\Research Stuff\Anesthesia research\codex-v2"

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
# source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Download spaCy model
python -m spacy download en_core_web_sm

# 6. Initialize system
python scripts/setup_codex.py

# 7. Start application
python src/frontend/app.py
```

Open browser to `http://localhost:8080`

## Detailed Setup

### 1. Environment Setup

#### Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

#### Dependencies
```bash
pip install -r requirements.txt
```

#### Environment Variables (Optional)
Create `.env` file:
```bash
# PubMed API
NCBI_API_KEY=your_api_key_here
CONTACT_EMAIL=your_email@domain.com

# Database
DATABASE_PATH=database/codex.duckdb

# Flask
SECRET_KEY=your_secret_key_here
FLASK_ENV=development
```

### 2. Database Initialization

#### Automatic Setup (Recommended)
```bash
python scripts/setup_codex.py
```

#### Manual Setup
```python
from src.core.database import init_database
from src.ontology.core_ontology import AnesthesiaOntology

# Initialize database
db = init_database()

# Load ontology
ontology = AnesthesiaOntology()
records = ontology.to_database_records()

for record in records:
    db.conn.execute("""
        INSERT OR REPLACE INTO ontology
        (token, type, plain_label, synonyms, category, severity_weight,
         notes, icd10_codes, mesh_codes, parent_token, children_tokens)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, list(record.values()))

print("Setup complete!")
```

### 3. Verify Installation

#### Health Check
```bash
curl http://localhost:8080/api/health
```

Expected response:
```json
{
    "status": "healthy",
    "version": "2.0.0",
    "evidence_version": "v1.0.0",
    "database": {
        "status": "connected",
        "papers": 2,
        "ontology_terms": 100+
    }
}
```

#### Test HPI Parsing
```bash
curl -X POST http://localhost:8080/api/hpi/parse \
  -H "Content-Type: application/json" \
  -d '{"hpi_text": "5-year-old male with asthma for tonsillectomy"}'
```

## Production Deployment

### 1. Environment Configuration

Create production `.env`:
```bash
# Production settings
FLASK_ENV=production
SECRET_KEY=secure_random_key_change_this
DATABASE_PATH=/var/lib/codex/codex.duckdb
LOG_LEVEL=INFO
LOG_FILE=/var/log/codex/app.log

# PubMed API
NCBI_API_KEY=your_production_api_key
CONTACT_EMAIL=admin@yourorganization.com

# Security
ALLOWED_HOSTS=yourdomain.com,localhost
```

### 2. Docker Deployment

#### Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy application
COPY src/ src/
COPY scripts/ scripts/
COPY database/ database/

# Create non-root user
RUN useradd -m -u 1000 codex
RUN chown -R codex:codex /app
USER codex

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Start application
CMD ["python", "src/frontend/app.py"]
```

#### Build and run
```bash
docker build -t codex-v2 .
docker run -p 8080:8080 -v $(pwd)/database:/app/database codex-v2
```

#### Docker Compose
```yaml
version: '3.8'
services:
  codex:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./database:/app/database
      - ./logs:/app/logs
    environment:
      - FLASK_ENV=production
      - DATABASE_PATH=/app/database/codex.duckdb
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - codex
    restart: unless-stopped
```

### 3. Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/m;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 4. Systemd Service

Create `/etc/systemd/system/codex.service`:
```ini
[Unit]
Description=Codex v2 Anesthesia Risk Assessment
After=network.target

[Service]
Type=simple
User=codex
Group=codex
WorkingDirectory=/opt/codex
Environment=PATH=/opt/codex/venv/bin
ExecStart=/opt/codex/venv/bin/python src/frontend/app.py
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=codex

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/codex/database /opt/codex/logs

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable codex
sudo systemctl start codex
sudo systemctl status codex
```

## Monitoring and Maintenance

### 1. Logging

Configure logging in production:
```python
import logging
from logging.handlers import RotatingFileHandler

if not app.debug:
    file_handler = RotatingFileHandler(
        'logs/codex.log', maxBytes=10240000, backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
```

### 2. Monitoring Script

```python
#!/usr/bin/env python3
"""
Codex monitoring script - checks system health and alerts on issues.
"""

import requests
import smtplib
import time
from email.mime.text import MIMEText

def check_health():
    try:
        response = requests.get('http://localhost:8080/api/health', timeout=10)
        data = response.json()

        if data['status'] != 'healthy':
            return False, f"Unhealthy status: {data.get('error', 'Unknown')}"

        return True, "System healthy"

    except Exception as e:
        return False, f"Health check failed: {e}"

def send_alert(message):
    # Configure email alerting
    pass

if __name__ == "__main__":
    healthy, message = check_health()
    if not healthy:
        print(f"ALERT: {message}")
        send_alert(message)
    else:
        print(f"OK: {message}")
```

### 3. Database Maintenance

#### Backup Script
```bash
#!/bin/bash
# backup_codex.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/codex"
DB_PATH="/var/lib/codex/codex.duckdb"

mkdir -p $BACKUP_DIR

# Create backup
cp $DB_PATH $BACKUP_DIR/codex_$DATE.duckdb

# Compress
gzip $BACKUP_DIR/codex_$DATE.duckdb

# Clean old backups (keep 30 days)
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete

echo "Backup completed: codex_$DATE.duckdb.gz"
```

#### Evidence Updates
```bash
#!/bin/bash
# update_evidence.sh

cd /opt/codex
source venv/bin/activate

python scripts/update_evidence.py --outcomes ALL --max-papers 1000
python scripts/validate_pools.py

# Restart service if successful
if [ $? -eq 0 ]; then
    sudo systemctl restart codex
    echo "Evidence update completed and service restarted"
else
    echo "Evidence update failed"
    exit 1
fi
```

## Security Considerations

### 1. Access Control
- Use HTTPS in production
- Implement authentication if required
- Set up rate limiting
- Regular security updates

### 2. Data Protection
- PHI detection and anonymization
- Audit logging for all actions
- Regular backups
- Access monitoring

### 3. Network Security
- Firewall configuration
- VPN access for internal use
- Regular vulnerability scanning

## Troubleshooting

### Common Issues

#### Database Locked
```bash
# Check processes using database
lsof database/codex.duckdb

# Force unlock (use with caution)
python -c "import duckdb; duckdb.connect('database/codex.duckdb').close()"
```

#### Memory Issues
```bash
# Check memory usage
free -h

# Adjust Python memory limits
export PYTHONHASHSEED=0
ulimit -v 4000000  # 4GB virtual memory limit
```

#### Port Conflicts
```bash
# Check port usage
netstat -tulpn | grep 8080

# Change port in app.py or environment
export PORT=8081
```

### Log Analysis

#### Common log patterns
```bash
# Error analysis
grep -i error logs/codex.log | tail -20

# Performance monitoring
grep "response_time" logs/codex.log | awk '{print $3}' | sort -n

# API usage
grep "POST /api" logs/codex.log | wc -l
```

## Performance Optimization

### 1. Database Optimization
- Regular VACUUM operations
- Index optimization
- Query performance monitoring

### 2. Application Optimization
- Enable Flask caching
- Optimize NLP processing
- Concurrent request handling

### 3. Infrastructure Optimization
- SSD storage for database
- Adequate RAM (8GB+ recommended)
- CDN for static assets

## Scaling Considerations

### Horizontal Scaling
- Load balancer configuration
- Shared database access
- Session management

### High Availability
- Database replication
- Health checks and failover
- Backup and disaster recovery

---

This deployment guide provides comprehensive instructions for setting up Codex v2 in any environment. For additional support, refer to the main README.md and API documentation.