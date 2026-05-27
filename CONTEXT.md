CRITICAL: Always cross-reference instructions with CONTEXT.md before proposing any code change.

# Project Context: Wetall Link Checker

## Business Goal
Surveiller la validité des liens d'affiliation et la disponibilité des stocks (focus grandes tailles) du catalogue Wetall.fr pour sécuriser le chiffre d'affaires.

## Tech Stack
- Runtime: Python 3.10 (httpx, beautifulsoup4, psycopg2-binary)
- Database: PostgreSQL (Neon.tech) via variable `DATABASE_URL`
- Automation: GitHub Actions (Trigger: workflow_dispatch & nightly cron)

## Architecture & Rules
1. Execution (Run): 100% deterministic, automated by GitHub Actions, storing results directly in Neon.tech. Zero Git commits generated during the run.
2. Database Schema: Table `wetall_link_history` (fields: id, date_scan, nom_produit, url_wetall, url_marchand, statut, code_etat).
3. Token Economy: Never rewrite the whole script if only one function changes. Use placeholders like `# ... rest of code remains unchanged`.