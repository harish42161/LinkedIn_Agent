# ==============================================================================
# Production Dockerfile for LinkedIn Job Application Automation Agent
# ==============================================================================
FROM python:3.11-slim

# Prevent Python from writing .pyc and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . /app/linkedin_job_agent

# Create directory structure for persistent storage and logs
RUN mkdir -p /app/linkedin_job_agent/data /app/linkedin_job_agent/logs /app/linkedin_job_agent/resumes

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose Streamlit dashboard port
EXPOSE 8501

# Default command: launch dashboard (can be overridden to schedule)
CMD ["python", "linkedin_job_agent/main.py", "dashboard", "--port", "8501"]
