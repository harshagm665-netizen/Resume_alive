"""
core/formatter.py — Formats job results as Telegram HTML messages.
"""

import re
from scrapers.base import Job

PORTAL_EMOJI = {
    "LinkedIn": "💼",
    "Naukri": "🟡",
    "Indeed": "🔵",
    "InstaHyre": "🟣",
    "Foundit": "🟠",
    "Shine": "✨",
}

MATCH_EMOJI = {
    "Excellent": "🔥",
    "Good": "✅",
    "Fair": "🟡",
    "Low": "🔴",
}

SCORE_BAR_MAP = [
    (90, "█████ 90–100%"),
    (80, "████░ 80–89%"),
    (70, "███░░ 70–79%"),
    (60, "██░░░ 60–69%"),
    (50, "█░░░░ 50–59%"),
    (40, "▒░░░░ 40–49%"),
    (0,  "░░░░░  <40%"),
]


def _score_bar(score: int) -> str:
    for threshold, bar in SCORE_BAR_MAP:
        if score >= threshold:
            return bar
    return "░░░░░"


def format_job_card(job: Job, rank: int | None = None) -> str:
    """Format a single Job as a Telegram HTML message card."""
    portal_em = PORTAL_EMOJI.get(job.portal, "🌐")
    match_em = MATCH_EMOJI.get(job.match_level, "⚪")

    rank_str = f"#{rank} " if rank else ""
    score_str = f"{job.score}%" if job.score else ""
    score_line = ""
    if job.score:
        bar = _score_bar(job.score)
        score_line = f"\n{match_em} <b>Match:</b> {score_str}  <code>{bar}</code>"

    reason_line = f"\n💡 <i>{job.score_reason}</i>" if job.score_reason else ""

    matching_line = ""
    if job.matching_skills:
        skills_preview = " · ".join(job.matching_skills[:5])
        matching_line = f"\n🎯 <b>Matching:</b> {skills_preview}"

    missing_line = ""
    if job.missing_skills:
        missing_preview = " · ".join(job.missing_skills[:3])
        missing_line = f"\n⚠️ <b>Missing:</b> {missing_preview}"

    salary_line = f"\n💰 <b>Salary:</b> {job.salary}" if job.salary and job.salary != "Not disclosed" else ""
    exp_line = f"\n🧪 <b>Exp:</b> {job.experience}" if job.experience and job.experience != "Not specified" else ""
    date_line = f"\n🗓 <b>Posted:</b> {job.posted_date}" if job.posted_date else ""

    card = (
        f"\n{portal_em} <b>{rank_str}{job.title}</b>"
        f"{score_line}"
        f"\n🏢 <b>{job.company}</b>  📍 {job.location}"
        f"{salary_line}"
        f"{exp_line}"
        f"{date_line}"
        f"{matching_line}"
        f"{missing_line}"
        f"{reason_line}"
        f"\n🔗 <a href='{job.url}'>Apply on {job.portal}</a>"
        f"\n{'─' * 28}"
    )
    return card


def format_search_header(
    query: str,
    location: str,
    total_found: int,
    shown: int,
    portals_used: list[str],
    has_resume: bool = False,
) -> str:
    portals_str = " · ".join(portals_used)
    resume_note = " (matched against your resume)" if has_resume else ""
    return (
        f"🔍 <b>Job Search Results{resume_note}</b>\n"
        f"📌 <b>Query:</b> {query}  |  📍 <b>Location:</b> {location}\n"
        f"🌐 <b>Portals:</b> {portals_str}\n"
        f"📊 <b>Found:</b> {total_found} jobs → Showing top <b>{shown}</b>\n"
        f"{'═' * 30}\n"
    )


def format_resume_header(profile: dict) -> str:
    name = profile.get("name", "Candidate")
    role = profile.get("current_role", "")
    exp = profile.get("total_experience_years", 0)
    skills_preview = ", ".join(profile.get("skills", [])[:8])
    return (
        f"📄 <b>Resume Parsed Successfully</b>\n"
        f"👤 <b>{name}</b>"
        + (f" — {role}" if role else "")
        + (f"  ({exp} yrs exp)" if exp else "")
        + f"\n🔧 <b>Skills:</b> {skills_preview or 'N/A'}\n"
        f"{'─' * 30}\n"
    )


def format_no_results(query: str, location: str) -> str:
    return (
        f"😔 <b>No matching jobs found</b>\n"
        f"Query: <i>{query}</i> in <i>{location}</i>\n\n"
        f"Try:\n"
        f"• Broaden your search keywords\n"
        f"• Try a nearby city\n"
        f"• Check spelling\n"
    )


def format_error(msg: str) -> str:
    return f"⚠️ <b>Error:</b> {msg}"


def split_into_chunks(text: str, max_len: int = 4000) -> list[str]:
    """Split long text into Telegram-safe chunks without breaking HTML tags."""
    if len(text) <= max_len:
        return [text] if text.strip() else []

    chunks = []
    while len(text) > max_len:
        # Find a safe split point at a newline
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len

        chunk = text[:split_at]

        # Close any unclosed HTML tags in this chunk
        open_tags = re.findall(r"<([a-zA-Z]+)[^>]*>", chunk)
        close_tags = re.findall(r"</([a-zA-Z]+)>", unclosed := chunk)
        # Count open vs close for each tag
        tag_counts: dict[str, int] = {}
        for tag in open_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        for tag in close_tags:
            if tag in tag_counts:
                tag_counts[tag] -= 1

        # Close any remaining open tags
        for tag, count in tag_counts.items():
            if count > 0:
                chunk += f"</{tag}>" * count

        chunks.append(chunk)
        text = text[split_at:]

        # Re-open tags that were closed at the boundary for the next chunk
        if tag_counts:
            reopen = "".join(f"<{tag}>" for tag, count in tag_counts.items() if count > 0)
            text = reopen + text

    if text.strip():
        chunks.append(text)
    return chunks
