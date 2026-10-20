#!/usr/bin/env bash
# ==============================================================================
# Installer Script for LinkedIn Job Agent macOS Launchd Daemon
# Registers the agent to run automatically every hour in the background.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.harish.linkedin_job_agent.plist"
SOURCE_PLIST="${SCRIPT_DIR}/${PLIST_NAME}"
TARGET_DIR="${HOME}/Library/LaunchAgents"
TARGET_PLIST="${TARGET_DIR}/${PLIST_NAME}"

echo "==================================================================="
echo "  Deploying LinkedIn Job Application Agent to macOS Launchd"
echo "==================================================================="

# 1. Ensure LaunchAgents directory exists
mkdir -p "${TARGET_DIR}"

# 2. Unload existing service if already active
if launchctl list | grep -q "com.harish.linkedin_job_agent"; then
    echo "⚠️  Existing daemon detected. Unloading previous instance..."
    launchctl unload "${TARGET_PLIST}" 2>/dev/null || true
fi

# 3. Copy plist into user's LaunchAgents
echo "📋 Installing plist to ${TARGET_PLIST}..."
cp "${SOURCE_PLIST}" "${TARGET_PLIST}"
chmod 644 "${TARGET_PLIST}"

# 4. Load the daemon
echo "🚀 Starting hourly background service..."
launchctl load -w "${TARGET_PLIST}"

# 5. Verify status
echo "🔍 Checking daemon status..."
if launchctl list | grep -q "com.harish.linkedin_job_agent"; then
    echo "✅ SUCCESS: LinkedIn Job Application Agent is now actively running in the background!"
    echo "   • Schedule: Every 1 hour automatically (even when terminal is closed)"
    echo "   • Logs: ${SCRIPT_DIR}/../logs/launchd_stdout.log"
else
    echo "⚠️  Daemon loaded, but verify with: launchctl list | grep linkedin"
fi
echo "==================================================================="
