"""
functions/bot/formatter.py — Format job cards and messages for Telegram.
"""
from db.models import Job

def escape_md(text: str) -> str:
    if not text: return ""
    chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for c in chars:
        text = str(text).replace(c, '\\' + c)
    return text

def format_job_card(job: Job) -> str:
    """Formats a single job into a MarkdownV2 message."""
    title = escape_md(job.title)
    company = escape_md(job.company)
    location = escape_md(job.location)
    salary = escape_md(job.salary or "Not disclosed")
    experience = escape_md(job.experience or "Not specified")
    
    text = f"*{title}* at *{company}*\n"
    text += f"📍 {location}\n"
    text += f"💰 {salary} \\| ⏳ {experience}\n"
    
    if job.ai_score > 0:
        score = escape_md(str(job.ai_score))
        text += f"🤖 Match: {score}%"
        if job.metadata and job.metadata.get("match_level"):
            ml = escape_md(job.metadata['match_level'])
            text += f" \\({ml}\\)"
        text += "\n"
        
    url = job.url.replace('\\', '\\\\').replace(')', '\\)')
    text += f"\n[Apply Here]({url})"
    return text

def format_error(msg: str) -> str:
    return f"❌ *Error*: {escape_md(msg)}"
