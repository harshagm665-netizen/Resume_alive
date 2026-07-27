"""
main.py — Telegram Job Scraper Bot with guided narrative flow.

Flow:
  /start -> Welcome -> Ask role -> Ask location -> Search -> Show results
  -> Suggest resume upload -> Repeat
"""

import asyncio
import atexit
import html
import os
import re
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger
from telegram import (
    Update, BotCommand,
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
    ConversationHandler,
)
from telegram.constants import ParseMode, ChatAction
from telegram.error import TelegramError

from config import TG_TOKEN, KEY_ROTATOR, ALL_GROQ_KEYS, GEMINI_API_KEY, SCORE_THRESHOLD, normalize_location
from scrapers import ALL_SCRAPERS, SCRAPER_INSTANCES, Job
from core import (
    parse_resume, batch_score,
    format_job_card, format_search_header, format_resume_header,
    format_no_results, format_error, split_into_chunks,
)
from db import db

# ── Single-instance PID lock ───────────────────────────────────────────────────
_LOCKFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.pid")

def _acquire_lock() -> None:
    if os.path.exists(_LOCKFILE):
        try:
            with open(_LOCKFILE) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)
            print(f"\nBot already running (PID {old_pid}). Stop it first.")
            sys.exit(1)
        except (ValueError, OSError):
            pass
    with open(_LOCKFILE, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(lambda: os.unlink(_LOCKFILE) if os.path.exists(_LOCKFILE) else None)

_acquire_lock()


# ── Conversation states ────────────────────────────────────────────────────────
ASK_ROLE      = 1
ASK_LOCATION  = 2
AWAITING_RESUME = 3


# ── Keyboard ───────────────────────────────────────────────────────────────────

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("New Search"), KeyboardButton("Upload Resume")],
        [KeyboardButton("My Status"),  KeyboardButton("Help")],
    ],
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Type a job role or tap a button...",
)

SKIP_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton("Skip")]],
    resize_keyboard=True,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _scrape_all_portals(query: str, location: str) -> tuple[list[Job], list[str], dict[str, str]]:
    all_jobs: list[Job] = []
    portals_used: list[str] = []
    errors: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=6) as executor:
        future_map = {
            executor.submit(
                SCRAPER_INSTANCES[scraper_cls.portal_name].search,
                query, location, 10,
            ): scraper_cls.portal_name
            for scraper_cls in ALL_SCRAPERS
            if scraper_cls.portal_name in SCRAPER_INSTANCES
        }
        for future in as_completed(future_map, timeout=60):
            portal_name = future_map[future]
            try:
                jobs = future.result()
                if jobs:
                    all_jobs.extend(jobs)
                    portals_used.append(portal_name)
                    logger.info(f"[{portal_name}] {len(jobs)} jobs")
                else:
                    errors[portal_name] = "No results"
            except Exception as e:
                import traceback
                logger.error(f"[{portal_name}] Scraper failed: {e}\n{traceback.format_exc()}")
                errors[portal_name] = str(e)

    return all_jobs, portals_used, errors


async def _send_long_message(message, text: str) -> None:
    chunks = split_into_chunks(text, max_len=4000)
    for chunk in chunks:
        try:
            await message.reply_text(chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        except TelegramError:
            plain = re.sub(r"<[^>]+>", "", chunk)
            try:
                await message.reply_text(plain[:4000])
            except Exception:
                pass


def _resume_prompt_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Yes, upload resume", callback_data="action:upload"),
            InlineKeyboardButton("Skip for now", callback_data="action:skip"),
        ],
    ])


