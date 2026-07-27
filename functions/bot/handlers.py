"""
functions/bot/handlers.py — Webhook handlers for Telegram bot.
"""
import json
import requests
from typing import Optional
from loguru import logger
from agents.orchestrator import Orchestrator
from agents.resume_analyzer import ResumeAnalyzerAgent
from bot.formatter import format_job_card, format_error
from db.firestore_client import fs_client
from db.models import UserProfile
from config import TG_TOKEN

def send_message(chat_id: str, text: str) -> Optional[dict]:
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        return None

def edit_message(chat_id: str, message_id: int, text: str):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Failed to edit message: {e}")

class StatusUpdater:
    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self.message_id = None
        self.current_text = ""
        
    def _escape(self, text: str) -> str:
        # Simple escape for MarkdownV2 inside the status block
        chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for c in chars:
            text = text.replace(c, '\\' + c)
        return text

    def update(self, status: str):
        self.current_text = f"🔄 *Status*: {self._escape(status)}"
        if not self.message_id:
            resp = send_message(self.chat_id, self.current_text)
            if resp and resp.get("ok"):
                self.message_id = resp["result"]["message_id"]
        else:
            edit_message(self.chat_id, self.message_id, self.current_text)

def download_file(file_id: str) -> Optional[bytes]:
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/getFile?file_id={file_id}"
        resp = requests.get(url, timeout=5).json()
        if not resp.get("ok"): return None
        
        file_path = resp["result"]["file_path"]
        dl_url = f"https://api.telegram.org/file/bot{TG_TOKEN}/{file_path}"
        dl_resp = requests.get(dl_url, timeout=10)
        return dl_resp.content
    except Exception as e:
        logger.error(f"File download failed: {e}")
        return None

def escape_md(text: str) -> str:
    chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for c in chars:
        text = text.replace(c, '\\' + c)
    return text

def handle_webhook(update: dict):
    if "message" not in update:
        return
        
    msg = update["message"]
    chat_id = str(msg["chat"]["id"])
    
    # Get user profile and state
    profile = fs_client.get_user_profile(chat_id)
    
    # Check Redis first for speed, fallback to profile/default
    from cache.redis_client import redis_client
    bot_state = redis_client.get(f"bot_state:{chat_id}")
    if not bot_state:
        bot_state = profile.bot_state if profile else "WAITING_FOR_RESUME"
    
    def set_bot_state(uid: str, state: str):
        redis_client.set(f"bot_state:{uid}", state)
        fs_client.update_bot_state(uid, state)
        
    text = msg.get("text", "").strip()
    
    # Handle /start
    if text.startswith("/start"):
        set_bot_state(chat_id, "WAITING_FOR_RESUME")
        send_message(chat_id, "Welcome to the Agentic Job Scraper\\!\n\nPlease upload your resume \\(PDF/DOCX\\) so I can automatically detect your role and match you with the best jobs\\.")
        return
        
    # Handle document upload
    if "document" in msg:
        if bot_state != "WAITING_FOR_RESUME":
            send_message(chat_id, "I've received a document, but I'm currently processing something else\\. Type /start to restart\\.")
            return
            
        doc = msg["document"]
        file_name = doc.get("file_name", "resume")
        file_id = doc["file_id"]
        
        status = StatusUpdater(chat_id)
        status.update("Downloading your resume...")
        
        file_bytes = download_file(file_id)
        if not file_bytes:
            send_message(chat_id, escape_md("❌ Failed to download file. Please try again."))
            return
            
        status.update("Analyzing resume and extracting skills...")
        analyzer = ResumeAnalyzerAgent()
        extracted = analyzer.analyze(file_bytes, file_name)
        
        if not extracted:
            send_message(chat_id, escape_md("❌ Could not parse the resume. Please ensure it is a valid PDF or DOCX."))
            return
            
        # Save profile
        if not profile:
            profile = UserProfile(uid=chat_id)
        profile.current_role = extracted.get("current_role", "Software Engineer")
        profile.skill_graph = extracted
        profile.bot_state = "CONFIRMING_ROLE"
        fs_client.save_user_profile(profile)
        
        # Ensure Redis cache is updated too
        set_bot_state(chat_id, "CONFIRMING_ROLE")
        
        role_md = escape_md(profile.current_role)
        status.update(f"Resume processed successfully!")
        send_message(chat_id, f"I've analyzed your resume and see you are a *{role_md}*\\.\n\nReply with *'Yes'* to search for this role in Bangalore/Remote, or type a custom query like *'AI Engineer in remote'*\\.")
        return

    # Handle text messages based on state
    if bot_state == "WAITING_FOR_RESUME":
        send_message(chat_id, "Please upload your resume \\(PDF/DOCX\\) first, or type /start to restart\\.")
        return
        
    if bot_state == "CONFIRMING_ROLE":
        if not profile:
            set_bot_state(chat_id, "WAITING_FOR_RESUME")
            send_message(chat_id, "I couldn't find your profile\\. Please upload your resume again or type /start\\.")
            return
            
        if text.lower() in ["yes", "y", "search"]:
            query = profile.current_role
            location = "Bangalore" # Default
        else:
            parts = text.lower().split(" in ")
            if len(parts) > 1:
                query = parts[0]
                location = parts[1]
            else:
                query = text
                location = "India"
                
        set_bot_state(chat_id, "READY")
        
        status = StatusUpdater(chat_id)
        status.update(f"Searching for '{query}' in '{location}'...")
        
        def progress_callback(msg: str):
            status.update(msg)
            
        try:
            orchestrator = Orchestrator()
            jobs = orchestrator.process_search_request(chat_id, query, location, progress_callback=progress_callback)
            
            if not jobs:
                status.update("Search finished.")
                send_message(chat_id, "No new jobs found matching your criteria\\.")
            else:
                status.update("Formatting top matches...")
                for job_dict in jobs[:5]:
                    from db.models import Job
                    job = Job(**job_dict)
                    card = format_job_card(job)
                    send_message(chat_id, card)
                    
                if len(jobs) > 5:
                    send_message(chat_id, escape_md(f"...and {len(jobs)-5} more jobs saved to database."))
                    
                status.update("Search complete!")
                
        except Exception as e:
            logger.error(f"Search failed: {e}")
            send_message(chat_id, format_error("An internal error occurred during the search."))
            
        set_bot_state(chat_id, "CONFIRMING_ROLE") # Reset for next search
        return

    # If READY or weird state
    set_bot_state(chat_id, "CONFIRMING_ROLE")
    send_message(chat_id, "I was in an unexpected state\\. Please try your search again\\.")
