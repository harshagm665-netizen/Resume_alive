"""
functions/main.py — Firebase Cloud Functions entry points.
"""

from firebase_functions import https_fn
from firebase_admin import initialize_app

# Initialize Firebase Admin SDK
initialize_app()

@https_fn.on_request()
def health(req: https_fn.Request) -> https_fn.Response:
    """Basic health check endpoint to verify deployment."""
    return https_fn.Response("OK", status=200)

@https_fn.on_request()
def telegram_webhook(req: https_fn.Request) -> https_fn.Response:
    """Endpoint for Telegram bot webhooks."""
    from bot.handlers import handle_webhook
    import json
    
    try:
        update = req.get_json(silent=True)
        if update:
            handle_webhook(update)
        return https_fn.Response("OK", status=200)
    except Exception as e:
        print(f"Webhook error: {e}")
        return https_fn.Response("Error", status=500)
