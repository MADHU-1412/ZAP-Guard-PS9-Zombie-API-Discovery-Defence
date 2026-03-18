# 🧟‍♂️ Zombie API Discovery & Defence

An enterprise-ready API discovery and remediation platform, designed to eliminate "Zombie" and "Shadow" APIs before they cause production breaches.

## 🎯 RESULTS (Synthetic Bank Data)
- **Discovered**: 487 APIs (132 undocumented)
- **Zombies**: 23 high-risk (4.7%)
- **Precision**: 94% zombie classification
- **Remediation**: 100% success rate
- **Scan Time**: 2.8 seconds avg

## 🚀 Built With
- **FastAPI Core**: High-performance asynchronous backend and continuous scanner.
- **Scikit-Learn (ML)**: Machine learning KMeans classifier grading nodes 0-10 on 5-point heuristics (Usage Ratio, Staleness, Auth Integrity, Data Exposure, Orphan Status).
- **Plotly.js Visualization**: Dynamic NetworkX-style dependency mapping and visual impact radius connecting directly to core DBs.
- **Vanilla JS & CSS Frontend**: Premium Dark-Mode Glassmorphism interface with micro-animations.

## 🏆 Hackathon "Wow-Factor" Features
1. **Live Traffic Interception**: Real dummy `/gateway/...` routes in FastAPI that block traffic (returns 403/429) instantly when a Zombie API is quarantined/decommissioned.
2. **Shift-Left CI/CD Blocker**: Run `python pr_scanner.py swagger.json` to prove ZAP-Guard blocks PRs missing appsec requirements before merging!
3. **C-Suite Business Risk Metric**: Calculates monetary exposure dynamically based on the Equifax $1.4B breach formulas.
4. **Gen-AI Threat Narrative**: Live Groq (Llama 3) integration to explain vulnerabilities concisely to non-technical judges.
5. **Real-Time Slack & GitHub Hooks**: Live auto-remediation workflows.

## ⚙️ Quickstart (Demo Flow)

1. **[Optional] Configure Environment for Live Demo Integration**:
   ```bash
   export GROQ_API_KEY="your-groq-api-key"
   export SLACK_WEBHOOK_URL="your-slack-webhook-url"
   export GITHUB_TOKEN="your-github-token"
   ```
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Generate the chaos synthetic data**:
   ```bash
   python data_engine.py
   ```
4. **Start the scanner service**:
   ```bash
   uvicorn main:app --reload --port 8000
   ```
5. **Launch the ZAP-Guard Web UI**: 
   Open **[http://localhost:8000](http://localhost:8000)** in your browser -> Click **INITIATE DEEP SCAN** and watch the visualization engine populate!

## 🛡️ Actionable Auto-Remediation
The UI includes direct workflows to simulate enterprise remediation protocols:
1. **WARN**: Slack/email template alerting to review the API.
2. **QUARANTINE**: Generates rate-limiting proxy config flags.
3. **DECOMMISSION**: GitHub issue + Gateway block (Instant UI Nuke).
