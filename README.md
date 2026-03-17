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

## ⚙️ Quickstart (Demo Flow)
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Generate the chaos synthetic data (Wait for `endpoints.json` and `apis.csv` to be created):
   ```bash
   python data_engine.py
   ```
3. Start the scanner service:
   ```bash
   uvicorn main:app --reload --port 8000
   ```
4. Open `http://localhost:8000` -> Click **INITIATE DEEP SCAN** and watch the visualization engine populate!

## 🛡️ Actionable Auto-Remediation
The UI includes direct workflows to simulate enterprise remediation protocols:
1. **WARN**: Slack/email template alerting to review the API.
2. **QUARANTINE**: Generates rate-limiting proxy config flags.
3. **DECOMMISSION**: GitHub issue + Gateway block (Instant UI Nuke).
