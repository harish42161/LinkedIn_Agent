"""Main CLI Entrypoint and Orchestrator for LinkedIn Job Application Agent.

Usage:
    python linkedin_job_agent/main.py run-once          # Run a single discovery & application cycle
    python linkedin_job_agent/main.py schedule          # Run continuous hourly daemon
    python linkedin_job_agent/main.py dashboard         # Launch Streamlit monitoring UI
    python linkedin_job_agent/main.py auth              # Verify or update session authentication
    python linkedin_job_agent/main.py status            # View current database and queue metrics
    python linkedin_job_agent/main.py parse-resume      # Test resume parsing and profile extraction
"""

import sys
import argparse
import subprocess
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from linkedin_job_agent.config import config
from linkedin_job_agent.database_manager import db_manager
from linkedin_job_agent.resume_parser import resume_parser
from linkedin_job_agent.scheduler import scheduler
from linkedin_job_agent.linkedin_auth import auth_manager
from linkedin_job_agent.notification_service import notification_service


def cmd_run_once(args):
    """Executes a single end-to-end hourly discovery cycle."""
    print("🚀 Triggering immediate job discovery and resume matching cycle...")
    stats = scheduler.execute_single_cycle()
    print("\n✅ Cycle finished.")


def cmd_schedule(args):
    """Starts the continuous hourly background daemon."""
    print(f"⏰ Starting Hourly LinkedIn Job Application Agent (Interval: {config.search_frequency_hours} hr)...")
    print("Press CTRL+C at any time to gracefully pause or terminate.\n")
    scheduler.start_hourly_loop()


def cmd_dashboard(args):
    """Launches the Streamlit monitoring interface."""
    dashboard_path = Path(__file__).resolve().parent / "dashboard.py"
    port = args.port if hasattr(args, "port") and args.port else 8501
    print(f"🌐 Launching Streamlit Dashboard on http://localhost:{port}...")
    cmd = [sys.executable, "-m", "streamlit", "run", str(dashboard_path), "--server.port", str(port)]
    subprocess.run(cmd)


def cmd_auth(args):
    """Checks session validity or updates session tokens."""
    if args.cookie:
        auth_manager.save_session(args.cookie, args.jsession)
        print("✅ LinkedIn session tokens updated and encrypted successfully.")

    valid, msg = auth_manager.verify_session()
    print(f"\nLinkedIn Session Check:")
    print(f"  Status: {'🟢 ACTIVE' if valid else '🔴 INACTIVE / UNCONFIGURED'}")
    print(f"  Details: {msg}\n")
    if not valid:
        print(auth_manager.prompt_interactive_login_instructions())


def cmd_status(args):
    """Prints current database and queue summary."""
    metrics = db_manager.get_dashboard_metrics()
    print("\n=======================================================")
    print("      LinkedIn Job Application Agent - Current Status  ")
    print("=======================================================")
    print(f"Candidate              : Harish Ghadage (3+ Yrs Data Engineering)")
    print(f"Target Cities          : Navi Mumbai, Pune, Mumbai")
    print(f"Minimum Match Score    : {config.minimum_match_score}%")
    print(f"Application Mode       : {config.application_mode.upper()}")
    print("-------------------------------------------------------")
    print(f"Total Discovered Jobs  : {metrics['total_discovered']}")
    print(f"High-Priority (≥95%)   : {metrics['high_priority_matches']}")
    print(f"Applications Submitted : {metrics['applications_submitted']}")
    print(f"Awaiting Review        : {metrics['awaiting_approval']}")
    print(f"Duplicates Skipped     : {metrics['duplicates_skipped']}")
    print(f"Failed Applications    : {metrics['failed_applications']}")
    print("=======================================================\n")


def cmd_parse_resume(args):
    """Parses resume file and displays extracted verified profile facts."""
    resume_path = Path(args.path) if args.path else config.resume_path
    print(f"📄 Parsing Resume from: {resume_path}")
    profile = resume_parser.load_candidate_profile()

    print("\n--- Verified Candidate Profile ---")
    print(f"Name                : {profile.full_name}")
    print(f"Title               : {profile.current_title}")
    print(f"Total Experience    : {profile.total_years_experience} Years")
    print(f"Current Company     : {profile.current_company}")
    print(f"Current Location    : {profile.current_location}")
    print(f"Notice Period       : {profile.notice_period_days} Days")
    print(f"Work Authorization  : {profile.work_authorization}")
    print(f"Verified Skills ({len(profile.all_flat_skills)}):")
    print(f"  {', '.join(profile.all_flat_skills[:15])}...")
    print(f"\nTarget Priority Roles:")
    for role in profile.target_roles:
        print(f"  - {role}")
    print("----------------------------------\n")


def main():
    parser = argparse.ArgumentParser(
        description="AI-Powered LinkedIn Job Application Automation Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run-once
    subparsers.add_parser("run-once", help="Run a single discovery, evaluation, and application cycle")

    # schedule
    subparsers.add_parser("schedule", help="Start continuous hourly scheduling daemon")

    # dashboard
    p_dash = subparsers.add_parser("dashboard", help="Start the Streamlit web monitoring dashboard")
    p_dash.add_argument("--port", type=int, default=8501, help="Port for dashboard (default: 8501)")

    # auth
    p_auth = subparsers.add_parser("auth", help="Manage LinkedIn authentication tokens")
    p_auth.add_argument("--cookie", type=str, help="Update 'li_at' cookie value")
    p_auth.add_argument("--jsession", type=str, help="Optional 'JSESSIONID' value")

    # status
    subparsers.add_parser("status", help="Show current application metrics and queue summary")

    # parse-resume
    p_res = subparsers.add_parser("parse-resume", help="Test resume parsing and view extracted details")
    p_res.add_argument("--path", type=str, help="Path to resume file (PDF or TXT)")

    args = parser.parse_args()

    if args.command == "run-once":
        cmd_run_once(args)
    elif args.command == "schedule":
        cmd_schedule(args)
    elif args.command == "dashboard":
        cmd_dashboard(args)
    elif args.command == "auth":
        cmd_auth(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "parse-resume":
        cmd_parse_resume(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
