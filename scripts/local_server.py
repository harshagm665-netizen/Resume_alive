import os
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import json
import sys

# Ensure functions directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../functions')))

# Try to import our webhook handler and orchestrator logic
try:
    from bot.handlers import handle_webhook
except ImportError:
    handle_webhook = None
    print("Warning: Could not import webhook handler. Ensure dependencies are installed.")

app = FastAPI(title="Job Scrapper Local Monitor")

# Mount the hosting directory so it can serve the CSS and JS for the dashboard
app.mount("/static", StaticFiles(directory="hosting"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves the monitoring dashboard UI."""
    try:
        with open("hosting/dashboard.html", "r") as f:
            html = f.read()
            # Fix asset paths for local testing
            html = html.replace('href="dashboard.css"', 'href="/static/dashboard.css"')
            html = html.replace('src="dashboard.js"', 'src="/static/dashboard.js"')
            return html
    except FileNotFoundError:
        return "<h1>Dashboard file not found! Make sure you are running from the project root.</h1>"

@app.post("/webhook")
async def telegram_webhook_local(request: Request, background_tasks: BackgroundTasks):
    """Local webhook receiver for Telegram testing."""
    if not handle_webhook:
        return {"status": "error", "message": "Handler not loaded"}
    
    update = await request.json()
    if update:
        # Run asynchronously in the background so Telegram gets an instant 200 OK
        background_tasks.add_task(handle_webhook, update)
    return {"status": "ok"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    print("======================================================")
    print("🚀 Local Monitor Server is starting...")
    print("📊 View your monitoring dashboard at: http://localhost:8000")
    print("🔗 Telegram Webhook endpoint at: http://localhost:8000/webhook")
    print("======================================================")
    uvicorn.run(app, host="0.0.0.0", port=8000)
