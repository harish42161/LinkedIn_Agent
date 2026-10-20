"""Comprehensive Test Suite for LinkedIn Job Application Automation Agent.

Covers resume parsing, job matching algorithms, duplicate prevention,
form filling logic, database operations, and application submission policies.
"""

import os
import sys
import tempfile
from pathlib import Path
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from linkedin_job_agent.config import load_config
from linkedin_job_agent.resume_parser import ResumeParser
from linkedin_job_agent.job_matcher import JobMatcher
from linkedin_job_agent.duplicate_checker import DuplicateChecker
from linkedin_job_agent.database_manager import DatabaseManager
from linkedin_job_agent.application_form_filler import ApplicationFormFiller
from linkedin_job_agent.application_submitter import ApplicationSubmitter
from linkedin_job_agent.notification_service import NotificationService


@pytest.fixture
def temp_db():
    """Provides a fresh isolated temporary SQLite database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = Path(tf.name)
    db = DatabaseManager(db_path=db_path)
    yield db
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def sample_profile():
    """Loads candidate profile."""
    parser = ResumeParser()
    return parser.load_candidate_profile()


def test_resume_parser_verified_facts(sample_profile):
    """Verifies that the resume parser preserves truth and does not invent data."""
    assert sample_profile.full_name == "Harish Ghadage"
    assert sample_profile.total_years_experience >= 3.0
    assert "Navi Mumbai" in sample_profile.current_location or "Pune" in sample_profile.preferred_locations
    assert sample_profile.has_skill("python")
    assert sample_profile.has_skill("pyspark")
    assert sample_profile.has_skill("sql")
    assert sample_profile.has_skill("pentaho")
    assert sample_profile.has_skill("power bi")
    # Non-existent skill should be false
    assert not sample_profile.has_skill("quantum_computing_non_existent")


def test_job_matcher_high_priority_fit(sample_profile):
    """Tests that a strong Data Engineer / PySpark / BFSI role gets a score >= 95%."""
    matcher = JobMatcher(profile=sample_profile)
    job = {
        "title": "Data Engineer - PySpark & ETL Pipelines",
        "company": "Axis Securities (BFSI)",
        "location": "Navi Mumbai, Maharashtra",
        "job_description": (
            "We are looking for a Data Engineer with 3+ years experience in Python, PySpark, "
            "SQL, and ETL pipelines in the Banking and Financial Services domain. "
            "Experience with Pentaho Data Integration, Hadoop, MySQL, and Power BI is preferred."
        )
    }
    result = matcher.evaluate_job(job)
    assert result.score >= 95.0, f"Expected >= 95.0, got {result.score}"
    assert result.is_eligible is True
    assert len(result.pros) > 0
    assert "PySpark" in str(result.pros) or "Python" in str(result.pros)


def test_job_matcher_disqualification():
    """Tests that internships and 10+ year roles are correctly disqualified."""
    matcher = JobMatcher()
    intern_job = {
        "title": "Software Engineering Intern (Unpaid)",
        "company": "College Project",
        "location": "Pune",
        "job_description": "Unpaid college internship."
    }
    res_intern = matcher.evaluate_job(intern_job)
    assert res_intern.score <= 30.0
    assert res_intern.is_eligible is False

    director_job = {
        "title": "Director of Data Engineering (12+ years experience)",
        "company": "MegaCorp",
        "location": "Navi Mumbai",
        "job_description": "Must have 12+ years of enterprise team leadership."
    }
    res_director = matcher.evaluate_job(director_job)
    assert res_director.score < 50.0
    assert res_director.is_eligible is False


def test_duplicate_checker(temp_db):
    """Verifies that duplicate jobs are detected by ID, URL, and fuzzy signature."""
    dedupe = DuplicateChecker(db=temp_db)

    job_a = {
        "job_id": "test_101",
        "title": "ETL Developer",
        "company": "FinTech Corp",
        "location": "Pune",
        "job_url": "https://linkedin.com/jobs/view/101?refId=xyz",
        "status": "Applied"
    }
    temp_db.upsert_job(job_a)

    # 1. Exact ID check
    is_dup, reason, _ = dedupe.check_duplicate({"job_id": "test_101"})
    assert is_dup is True
    assert "test_101" in reason

    # 2. Canonical URL check
    is_dup_url, reason_url, _ = dedupe.check_duplicate({
        "job_id": "test_999",
        "job_url": "https://linkedin.com/jobs/view/101?differentParam=123"
    })
    assert is_dup_url is True

    # 3. Fuzzy signature check (same company & title in active progress)
    is_dup_fuzzy, reason_fuzzy, _ = dedupe.check_duplicate({
        "job_id": "test_888",
        "title": "ETL Developer",
        "company": "FinTech Corp",
        "location": "Pune",
        "job_url": "https://linkedin.com/jobs/view/888"
    })
    assert is_dup_fuzzy is True
    assert "already in progress" in reason_fuzzy


def test_application_form_filler_factual_answers(sample_profile):
    """Tests that form filler uses verified profile facts without fabricating."""
    filler = ApplicationFormFiller(profile=sample_profile)
    job = {"title": "Data Engineer", "company": "Test Co", "location": "Navi Mumbai"}

    custom_questions = [
        {"question": "How many years of experience do you have with Python?"},
        {"question": "How many years of experience do you have with PySpark?"},
        {"question": "What is your notice period?"},
        {"question": "Are you authorized to work in India?"},
        {"question": "What was the name of your first elementary school teacher?"} # Unknown/unverified
    ]

    res = filler.prepare_application_data(job, custom_questions)

    assert res.fields_filled["full_name"] == "Harish Ghadage"
    assert res.fields_filled["email"] == sample_profile.email
    assert res.fields_filled["custom_How many years of experience do you have with Python?"] == "3.2"
    assert res.fields_filled["custom_How many years of experience do you have with PySpark?"] == "2.5"
    assert "30 Days" in res.fields_filled["custom_What is your notice period?"]

    # The unknown question must be flagged as unresolved rather than guessed!
    assert res.is_complete is False
    assert len(res.unresolved_questions) == 1
    assert "elementary school teacher" in res.unresolved_questions[0]["question"]


def test_application_submitter_policy(temp_db, sample_profile):
    """Verifies that submitter routes external portals and incomplete forms to approval."""
    submitter = ApplicationSubmitter(db=temp_db)

    # Case A: External application portal -> Must pause for manual approval
    job_external = {
        "job_id": "ext_501",
        "title": "Data Engineer",
        "company": "Global Bank",
        "location": "Pune",
        "is_easy_apply": False,
        "job_url": "https://company.careers/apply/501"
    }
    temp_db.upsert_job(job_external)
    status, msg = submitter.process_application(job_external, match_score=96.0)
    assert status == "Awaiting Approval"
    assert "External application portal" in msg

    # Case B: Easy Apply with high match (>= 95%) and complete facts -> Auto applied!
    job_easy = {
        "job_id": "easy_601",
        "title": "Data Engineer (PySpark)",
        "company": "Navi Finance",
        "location": "Navi Mumbai",
        "is_easy_apply": True,
        "job_url": "https://linkedin.com/jobs/view/601"
    }
    temp_db.upsert_job(job_easy)
    status_easy, msg_easy = submitter.process_application(job_easy, match_score=96.0)
    assert status_easy == "Applied"
    assert "Easy Apply successfully dispatched" in msg_easy


def test_hourly_summary_formatting():
    """Verifies that the hourly notification summary matches user specifications."""
    notifier = NotificationService()
    stats = {
        "jobs_discovered": 25,
        "relevant_jobs": 8,
        "high_priority_matches": 4,
        "applications_submitted": 3,
        "awaiting_review": 2,
        "duplicates_skipped": 5,
        "errors_count": 0
    }
    text = notifier.format_hourly_summary(stats)
    assert "Jobs discovered: 25" in text
    assert "Relevant jobs: 8" in text
    assert "High-priority matches: 4" in text
    assert "Applications submitted: 3" in text
    assert "Awaiting review: 2" in text
    assert "Duplicates skipped: 5" in text
    assert "Errors: 0" in text
