# AI-Powered LinkedIn Job Application Automation Agent

An enterprise-grade, intelligent automation system that continuously searches LinkedIn for relevant **Data Engineering, ETL, and Analytics** roles in **Navi Mumbai, Pune, and Mumbai**, evaluates opportunities against **Harish Ghadage's verified resume**, and automates permitted application submissions with strict zero-fabrication safety gates.

---

## 🎯 Target Configuration

- **Candidate:** Harish Ghadage (3+ years experience in BFSI / Banking / NBFC Data Engineering)
- **Minimum Match Score:** `95.0%` (Configurable in `config.yaml` / `.env`)
- **Application Mode:** `auto_submit` (automatically submits eligible Easy Apply applications scoring ≥ 95% with 100% verified facts)
- **Search Frequency:** Every `1 Hour` (3600 seconds)
- **Target Priority Roles:**
  1. Data Engineer
  2. ETL Developer
  3. Data Analyst
  4. PySpark Developer
  5. Python Developer – Data Engineering
  6. BI Developer / BI Data Engineer
- **Target Locations:**
  - Navi Mumbai, Maharashtra
  - Pune, Maharashtra
  - Mumbai, Maharashtra

---

## 🏗️ Architecture & Module Structure

```
linkedin_job_agent/
├── config.py                   # Type-safe configuration loader & .env integration
├── config.yaml                 # Core configuration (weights, thresholds, targets)
├── .env.example                # Secrets & session token templates
├── requirements.txt            # Project dependencies
├── resume_parser.py            # Resume parser (PDF/TXT) & verified profile loader
├── linkedin_auth.py            # AES-encrypted session tokens & verification
├── job_search.py               # Live LinkedIn job discovery engine
├── job_matcher.py              # Multi-dimensional scoring (0-100) & explainability
├── application_form_filler.py  # Factual form filler (strict zero-fabrication)
├── application_submitter.py    # Policy engine, rate limits & submission dispatcher
├── duplicate_checker.py        # Triple-layer deduplication (ID, URL, Fuzzy Signature)
├── database_manager.py         # SQLite WAL-mode database & audit logs
├── scheduler.py                # Hourly daemon loop & emergency stop killswitch
├── notification_service.py     # Hourly summaries, macOS desktop alerts & webhooks
├── dashboard.py                # Streamlit monitoring & control dashboard
├── main.py                     # CLI launcher and orchestrator
├── data/
│   ├── candidate_profile.json  # Verified source of truth candidate facts
│   ├── jobs.db                 # SQLite database
│   └── session.enc             # Encrypted session storage
├── resumes/
│   └── harish_ghadage_resume.txt
└── tests/
    └── test_agent.py           # Comprehensive pytest suite
```

---

## 🚀 Quick Start & CLI Commands

### 1. Run a Single Discovery Cycle
Executes job discovery across target cities, scores against resume, checks duplicates, and processes applications:
```bash
python linkedin_job_agent/main.py run-once
```

### 2. Launch the Streamlit Monitoring Dashboard
Interactive control center with live metrics, match charts, and manual review triggers:
```bash
python linkedin_job_agent/main.py dashboard --port 8501
# Or:
streamlit run linkedin_job_agent/dashboard.py
```
Open **http://localhost:8501** in your browser.

### 3. Start the Hourly Background Daemon
Runs discovery and submission continuously every 1 hour with graceful shutdown:
```bash
python linkedin_job_agent/main.py schedule
```

### 4. Check Agent Metrics & Status
View current database counts, queue statuses, and matching stats:
```bash
python linkedin_job_agent/main.py status
```

### 5. Verify or Update LinkedIn Session Authentication
Check if your LinkedIn session is active, or safely import session cookies:
```bash
python linkedin_job_agent/main.py auth
python linkedin_job_agent/main.py auth --cookie "your_li_at_cookie_value"
```

### 6. Inspect Resume Extraction
Validate that all facts, dates, and skills are extracted without invention:
```bash
python linkedin_job_agent/main.py parse-resume
```

---

## 🛡️ Reliability & Security Policy

1. **Zero Fabrication:** The agent strictly fills answers from verified profile facts. Any unknown question is isolated and queued for human review under `Awaiting Approval`.
2. **Encrypted Authentication:** LinkedIn cookies are encrypted with AES-128 Fernet. Passwords are never stored in plaintext or logged.
3. **Emergency Stop:** A kill switch can be toggled instantly from the Streamlit UI or `config.yaml` to pause automated submissions.
4. **Rate Limits:** Defends account standing by enforcing hourly (`5`) and daily (`25`) application caps.
5. **Triple-Layer Deduplication:** Matches by LinkedIn Job ID, canonical URL, and company+title fuzzy signature to prevent duplicate submissions across runs.

---

## 🧪 Running Automated Tests

Run the full pytest suite:
```bash
pytest linkedin_job_agent/tests/test_agent.py -v
```
All tests validate scoring logic, edge-case disqualifications, deduplication, factual form filling, and submission policies.
