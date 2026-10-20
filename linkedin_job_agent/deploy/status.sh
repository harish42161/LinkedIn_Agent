#!/usr/bin/env bash
# ==============================================================================
# Status Checker for Deployed LinkedIn Job Agent Services
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/../.."

echo "==================================================================="
echo "       LinkedIn Job Application Agent - Deployment Status          "
echo "==================================================================="

# 1. Check macOS Launchd Daemon
echo -n "1. macOS Launchd Daemon: "
if launchctl list 2>/dev/null | grep -q "com.harish.linkedin_job_agent"; then
    PID=$(launchctl list | grep "com.harish.linkedin_job_agent" | awk '{print $1}')
    if [ "$PID" != "-" ] && [ -n "$PID" ]; then
        echo "🟢 ACTIVE (PID: $PID)"
    else
        echo "🟡 REGISTERED (Scheduled to run hourly)"
    fi
else
    echo "⚪ Not installed via Launchd"
fi

# 2. Check Streamlit Dashboard on port 8501
echo -n "2. Streamlit Dashboard (Port 8501): "
if lsof -i :8501 >/dev/null 2>&1; then
    DASH_PID=$(lsof -ti :8501 | head -n 1)
    echo "🟢 RUNNING (PID: $DASH_PID) -> http://localhost:8501"
else
    echo "⚪ Not running"
fi

# 3. Check Database Metrics
echo "-------------------------------------------------------------------"
if [ -f "${PROJECT_ROOT}/venv/bin/python" ]; then
    "${PROJECT_ROOT}/venv/bin/python" "${PROJECT_ROOT}/linkedin_job_agent/main.py" status
else
    python3 "${PROJECT_ROOT}/linkedin_job_agent/main.py" status
fi
echo "==================================================================="
