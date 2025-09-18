FROM python:3.11-slim

WORKDIR /app

# Copy minimal requirements and install Python dependencies
COPY requirements-minimal.txt .
RUN pip install --no-cache-dir -r requirements-minimal.txt

# Copy application code
COPY . .

# Initialize comprehensive production database for deployment
RUN python scripts/create_comprehensive_production_db.py

# Expose port
EXPOSE 8084

# Run the application
CMD ["gunicorn", "app_simple:app", "--bind", "0.0.0.0:8084", "--workers", "1", "--timeout", "300", "--max-requests", "1000", "--max-requests-jitter", "100"]