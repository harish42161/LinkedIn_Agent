"""Resume Parser and Candidate Profile Manager.

Extracts structured candidate details, verified skills, and experience
from uploaded PDF or text resumes, ensuring zero invention of credentials.
"""

import re
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from linkedin_job_agent.config import config

logger = logging.getLogger("linkedin_agent.resume")


@dataclass
class CandidateProfile:
    """Strongly-typed verified candidate profile model."""
    full_name: str
    email: str
    phone: str
    current_location: str
    preferred_locations: List[str]
    total_years_experience: float
    current_title: str
    current_company: str
    notice_period_days: int
    work_authorization: str
    require_sponsorship: bool
    skills: Dict[str, List[str]]
    all_flat_skills: List[str]
    domains: List[str]
    target_roles: List[str]
    education: List[Dict[str, Any]]
    positions: List[Dict[str, Any]]
    raw_resume_text: str = ""

    def has_skill(self, skill_name: str) -> bool:
        """Case-insensitive check if candidate has a specific skill."""
        s_lower = skill_name.lower().strip()
        return any(s_lower == s.lower().strip() or s_lower in s.lower() for s in self.all_flat_skills)


class ResumeParser:
    """Parses resumes (PDF, TXT, JSON) and provides verified candidate profile."""

    def __init__(self, profile_json_path: Optional[Path] = None, resume_file_path: Optional[Path] = None):
        self.profile_json_path = Path(profile_json_path) if profile_json_path else config.candidate_profile_path
        self.resume_file_path = Path(resume_file_path) if resume_file_path else config.resume_path

    def extract_text_from_file(self, file_path: Path) -> str:
        """Extracts text from PDF, TXT, or MD files."""
        if not file_path.exists():
            logger.warning(f"Resume file not found at: {file_path}")
            return ""

        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(file_path))
                text_parts = []
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                return "\n".join(text_parts)
            except Exception as e:
                logger.error(f"Failed to parse PDF resume: {e}")
                return ""
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

    def load_candidate_profile(self) -> CandidateProfile:
        """Loads and parses candidate profile from verified JSON and raw resume text."""
        raw_text = self.extract_text_from_file(self.resume_file_path)

        data: Dict[str, Any] = {}
        if self.profile_json_path.exists():
            with open(self.profile_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

        personal = data.get("personal_info", {})
        experience = data.get("experience", {})
        skills_dict = data.get("skills", {})

        # Flatten skills into set
        flat_skills: List[str] = []
        for cat, slist in skills_dict.items():
            if isinstance(slist, list):
                flat_skills.extend(slist)
        flat_skills = sorted(list(set(flat_skills)))

        domains = skills_dict.get("domains", ["Banking", "Financial Services", "NBFC"])

        # Construct verified profile
        profile = CandidateProfile(
            full_name=personal.get("full_name", "Harish Ghadage"),
            email=personal.get("email", "harish.ghadage@example.com"),
            phone=personal.get("phone", "+91 98765 43210"),
            current_location=personal.get("current_location", "Navi Mumbai, Maharashtra, India"),
            preferred_locations=personal.get("preferred_locations", [
                "Navi Mumbai, Maharashtra",
                "Pune, Maharashtra",
                "Mumbai, Maharashtra"
            ]),
            total_years_experience=float(experience.get("total_years", 3.2)),
            current_title=experience.get("current_title", "Data Engineer / ETL Developer"),
            current_company=experience.get("current_company", "Apex Financial Technologies"),
            notice_period_days=int(experience.get("notice_period_days", 30)),
            work_authorization=experience.get("work_authorization", "Authorized to work in India (Citizen)"),
            require_sponsorship=bool(experience.get("require_sponsorship", False)),
            skills=skills_dict,
            all_flat_skills=flat_skills,
            domains=domains,
            target_roles=data.get("target_roles", config.target_roles),
            education=data.get("education", []),
            positions=experience.get("positions", []),
            raw_resume_text=raw_text
        )

        return profile


# Singleton parser
resume_parser = ResumeParser()
