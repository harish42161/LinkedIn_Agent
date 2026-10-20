# 🚀 Production Deployment Guide: LinkedIn Job Application Agent

This guide documents the deployment options provided in the **Full Production Bundle**.

---

## 🖥️ Option 1: Native macOS Launchd Daemon (Currently Active)

The agent is installed as a native background service using macOS `launchd`. It runs **automatically every hour** without requiring an open terminal or IDE session.

### Control Commands:
```bash
# Check service and process status
./linkedin_job_agent/deploy/status.sh

# View live execution logs
tail -f linkedin_job_agent/logs/launchd_stdout.log

# Stop / Uninstall the daemon
./linkedin_job_agent/deploy/uninstall_daemon.sh

# Re-install / Restart the daemon
./linkedin_job_agent/deploy/install_daemon.sh
```

- **Plist Location:** `~/Library/LaunchAgents/com.harish.linkedin_job_agent.plist`
- **Schedule Interval:** Every 3600 seconds (1 hour)
- **Start at Login:** Enabled (`RunAtLoad: true`)

---

## 🐳 Option 2: Docker & Docker Compose (Containerized)

To run the agent inside isolated Docker containers (ideal for Linux servers or cloud VPS):

### Start Services:
```bash
cd linkedin_job_agent/deploy
docker compose up -d --build
```

### Services Managed:
1. `linkedin_job_scheduler`: Executes the background hourly job search & application daemon.
2. `linkedin_job_dashboard`: Serves the Streamlit web dashboard at `http://localhost:8501`.

### Useful Docker Commands:
```bash
# View live container logs
docker compose logs -f

# Check container health
docker compose ps

# Stop containers
docker compose down
```

---

## ☁️ Option 3: Cloud Deployment (AWS EC2 / DigitalOcean / Railway)

### On Ubuntu / Debian Server:
```bash
# 1. Clone repository to server
git clone <your_repo_url> /opt/linkedin-job-agent
cd /opt/linkedin-job-agent

# 2. Configure environment
cp linkedin_job_agent/.env.example linkedin_job_agent/.env
nano linkedin_job_agent/.env

# 3. Launch with Docker Compose
cd linkedin_job_agent/deploy
docker compose up -d --build
```

### Systemd Service (Alternative for Linux VPS):
If you prefer running without Docker on Linux, a systemd unit file can be created:
```ini
[Unit]
Description=LinkedIn Job Application Agent
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/linkedin-job-agent
ExecStart=/opt/linkedin-job-agent/venv/bin/python linkedin_job_agent/main.py schedule
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```
