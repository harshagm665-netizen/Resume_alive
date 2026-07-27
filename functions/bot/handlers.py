"""
functions/bot/handlers.py — Webhook handlers for Telegram bot.
"""
import json
from loguru import logger
from agents.orchestrator import Orchestrator
from bot.formatter import format_job_card, format_error
import requests
from config import TG_TOKEN

def send_message(chat_id: str, text: str):
    """Simple wrapper to send a telegram message via API."""
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Failed to send message: {e}")

def handle_webhook(update: dict):
    """Processes an incoming Telegram webhook update."""
    if "message" not in update:
        return
        
    msg = update["message"]
    chat_id = str(msg["chat"]["id"])
    text = msg.get("text", "").strip()
    
    if not text:
        return
        
    if text.startswith("/start"):
        send_message(chat_id, "Welcome to the Agentic Job Scraper! Send me a search query, e.g., 'Python Developer in Bangalore'.")
        return
        
    # Treat text as a search query
    logger.info(f"Received search request from {chat_id}: {text}")
    
    # Parse query and location roughly (e.g. "Software Engineer in Bangalore")
    parts = text.lower().split(" in ")
    if len(parts) > 1:
        query = parts[0]
        location = parts[1]
    else:
        query = text
        location = "India"
        
    send_message(chat_id, f"🔍 Searching for '{query}' in '{location}'...")
    
    try:
        orchestrator = Orchestrator()
        # In a real webhook, this might time out if it takes >10s.
        # Typically we would enqueue this and process in a background function.
        # But for this simple implementation, we run it directly.
        jobs = orchestrator.process_search_request(chat_id, query, location)
        
        if not jobs:
            send_message(chat_id, "No new jobs found matching your criteria.")
            return
            
        for job_dict in jobs[:5]: # Send top 5
            from db.models import Job
            job = Job(**job_dict)
            card = format_job_card(job)
            send_message(chat_id, card)
            
        if len(jobs) > 5:
            send_message(chat_id, f"...and {len(jobs)-5} more jobs saved to database.")
            
    except Exception as e:
        logger.error(f"Search failed: {e}")
        send_message(chat_id, format_error("An internal error occurred during the search."))