async def _do_search(message, user_id: str, query: str, location: str) -> None:
    # Use the exact query to avoid confusing job board search engines (which might do an OR search for "actively hiring")
    search_query = query
    q_safe = html.escape(query)
    l_safe = html.escape(location)

    status_msg = await message.reply_text(
        f"Searching <b>{q_safe}</b> in <b>{l_safe}</b>...\n"
        "Scraping 5 portals concurrently...",
        parse_mode=ParseMode.HTML,
    )

    try:
        all_jobs, portals_used, errors = await asyncio.get_running_loop().run_in_executor(
            None, _scrape_all_portals, search_query, location
        )

        if not all_jobs:
            await status_msg.edit_text(
                format_no_results(q_safe, l_safe), parse_mode=ParseMode.HTML
            )
            return

        seen: set[str] = set()
        unique_jobs: list[Job] = []
        
        def is_older_than_a_week(posted: str) -> bool:
            p = posted.lower()
            old_keywords = ["month", "30 days", "14 days", "15 days", "20 days", "weeks", "2 week", "3 week", "4 week", "year"]
            for k in old_keywords:
                if k in p:
                    return True
            return False
            
        def matches_location(job_loc: str, target_loc: str) -> bool:
            jl = job_loc.lower()
            tl = target_loc.lower()
            if tl in jl or "remote" in jl: return True
            if tl == "india" or tl == "skip": return True
            if "bangalore" in tl or "banglore" in tl or "bengaluru" in tl:
                if "bangalore" in jl or "bengaluru" in jl or "banglore" in jl: return True
            return False

        def is_relevant(job_title: str, search_query: str) -> bool:
            query_words = [w.lower() for w in search_query.split() if len(w) > 2]
            jt = job_title.lower()
            return any(qw in jt for qw in query_words)

        for job in all_jobs:
            if is_older_than_a_week(job.posted_date or ""):
                continue
            if not matches_location(job.location, location):
                continue
            if not is_relevant(job.title, query):
                continue
                
            k = job.dedup_key()
            if k not in seen:
                seen.add(k)
                unique_jobs.append(job)

        await status_msg.edit_text(
            f"Found <b>{len(unique_jobs)}</b> unique recent jobs. Scoring with AI...",
            parse_mode=ParseMode.HTML,
        )

        resume_profile = db.get_resume_profile(user_id)
        has_resume = bool(resume_profile)

        scored_jobs = await asyncio.get_running_loop().run_in_executor(
            None, batch_score, unique_jobs, resume_profile, query, location, SCORE_THRESHOLD
        )

        top_jobs = scored_jobs[:25]

        for job in scored_jobs:
            db.upsert_job(job, search_query=query, search_location=location, user_id=user_id)
        db.log_search(user_id, query, location, len(unique_jobs), portals_used, has_resume)

        if not top_jobs:
            await status_msg.edit_text(
                format_no_results(q_safe, l_safe), parse_mode=ParseMode.HTML
            )
            return

        await status_msg.delete()

        header = format_search_header(
            query=q_safe, location=l_safe,
            total_found=len(unique_jobs), shown=len(top_jobs),
            portals_used=portals_used, has_resume=has_resume,
        )
        await message.reply_text(header, parse_mode=ParseMode.HTML)

        full_text = ""
        for i, job in enumerate(top_jobs, 1):
            full_text += format_job_card(job, rank=i) + "\n"
        await _send_long_message(message, full_text)

        if errors:
            failed = html.escape(", ".join(errors.keys()))
            await message.reply_text(
                f"Portals with issues: {failed}", parse_mode=ParseMode.HTML
            )

        if not has_resume:
            await message.reply_text(
                "Want better matches? Upload your resume and I'll personalize every search!",
                reply_markup=_resume_prompt_kb(),
            )

    except Exception as e:
        logger.error(f"Search error: {e}\n{traceback.format_exc()}")
        try:
            await status_msg.edit_text(
                format_error(html.escape(str(e)[:200])), parse_mode=ParseMode.HTML
            )
        except Exception:
            pass


