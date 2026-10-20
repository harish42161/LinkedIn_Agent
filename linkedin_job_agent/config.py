"""Configuration Loader and Environment Settings.

Loads config.yaml, merges environment variables from .env,
and exposes strongly-typed settings across the automation agent.
"""

import os
from pathlib import Path
from typing import Any, Dict, List
import yaml
from dotenv import load_dotenv

# Base Paths
AGENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = AGENT_DIR.parent
CONFIG_YAML_PATH = AGENT_DIR / "config.yaml"
ENV_PATH = AGENT_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()


class AgentConfig:
    def __init__(self, config_dict: Dict[str, Any]):
        self._raw = config_dict
        agent = config_dict.get("agent", {})
        self.name: str = agent.get("name", "LinkedIn Job Agent")
        self.version: str = agent.get("version", "1.0.0")
        self.search_frequency_hours: int = int(agent.get("search_frequency_hours", 1))
        self.search_interval_seconds: int = int(agent.get("search_interval_seconds", 3600))
        
        # Override application mode from env if provided
        env_mode = os.getenv("APPLICATION_MODE")
        self.application_mode: str = env_mode if env_mode else agent.get("application_mode", "auto_submit")
        
        # Match score thresholds (95% default as specified)
        env_min_score = os.getenv("MINIMUM_MATCH_SCORE")
        self.minimum_match_score: float = float(env_min_score) if env_min_score else float(agent.get("minimum_match_score", 95.0))
        self.high_priority_threshold: float = float(agent.get("high_priority_threshold", 95.0))
        self.good_match_threshold: float = float(agent.get("good_match_threshold", 85.0))
        self.rejection_threshold: float = float(agent.get("rejection_threshold", 70.0))
        
        # Rate limits
        self.max_applications_per_hour: int = int(agent.get("max_applications_per_hour", 5))
        self.max_applications_per_day: int = int(agent.get("max_applications_per_day", 25))
        self.emergency_stop: bool = bool(agent.get("emergency_stop", False))

        # Target Roles & Locations
        self.target_roles: List[str] = config_dict.get("target_roles", [
            "Data Engineer",
            "ETL Developer",
            "Data Analyst",
            "PySpark Developer",
            "Python Developer – Data Engineering",
            "BI Developer / BI Data Engineer"
        ])
        
        self.target_locations: List[str] = config_dict.get("target_locations", [
            "Navi Mumbai, Maharashtra, India",
            "Pune, Maharashtra, India",
            "Mumbai, Maharashtra, India"
        ])

        # Experience filters
        exp = config_dict.get("experience_filter", {})
        self.min_experience_years: float = float(exp.get("min_years", 1.0))
        self.max_experience_years: float = float(exp.get("max_years", 5.5))
        self.candidate_experience_years: float = float(exp.get("preferred_years", 3.2))

        # Weights
        self.matching_weights: Dict[str, float] = config_dict.get("matching_weights", {
            "technical_skills": 0.40,
            "experience_years": 0.20,
            "responsibilities": 0.15,
            "database_programming": 0.10,
            "location": 0.10,
            "industry_domain": 0.05
        })

        # Storage paths
        storage = config_dict.get("storage", {})
        self.database_path = self._resolve_path(storage.get("database_path", "linkedin_job_agent/data/jobs.db"))
        self.candidate_profile_path = self._resolve_path(storage.get("candidate_profile_path", "linkedin_job_agent/data/candidate_profile.json"))
        self.resume_path = self._resolve_path(storage.get("resume_path", "linkedin_job_agent/resumes/harish_ghadage_resume.txt"))
        self.session_storage_path = self._resolve_path(storage.get("session_storage_path", "linkedin_job_agent/data/session.enc"))

        # Auth
        auth = config_dict.get("auth", {})
        self.li_at: str = os.getenv("LINKEDIN_LI_AT", "")
        self.jsessionid: str = os.getenv("LINKEDIN_JSESSIONID", "")
        self.encryption_key: str = os.getenv("LINKEDIN_ENCRYPTION_KEY", "")
        self.interactive_login: bool = bool(auth.get("interactive_login", False))
        self.headless_browser: bool = bool(auth.get("headless_browser", True))

        # Notifications
        notif = config_dict.get("notifications", {})
        self.console_summary: bool = bool(notif.get("console_summary", True))
        self.system_desktop_notif: bool = bool(notif.get("system_desktop", True))
        self.webhook_enabled: bool = bool(notif.get("webhook_enabled", False))
        self.webhook_url: str = os.getenv("WEBHOOK_URL", notif.get("webhook_url", ""))

        # Private Dashboard Access Control
        self.dashboard_username: str = os.getenv("DASHBOARD_USERNAME", "harish")
        self.dashboard_password: str = os.getenv("DASHBOARD_PASSWORD", "Harish@2026")

    def _resolve_path(self, rel_or_abs: str) -> Path:
        p = Path(rel_or_abs)
        if p.is_absolute():
            return p
        # Check relative to ROOT_DIR or AGENT_DIR
        candidate = ROOT_DIR / rel_or_abs
        if candidate.parent.exists():
            return candidate
        return AGENT_DIR / rel_or_abs

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "application_mode": self.application_mode,
            "minimum_match_score": self.minimum_match_score,
            "search_frequency_hours": self.search_frequency_hours,
            "target_roles": self.target_roles,
            "target_locations": self.target_locations,
            "max_applications_per_hour": self.max_applications_per_hour,
            "max_applications_per_day": self.max_applications_per_day,
            "database_path": str(self.database_path),
            "candidate_profile_path": str(self.candidate_profile_path),
            "resume_path": str(self.resume_path),
        }


def load_config(config_path: Path = CONFIG_YAML_PATH) -> AgentConfig:
    """Load and parse YAML configuration."""
    if not config_path.exists():
        raw_dict = {}
    else:
        with open(config_path, "r", encoding="utf-8") as f:
            raw_dict = yaml.safe_load(f) or {}
    return AgentConfig(raw_dict)


# Global instance
config = load_config()
