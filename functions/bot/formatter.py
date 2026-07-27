"""
functions/bot/formatter.py — Format job cards and messages for Telegram.
"""
from db.models import Job

def format_job_card(job: Job) -> str:
    """Formats a single job into a MarkdownV2 message."""
    title = job.title.replace('*', '').replace('_', '\\_')
    company = job.company.replace('*', '').replace('_', '\\_')
    location = job.location.replace('_', '\\_')
    
    text = f"*{title}* at *{company}*\n"
    text += f"📍 {location}\n"
    text += f"💰 {job.salary} | ⏳ {job.experience}\n"
    
    if job.ai_score > 0:
        text += f"🤖 Match: {job.ai_score}%"
        if job.metadata.get("match_level"):
            text += f" ({job.metadata['match_level']})"
        text += "\n"
        
    text += f"\n[Apply Here]({job.url})"
    return text

def format_error(msg: str) -> str:
    return f"❌ *Error*: {msg}"