# ── Entry: /start ──────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_id = str(user.id)
    has_resume = db.get_resume_profile(user_id) is not None

    if has_resume:
        text = (
            f"Welcome back, <b>{html.escape(user.first_name)}</b>!\n\n"
            "I'm your Job Scraper Bot. I search 5 portals at once "
            "and rank results with AI.\n\n"
            "Your resume is loaded - searches will be personalized.\n\n"
            "<b>What role are you looking for?</b>\n"
            "Just type it, e.g. <code>python developer</code>, <code>data scientist</code>"
        )
    else:
        text = (
            f"Hey <b>{html.escape(user.first_name)}</b>! I'm your Job Scraper Bot.\n\n"
            "I search LinkedIn, Indeed, Naukri, InstaHyre, and Shine "
            "all at once and rank results with AI.\n\n"
            "<b>What role are you looking for?</b>\n"
            "Just type it, e.g. <code>python developer</code>, <code>data scientist</code>"
        )

    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=MAIN_KB)
    context.user_data["flow"] = "ask_role"
    return ASK_ROLE


# ── State: ASK_ROLE ────────────────────────────────────────────────────────────

async def handle_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if not text:
        return ASK_ROLE

    tl = text.lower()

    # Keyboard button shortcuts (always work regardless of flow)
    if tl == "new search":
        await update.message.reply_text(
            "<b>What role are you looking for?</b>\n"
            "e.g. <code>python developer</code>, <code>react frontend</code>, <code>ml engineer</code>",
            parse_mode=ParseMode.HTML,
        )
        context.user_data["flow"] = "ask_role"
        return ASK_ROLE

    if tl == "upload resume":
        await update.message.reply_text(
            "Send your resume (PDF or DOCX).\n"
            "I'll extract your skills and personalize future searches.\n\n"
            "Send /cancel to go back.",
            reply_markup=ReplyKeyboardRemove(),
        )
        context.user_data["flow"] = "awaiting_resume"
        return AWAITING_RESUME

    if tl == "my status":
        user_id = str(update.effective_user.id)
        has_resume = db.get_resume_profile(user_id) is not None
        groq_available = len([k for k in ALL_GROQ_KEYS if k not in KEY_ROTATOR._exhausted])
        groq_total = len(ALL_GROQ_KEYS)
        gemini_ok = bool(GEMINI_API_KEY)

        msg = (
            "<b>Bot Status</b>\n\n"
            f"Groq Keys: {groq_available}/{groq_total} available\n"
            f"Gemini Fallback: {'Ready' if gemini_ok else 'No key'}\n"
            f"Resume: {'Saved - personalized matching' if has_resume else 'Not uploaded'}\n"
            f"Database: SQLite (WAL mode)\n"
            f"Portals: {len(ALL_SCRAPERS)} active"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=MAIN_KB)
        context.user_data["flow"] = "ask_role"
        return ASK_ROLE

    if tl == "help":
        msg = (
            "<b>How it works:</b>\n\n"
            "1. Tell me what job you want\n"
            "2. Tell me the city\n"
            "3. I search 5 portals at once\n"
            "4. AI ranks results by relevance\n"
            "5. You get top matches with apply links\n\n"
            "<b>Portals searched:</b>\n"
            "LinkedIn, Indeed, Naukri, InstaHyre, Shine\n\n"
            "<b>Commands:</b>\n"
            "/start - Begin a new search\n"
            "/search python developer in bangalore - Quick search\n"
            "/upload - Upload resume for personalized matching\n"
            "/status - Check bot health\n"
            "/clearresume - Remove saved resume"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=MAIN_KB)
        context.user_data["flow"] = "ask_role"
        return ASK_ROLE

    # Regular text -> treat as job role
    context.user_data["query"] = text
    await update.message.reply_text(
        f"<b>{html.escape(text)}</b> - got it!\n\n"
        "<b>Which city?</b>\n"
        "e.g. <code>bangalore</code>, <code>mumbai</code>, <code>pune</code>, <code>delhi</code>\n"
        "Or tap Skip for nationwide results.",
        parse_mode=ParseMode.HTML,
        reply_markup=SKIP_KB,
    )
    context.user_data["flow"] = "ask_location"
    return ASK_LOCATION


