#!/usr/bin/env bash
# ==============================================================================
# Uninstaller Script for LinkedIn Job Agent macOS Launchd Daemon
# ==============================================================================

set -e

TARGET_PLIST="${HOME}/Library/LaunchAgents/com.harish.linkedin_job_agent.plist"

echo "Stopping and uninstalling LinkedIn Job Application Agent daemon..."

if [ -f "${TARGET_PLIST}" ]; then
    launchctl unload "${TARGET_PLIST}" 2>/dev/null || true
    rm -f "${TARGET_PLIST}"
    echo "✅ Successfully stopped and uninstalled background daemon."
else
    echo "ℹ️ Daemon was not installed."
fi
