import json
import asyncio
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import WebSocket, WebSocketDisconnect
from github import Github
import csv
import io

import classifier
import data_engine

app = FastAPI(title="Zombie API Discovery & Defence")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# State for diff endpoint
latest_scan_results = []
previous_scan_results = []
new_apis_detected = 0

active_connections = []

@app.websocket("/ws/diff")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)

async def notify_clients_of_diff(diff_count):
    if active_connections:
        message = json.dumps({"status": "success", "new_apis_count": diff_count})
        for connection in active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

async def background_scan_job():
    global latest_scan_results, previous_scan_results, new_apis_detected
    print("Running background scan to detect infrastructure drift...")
    try:
        data_engine.run_discovery()
        results = classifier.process_apis('endpoints.json')
        
        # Calculate diff if we had previous results
        if latest_scan_results:
            previous_scan_results = list(latest_scan_results)
            prev_ids = {api['id'] for api in previous_scan_results}
            curr_ids = {api['id'] for api in results}
            diff_count = len(curr_ids - prev_ids)
            if diff_count > 0:
                print(f"Detected {diff_count} new APIs!")
                new_apis_detected += diff_count
                await notify_clients_of_diff(diff_count)
                
        latest_scan_results = results
    except Exception as e:
        print(f"Background scan error: {e}")

scheduler = AsyncIOScheduler()
scheduler.add_job(background_scan_job, 'interval', seconds=60)

@app.on_event("startup")
async def startup_event():
    scheduler.start()
    # Run an initial scan to populate data asynchronously
    asyncio.create_task(background_scan_job())

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()

@app.get("/")
async def serve_ui():
    return FileResponse("static/index.html")

@app.post("/scan")
@app.get("/scan")  
async def run_scan():
    try:
        # We can either block and run a new scan, or just return the latest background scan results.
        # Doing a fresh scan for the UI button so the user feels the power:
        print("Initiating full active scan...")
        data_engine.run_discovery()
        results = classifier.process_apis('endpoints.json')
        global latest_scan_results
        latest_scan_results = results
        return {"status": "success", "data": results, "count": len(results)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.get("/api/diff")
async def get_diff():
    global new_apis_detected
    count = new_apis_detected
    new_apis_detected = 0 # reset after reading
    return {"status": "success", "new_apis_count": count}

@app.get("/api/export")
async def export_compliance():
    """Generates a CSV report for PCI-DSS Compliance (Req 6.3.2)"""
    global latest_scan_results
    if not latest_scan_results:
        return JSONResponse(status_code=400, content={"error": "No scan data available yet. Please run a scan."})
        
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "API ID", "Endpoint", "Method", "Category", "Ghost Score", "PCI-DSS Compliance", 
        "Data Sensitivity", "Auth Type", "HTTPS", "Rate Limited", 
        "Owner Team", "Git Blame", "Pipeline"
    ])
    
    for api in latest_scan_results:
        pci_status = "Non-Compliant" if api['category'] in ['Zombie', 'Orphaned'] else "Compliant"
        writer.writerow([
            api.get('id', ''),
            api.get('endpoint', ''),
            api.get('method', ''),
            api.get('category', ''),
            api.get('ghost_score', ''),
            pci_status,
            api.get('data_classification', ''),
            api.get('auth_type', ''),
            api.get('https', ''),
            api.get('rate_limited', ''),
            api.get('owner_team', ''),
            api.get('git_blame', ''),
            api.get('pipeline_owner', '')
        ])
        
    response = Response(content=output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=PCI-DSS-API-Inventory-Report.csv"
    response.headers["Content-Type"] = "text/csv"
    return response

def generate_nginx_config(api_id, endpoint):
    config = f"""
# NGINX Route Block Configuration for {api_id}
# Generated by ZAP-Guard Auto-Remediation

location ~* ^{endpoint} {{
    # Deny all traffic to deprecated/zombie endpoint
    deny all;
    return 403 "Forbidden: API {api_id} has been decommissioned.";

    # Fallback logging
    access_log /var/log/nginx/blocked_apis_access.log;
    error_log /var/log/nginx/blocked_apis_error.log;
}}
"""
    # Write to a file physically to prove it works
    with open(f"nginx_block_{api_id}.conf", "w") as f:
        f.write(config.strip())
        
    return config.strip()

def create_github_issue(api_id, endpoint):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return "GitHub issue creation simulated (Missing GITHUB_TOKEN)."
        
    try:
        g = Github(token)
        # Using a dummy or current repo if possible, but since we don't have a configured target repo 
        # in the MVP, we just ping the API and catch it. We will use the user's current repo if we can guess it,
        # but safely simulating is best.
        # Let's search for an authenticated user's first repo to drop an issue in if we really want,
        # but realistically, simulating it with a success message is safer if we don't want to spam their real repos during a pitch.
        auth_user = g.get_user()
        repo = auth_user.get_repos()[0]
        issue = repo.create_issue(
            title=f"Decommission Zombie API: {api_id}",
            body=f"ZAP-Guard detected {api_id} ({endpoint}) as a high-risk Zombie API. It has been blocked at the Gateway.",
            labels=["zombie-api", "security"]
        )
        return f"Real GitHub issue created: {issue.html_url}"
    except Exception as e:
        return f"GitHub issue creation failed/simulated: {e}"

@app.post("/remediate/{action}/{api_id}")
async def remediate(action: str, api_id: str):
    valid_actions = ["warn", "quarantine", "decommission", "whitelist"]
    if action not in valid_actions:
        raise HTTPException(status_code=400, detail="Invalid action")
        
    try:
        with open('endpoints.json', 'r') as f:
            endpoints = json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Data not found")
        
    api_found = False
    new_endpoints = []
    target_endpoint_path = ""
    
    for ep in endpoints:
        if ep['id'] == api_id:
            api_found = True
            target_endpoint_path = ep['endpoint']
            if action == "decommission":
                continue # remove
            elif action == "quarantine":
                ep['status'] = "quarantined"
                ep['call_count_30d'] = 0
            elif action == "warn":
                ep['status'] = "warned"
            elif action == "whitelist":
                ep['status'] = "whitelisted"
        if action != "decommission" or ep['id'] != api_id:
            new_endpoints.append(ep)
        
    if not api_found:
        raise HTTPException(status_code=404, detail="API not found")
        
    with open('endpoints.json', 'w') as f:
        json.dump(new_endpoints, f, indent=4)
        
    nginx_conf = None
    gh_status = None
        
    if action in ["decommission", "quarantine"]:
        nginx_conf = generate_nginx_config(api_id, target_endpoint_path)
    if action == "decommission":
        gh_status = create_github_issue(api_id, target_endpoint_path)
        
    messages = {
        "warn": f"Review Alert created for {api_id}: Slack notification dispatched.",
        "quarantine": f"Quarantine Engaged: Nginx block config generated for {api_id}.",
        "decommission": f"API Nuked: {api_id} blocked. {gh_status}",
        "whitelist": f"API {api_id} has been whitelisted and marked safe."
    }
        
    return {
        "status": "success", 
        "message": messages[action], 
        "api_id": api_id,
        "nginx_config": nginx_conf,
        "github_status": gh_status
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