# ── State: ASK_LOCATION ────────────────────────────────────────────────────────

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    query = context.user_data.get("query", "Software Engineer")
    location = "India" if text.lower() == "skip" else text

    if not location:
        location = "India"

    user_id = str(update.effective_user.id)
    await _do_search(update.message, user_id, query, location)

    await update.message.reply_text(
        "What would you like to do next?",
        reply_markup=MAIN_KB,
    )
    context.user_data["flow"] = "ask_role"
    return ASK_ROLE


# ── State: AWAITING_RESUME ─────────────────────────────────────────────────────

async def handle_resume_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = str(update.effective_user.id)
    doc = update.message.document

    if not doc:
        await update.message.reply_text("Please send a PDF or DOCX file.")
        return AWAITING_RESUME

    filename = doc.file_name or "resume.pdf"
    if not (filename.lower().endswith(".pdf") or filename.lower().endswith(".docx")):
        await update.message.reply_text("Only PDF and DOCX files are supported. Try again.")
        return AWAITING_RESUME

    status = await update.message.reply_text("Parsing your resume...")

    try:
        tg_file = await doc.get_file()
        file_bytes = bytes(await tg_file.download_as_bytearray())

        profile = await asyncio.get_running_loop().run_in_executor(
            None, parse_resume, file_bytes, filename
        )

        db.save_resume_profile(user_id, profile, filename)

        summary = format_resume_header(profile)
        await status.edit_text(
            summary + "\nResume saved! All future searches will be personalized.",
            parse_mode=ParseMode.HTML,
        )

        await update.message.reply_text(
            "<b>Now, what role are you looking for?</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=MAIN_KB,
        )
        context.user_data["flow"] = "ask_role"
        return ASK_ROLE

    except Exception as e:
        logger.error(f"Resume upload error: {e}\n{traceback.format_exc()}")
        await status.edit_text(
            format_error(html.escape(str(e)[:200])), parse_mode=ParseMode.HTML
        )
        await update.message.reply_text("Try again or send /cancel.", reply_markup=MAIN_KB)
        return AWAITING_RESUME


# ── Commands that work outside conversation ────────────────────────────────────

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cancelled.", reply_markup=MAIN_KB)
    context.user_data["flow"] = "ask_role"
    return ConversationHandler.END


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    args_text = " ".join(context.args) if context.args else ""
    if not args_text:
        await update.message.reply_text(
            "<b>What role are you looking for?</b>\n"
            "e.g. <code>/search python developer in bangalore</code>",
            parse_mode=ParseMode.HTML,
        )
        context.user_data["flow"] = "ask_role"
        return ASK_ROLE

    lower = args_text.lower()
    if " in " in lower:
        idx = lower.rfind(" in ")
        query = args_text[:idx].strip()
        location = args_text[idx + 4:].strip()
    else:
        query = args_text
        location = "India"

    user_id = str(update.effective_user.id)
    await _do_search(update.message, user_id, query, location)
    await update.message.reply_text("What next?", reply_markup=MAIN_KB)
    context.user_data["flow"] = "ask_role"
    return ASK_ROLE


async def cmd_clear_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db.delete_resume_profile(str(update.effective_user.id))
    await update.message.reply_text(
        "Resume cleared. Searches will use generic scoring now.",
        reply_markup=MAIN_KB,
    )
    context.user_data["flow"] = "ask_role"
    return ASK_ROLE


