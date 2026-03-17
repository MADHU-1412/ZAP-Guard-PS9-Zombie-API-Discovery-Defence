import json
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import classifier

app = FastAPI(title="Zombie API Discovery & Defence")

# Allow CORS for easy testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_ui():
    return FileResponse("static/index.html")

@app.post("/scan")
@app.get("/scan")  
async def run_scan():
    # Simulate network scan delay (Requirement: < 3sec, let's do 1.5s for snappy feel)
    await asyncio.sleep(1.5)
    
    try:
        results = classifier.process_apis('endpoints.json')
        return {"status": "success", "data": results, "count": len(results)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.post("/remediate/{action}/{api_id}")
async def remediate(action: str, api_id: str):
    valid_actions = ["warn", "quarantine", "decommission"]
    if action not in valid_actions:
        raise HTTPException(status_code=400, detail="Invalid action")
        
    try:
        with open('endpoints.json', 'r') as f:
            endpoints = json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Data not found")
        
    api_found = False
    new_endpoints = []
    
    for ep in endpoints:
        if ep['id'] == api_id:
            api_found = True
            if action == "decommission":
                # Remove completely
                continue
            elif action == "quarantine":
                ep['status'] = "quarantined"
                # Reset calls to simulate quarantine effect
                ep['call_count_30d'] = 0
            elif action == "warn":
                ep['status'] = "warned"
        new_endpoints.append(ep)
        
    if not api_found:
        raise HTTPException(status_code=404, detail="API not found")
        
    with open('endpoints.json', 'w') as f:
        json.dump(new_endpoints, f, indent=4)
        
    messages = {
        "warn": f"Review Alert created for {api_id}: Slack notification dispatched.",
        "quarantine": f"Quarantine Engaged: Nginx rate-limiting config generated for {api_id}.",
        "decommission": f"API Nuked: {api_id} blocked at Gateway & GitHub deprecation issue created."
    }
        
    return {"status": "success", "message": messages[action], "api_id": api_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
