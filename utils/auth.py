import hmac
import hashlib
import json
import time
from typing import Tuple, Dict, Any
from urllib.parse import parse_qsl

def verify_telegram_init_data(init_data: str, bot_token: str, expiry_seconds: int = 86400) -> Tuple[bool, Dict[str, Any]]:
    """
    Cryptographically verifies that the initData received from the Telegram Mini App
    is authentic and hasn't tampered with or expired.
    
    Args:
        init_data: The raw query string passed by the Telegram client.
        bot_token: The bot's HTTP token from @BotFather.
        expiry_seconds: Expiration delta (default: 24 hours).
        
    Returns:
        A tuple of (is_valid, user_data_dict).
    """
    try:
        parsed_data = dict(parse_qsl(init_data))
    except Exception:
        return False, {}

    received_hash = parsed_data.pop("hash", None)
    if not received_hash:
        return False, {}

    # Check expiration (auth_date is in Unix timestamp seconds)
    auth_date_str = parsed_data.get("auth_date")
    if not auth_date_str:
        return False, {}
    try:
        auth_date = int(auth_date_str)
        if time.time() - auth_date > expiry_seconds:
            return False, {}
    except ValueError:
        return False, {}

    # Build check string by sorting keys alphabetically
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))

    # Calculate secret key: HMAC-SHA256 of bot_token with salt b"WebAppData"
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    
    # Calculate hash signature
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if calculated_hash != received_hash:
        return False, {}

    # Extract user JSON
    user_str = parsed_data.get("user")
    if not user_str:
        return False, {}

    try:
        user_data = json.loads(user_str)
        return True, user_data
    except Exception:
        return False, {}