async def cmd_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Send your resume (PDF or DOCX).\n"
        "I'll extract your skills and personalize future searches.\n\n"
        "Send /cancel to go back.",
        reply_markup=ReplyKeyboardRemove(),
    )
    context.user_data["flow"] = "awaiting_resume"
    return AWAITING_RESUME


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = str(update.effective_user.id)
    has_resume = db.get_resume_profile(user_id) is not None
    groq_available = len([k for k in ALL_GROQ_KEYS if k not in KEY_ROTATOR._exhausted])
    groq_total = len(ALL_GROQ_KEYS)
    gemini_ok = bool(GEMINI_API_KEY)

    msg = (
        "<b>Bot Status</b>\n\n"
        f"Groq Keys: {groq_available}/{groq_total} available\n"
        f"Gemini Fallback: {'Ready' if gemini_ok else 'No key'}\n"
        f"Resume: {'Saved' if has_resume else 'Not uploaded'}\n"
        f"Portals: {len(ALL_SCRAPERS)} active"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=MAIN_KB)
    context.user_data["flow"] = "ask_role"
    return ASK_ROLE


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = (
        "<b>How it works:</b>\n\n"
        "1. Tell me what job you want\n"
        "2. Tell me the city\n"
        "3. I search 5 portals at once\n"
        "4. AI ranks results by relevance\n"
        "5. You get top matches with apply links\n\n"
        "<b>Commands:</b>\n"
        "/start - Begin\n"
        "/search python developer in bangalore - Quick search\n"
        "/upload - Upload resume\n"
        "/status - Bot health"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=MAIN_KB)
    context.user_data["flow"] = "ask_role"
    return ASK_ROLE


# ── Inline callback handler ────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query_obj = update.callback_query
    await query_obj.answer()

    data = query_obj.data or ""

    if data == "action:upload":
        await query_obj.message.reply_text(
            "Send your resume (PDF or DOCX):",
            reply_markup=ReplyKeyboardRemove(),
        )
        context.user_data["flow"] = "awaiting_resume"

    elif data == "action:skip":
        try:
            await query_obj.edit_message_text("No problem! Type your next search.")
        except Exception:
            pass
        context.user_data["flow"] = "ask_role"

    elif data.startswith("qs:"):
        parts = data.split(":", 2)
        if len(parts) == 3:
            _, role, location = parts
            try:
                await query_obj.edit_message_text(
                    f"Searching <b>{html.escape(role)}</b> in <b>{html.escape(location)}</b>...",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
            user_id = str(update.effective_user.id)
            await _do_search(query_obj.message, user_id, role, location)
            await query_obj.message.reply_text("What next?", reply_markup=MAIN_KB)
            context.user_data["flow"] = "ask_role"


# ── Error handler ──────────────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Unhandled error: {context.error}\n{traceback.format_exc()}")
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                format_error("Something went wrong. Please try again."),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


# ── Bot commands menu ──────────────────────────────────────────────────────────

async def post_init(application: Application) -> None:
    commands = [
        BotCommand("start", "Start - begin job search"),
        BotCommand("search", "Quick search - /search <role> in <city>"),
        BotCommand("upload", "Upload resume for better matching"),
        BotCommand("status", "Check bot status"),
        BotCommand("clearresume", "Clear saved resume"),
        BotCommand("help", "How it works"),
        BotCommand("cancel", "Cancel current action"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands registered.")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    if not TG_TOKEN:
        raise ValueError("TG_TOKEN not set in .env!")

    import sys
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add("bot.log", rotation="5 MB", level="DEBUG")

    logger.info("Starting Job Scraper Bot...")

    app = (
        Application.builder()
        .token(TG_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .post_init(post_init)
        .build()
    )

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
            MessageHandler(filters.Regex(r"^New Search$"), cmd_start),
        ],
        states={
            ASK_ROLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_role),
            ],
            ASK_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_location),
            ],
            AWAITING_RESUME: [
                MessageHandler(filters.Document.ALL, handle_resume_file),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("search", cmd_search),
            CommandHandler("upload", cmd_upload),
            CommandHandler("clearresume", cmd_clear_resume),
            CommandHandler("status", cmd_status),
            CommandHandler("help", cmd_help),
        ],
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_error_handler(error_handler)

    logger.info("Bot polling started.")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
