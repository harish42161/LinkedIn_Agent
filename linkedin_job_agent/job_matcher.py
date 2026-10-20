"""Resume-Based Job Matcher.

Evaluates LinkedIn job descriptions against the candidate's verified resume
across technical skills, experience years, ETL responsibilities, databases,
locations, and domain relevance to calculate a score from 0 to 100.
"""

import re
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from linkedin_job_agent.config import config
from linkedin_job_agent.resume_parser import CandidateProfile, resume_parser

logger = logging.getLogger("linkedin_agent.matcher")


@dataclass
class MatchResult:
    score: float
    category: str
    is_eligible: bool
    pros: List[str]
    gaps: List[str]
    explanation: str
    breakdown: Dict[str, float]


class JobMatcher:
    """Calculates multi-dimensional alignment scores between jobs and candidate profile."""

    def __init__(self, profile: Optional[CandidateProfile] = None):
        self.profile = profile if profile else resume_parser.load_candidate_profile()

        # Skill lookup dictionary with weights
        self.core_skills = {
            "python": 1.2,
            "sql": 1.2,
            "pyspark": 1.5,
            "spark": 1.3,
            "etl": 1.4,
            "pentaho": 1.4,
            "spoon": 1.2,
            "hadoop": 1.1,
            "hive": 1.1,
            "hdfs": 1.0,
            "sqoop": 1.0,
            "mysql": 1.0,
            "pl/sql": 1.1,
            "plsql": 1.1,
            "pandas": 1.0,
            "numpy": 1.0,
            "power bi": 1.1,
            "dax": 1.0,
            "excel": 0.8,
            "rest api": 0.9,
            "postman": 0.8,
            "sftp": 0.9,
            "informatica": 1.0,
            "data warehouse": 1.1,
            "data pipeline": 1.2,
            "data transformation": 1.1,
            "data validation": 1.1,
            "git": 0.8
        }

        # Seniority penalty keywords
        self.disqualifiers = [
            "unpaid", "internship", "trainee", "phd required",
            "10+ years", "12+ years", "15+ years", "director of", "vice president"
        ]

    def evaluate_job(self, job_data: Dict[str, Any]) -> MatchResult:
        """Evaluates a single job opportunity against the candidate's profile."""
        title = job_data.get("title", "").lower()
        desc = job_data.get("job_description", "").lower()
        combined_text = f"{title} {desc}"
        location_raw = job_data.get("location", "").lower()

        pros: List[str] = []
        gaps: List[str] = []

        # 0. Fast Disqualification Check
        for disq in self.disqualifiers:
            if disq in combined_text and "years" in disq:
                # Check if it's a strict 10+ year requirement
                req_years = self._extract_required_years(combined_text)
                if req_years and req_years > 7.0:
                    gaps.append(f"Requires {req_years}+ years experience (Candidate has {self.profile.total_years_experience} years)")
                    return MatchResult(
                        score=35.0,
                        category="Unsuitable (Experience Mismatch)",
                        is_eligible=False,
                        pros=pros,
                        gaps=gaps,
                        explanation=f"Role requires {req_years}+ years of experience, exceeding candidate's 3+ years experience level.",
                        breakdown={"technical": 50, "experience": 10, "responsibilities": 40, "database": 40, "location": 50, "domain": 30}
                    )
            elif disq in title:
                gaps.append(f"Disqualified due to position level: '{disq}'")
                return MatchResult(
                    score=20.0,
                    category="Disqualified",
                    is_eligible=False,
                    pros=pros,
                    gaps=gaps,
                    explanation=f"Position marked as '{disq}', not matching professional Data Engineer goals.",
                    breakdown={"technical": 0, "experience": 0, "responsibilities": 0, "database": 0, "location": 0, "domain": 0}
                )

        # 1. Technical Skills Score (Weight 40%)
        tech_score, matched_skills, missing_skills = self._score_technical_skills(combined_text)
        if matched_skills:
            pros.append(f"Matching core skills: {', '.join(matched_skills[:6])}")
        if missing_skills:
            gaps.append(f"Uncommon / missing technologies: {', '.join(missing_skills[:4])}")

        # 2. Experience Years Score (Weight 20%)
        exp_score, req_years = self._score_experience_years(combined_text)
        if req_years:
            if exp_score >= 90:
                pros.append(f"Experience aligned: requires ~{req_years} years (Candidate: {self.profile.total_years_experience} yrs)")
            else:
                gaps.append(f"Experience gap: JD specifies {req_years} years vs candidate {self.profile.total_years_experience} yrs")
        else:
            pros.append("Experience requirement flexible or matching 3+ years")

        # 3. Responsibilities & Role Relevance (Weight 15%)
        resp_score = self._score_responsibilities(title, desc)
        if resp_score >= 85:
            pros.append("Job description centers on data pipelines, ETL architecture, and transformations")

        # 4. Database & Programming (Weight 10%)
        db_score = self._score_database_programming(combined_text)
        if db_score >= 85:
            pros.append("Strong match with SQL/PLSQL, database modeling, and Python scripting")

        # 5. Location Match (Weight 10%)
        loc_score, loc_note = self._score_location(location_raw)
        if loc_score >= 90:
            pros.append(loc_note)
        else:
            gaps.append(loc_note)

        # 6. Industry & Domain Bonus (Weight 5%)
        domain_score = self._score_domain(combined_text)
        if domain_score >= 80:
            pros.append("Directly in BFSI, Banking, or NBFC financial domain")

        # Calculate final weighted total
        weights = config.matching_weights
        final_score = (
            tech_score * weights.get("technical_skills", 0.40) +
            exp_score * weights.get("experience_years", 0.20) +
            resp_score * weights.get("responsibilities", 0.15) +
            db_score * weights.get("database_programming", 0.10) +
            loc_score * weights.get("location", 0.10) +
            domain_score * weights.get("industry_domain", 0.05)
        )
        final_score = round(min(100.0, max(0.0, final_score)), 1)

        # Categorization based on thresholds
        if final_score >= config.high_priority_threshold:
            category = "High-priority match (Eligible for Auto-Apply)"
            is_eligible = True
        elif final_score >= config.good_match_threshold:
            category = "Good match"
            is_eligible = (config.application_mode == "auto_submit" and final_score >= config.minimum_match_score)
        elif final_score >= config.rejection_threshold:
            category = "Moderate match (Review needed)"
            is_eligible = False
        else:
            category = "Below threshold"
            is_eligible = False

        # Explanation summary
        if final_score >= 90:
            summary = (f"Excellent {final_score}% match! Job strongly aligns with candidate's "
                       f"3+ years experience in Python, PySpark, ETL pipelines, and SQL.")
        elif final_score >= 80:
            summary = (f"Solid {final_score}% match. Good alignment on core data engineering competencies, "
                       f"with minor variance in specialized requirements.")
        else:
            summary = (f"{final_score}% score. The job requirements diverge from candidate's "
                       f"experience level or core technical focus.")

        return MatchResult(
            score=final_score,
            category=category,
            is_eligible=is_eligible,
            pros=pros,
            gaps=gaps,
            explanation=summary,
            breakdown={
                "technical_skills": round(tech_score, 1),
                "experience_years": round(exp_score, 1),
                "responsibilities": round(resp_score, 1),
                "database_programming": round(db_score, 1),
                "location": round(loc_score, 1),
                "industry_domain": round(domain_score, 1)
            }
        )

    def _score_technical_skills(self, text: str) -> Tuple[float, List[str], List[str]]:
        matched: List[str] = []
        found_weights: float = 0.0
        total_possible: float = 0.0

        for skill, weight in self.core_skills.items():
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text):
                matched.append(skill.title())
                found_weights += weight
            total_possible += weight

        # Relative match ratio based on skills demanded in the JD
        if matched:
            ratio = min(1.0, (found_weights / 9.0))  # 9.0 represents high density of candidate skills
            score = 65.0 + (ratio * 35.0)
        else:
            score = 25.0

        missing = []
        # Check for typical other tools
        for tech in ["aws", "azure", "gcp", "snowflake", "kafka", "dbt"]:
            if tech in text and not self.profile.has_skill(tech):
                missing.append(tech.upper())

        return score, matched, missing

    def _extract_required_years(self, text: str) -> Optional[float]:
        # Matches patterns like '3-5 years', '3+ years', 'minimum 3 years', 'at least 4 years'
        patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*years?',
            r'(\d+(?:\.\d+)?)\+?\s*years?(?:\s*of)?\s*experience',
            r'(?:minimum|at least)\s*(\d+(?:\.\d+)?)\s*years?'
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                groups = m.groups()
                if len(groups) == 2 and groups[1]:
                    return float(groups[0])
                return float(groups[0])
        return None

    def _score_experience_years(self, text: str) -> Tuple[float, Optional[float]]:
        req = self._extract_required_years(text)
        cand = self.profile.total_years_experience  # 3.2
        if req is None:
            return 92.0, None  # Default good score if unmentioned

        diff = cand - req
        if -0.5 <= diff <= 2.5:
            # Ideal sweet spot (e.g. requires 2-4 years)
            return 100.0, req
        elif diff > 2.5:
            # Overqualified slightly
            return 85.0, req
        elif -2.0 <= diff < -0.5:
            # Slightly higher than candidate
            return 75.0, req
        else:
            # Requires 6+ or 7+ years
            return max(20.0, 70.0 - (abs(diff) * 15.0)), req

    def _score_responsibilities(self, title: str, desc: str) -> float:
        score = 60.0
        # Title alignment check
        title_lower = title.lower()
        if any(role.lower() in title_lower for role in config.target_roles):
            score += 25.0

        keywords = ["pipeline", "etl", "extract", "transform", "load", "data lake", "warehouse", "analytics", "validation"]
        matched_kw = sum(1 for kw in keywords if kw in desc)
        score += min(15.0, matched_kw * 2.0)
        return min(100.0, score)

    def _score_database_programming(self, text: str) -> float:
        score = 50.0
        if "sql" in text:
            score += 20.0
        if "mysql" in text or "pl/sql" in text or "oracle" in text:
            score += 15.0
        if "python" in text:
            score += 15.0
        return min(100.0, score)

    def _score_location(self, loc_text: str) -> Tuple[float, str]:
        loc_text = loc_text.lower()
        if "navi mumbai" in loc_text:
            return 100.0, "Prime Target Location: Navi Mumbai"
        if "pune" in loc_text:
            return 98.0, "Prime Target Location: Pune"
        if "mumbai" in loc_text or "thane" in loc_text:
            return 95.0, "Target Location: Mumbai / MMR"
        if "remote" in loc_text or "hybrid" in loc_text:
            return 90.0, "Flexible Work: Remote / Hybrid"
        if "india" in loc_text:
            return 70.0, "India location outside primary Mumbai/Pune preference"
        return 50.0, f"Location '{loc_text}' is outside priority cities"

    def _score_domain(self, text: str) -> float:
        bfsi_terms = ["banking", "nbfc", "bfsi", "finance", "financial", "fintech", "lending", "credit", "wealth"]
        matched = sum(1 for term in bfsi_terms if term in text)
        if matched >= 2:
            return 100.0
        elif matched == 1:
            return 85.0
        return 65.0


job_matcher = JobMatcher()
