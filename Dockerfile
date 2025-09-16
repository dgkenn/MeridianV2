FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Initialize database
RUN python init_simple.py

# Expose port
EXPOSE 8084

# Run the application
CMD ["gunicorn", "app_simple:app", "--bind", "0.0.0.0:8084", "--workers", "2", "--timeout", "300"]