import tweepy
import os
import pandas as pd
import requests
from datetime import datetime, timezone, timedelta
from io import StringIO
import re
import json
import time
from typing import List, Dict, Any, Tuple, Optional
from openai import OpenAI
import logging
from pathlib import Path
import random
import tempfile
import shutil

# ===============================
# LOGGING SETUP
# ===============================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===============================
# ENSURE LOG FILES EXIST
# ===============================
def ensure_file_exists(file_path: str, default_content: Any = None):
    path = Path(file_path)
    if not path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(default_content, (dict, list)):
                with path.open("w", encoding="utf-8") as f:
                    json.dump(default_content, f, ensure_ascii=False, indent=2)
            else:
                with path.open("w", encoding="utf-8") as f:
                    f.write(str(default_content or ""))
            logger.info(f"Created missing log file: {file_path}")
        except Exception as e:
            logger.error(f"Could not create file {file_path}: {e}")

# Logs
ensure_file_exists("logs/posted_log.json", [])
ensure_file_exists("logs/skipped_tweets.json", [])
ensure_file_exists("logs/dry_run_log.txt", "")
ensure_file_exists("logs/auth_cache.json", {"valid_until": None})

# Feed-specific storage (initialized with placeholder URLs from env)
feed1_url = os.getenv("RSS_FEED_1_URL", "https://rss.app/feeds/YOUR_FEED_1_ID.csv")
feed2_url = os.getenv("RSS_FEED_2_URL", "https://rss.app/feeds/YOUR_FEED_2_ID.csv")

ensure_file_exists("logs/feed1.json", {"url": feed1_url, "fetched_tweets": []})
ensure_file_exists("logs/feed2.json", {"url": feed2_url, "fetched_tweets": []})

# ===============================
# CONFIGURATION (ENV VARS ONLY)
# ===============================
consumer_key = os.getenv("TWITTER_CONSUMER_KEY")
consumer_secret = os.getenv("TWITTER_CONSUMER_SECRET")
access_token = os.getenv("TWITTER_ACCESS_TOKEN")
access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

# RSS Feed Configuration - customize with your own RSS feed URLs
FEEDS = [
    {"url": feed1_url, "limit": int(os.getenv("RSS_FEED_1_LIMIT", "10")), "file": "logs/feed1.json"},
    {"url": feed2_url, "limit": int(os.getenv("RSS_FEED_2_LIMIT", "10")), "file": "logs/feed2.json"},
]

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "meta-llama/llama-3.2-3b-instruct:free")
AI_RETRY_ATTEMPTS = int(os.getenv("AI_RETRY_ATTEMPTS", "3"))
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "150"))
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.7"))
BLOCK_RISK_THRESHOLD = float(os.getenv("BLOCK_RISK_THRESHOLD", "10.0"))  # Default 10.0 = disabled

# REMOVED: LOAD_FROM_STORED and ALWAYS_FETCH - now always fetches from RSS
ALWAYS_FETCH_RSS = True  # Hardcoded: always fetch from RSS since it doesn't hit X API

X_CHAR_LIMIT = 280
FILTER_CONFIG = {
    "blocked_keywords": [
        "we'll", "we will", "join us", "tomorrow", "register", "sign up",
        "link below", "spaces", "event", "set reminder", "8–9 pm",
        "tune in", "livestream", "discussion", "webinar", "follow for more",
        "today", "next week", "morning", "evening", "tonight"
    ],
    "personal_words": ["i ", "my ", "me ", "our ", "we ", "mine ", "myself"],
    "allow_symbols": r"[\w\s,.'\"!?-]",
    "thread_patterns": [r"^\(?\s*1[\./]\s*", r"part\s*\d+", r"🧵", r"thread"]
}

DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
POSTS_PER_RUN = int(os.getenv("POSTS_PER_RUN", "1"))
RATE_LIMIT_WAIT = int(os.getenv("RATE_LIMIT_WAIT", "180"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
SLEEP_BETWEEN_POSTS = int(os.getenv("SLEEP_BETWEEN_POSTS", "60"))
DAILY_POST_LIMIT = int(os.getenv("DAILY_POST_LIMIT", "17"))

# AI request limiting
MAX_AI_REQUESTS_PER_RUN = int(os.getenv("MAX_AI_REQUESTS_PER_RUN", "40"))

POSTED_LOG = "logs/posted_log.json"
SKIPPED_LOG = "logs/skipped_tweets.json"
DRY_RUN_LOG = "logs/dry_run_log.txt"
AUTH_CACHE = "logs/auth_cache.json"

# ===============================
# OPENROUTER CLIENT
# ===============================
client_ai: Optional[OpenAI] = None
if OPENROUTER_API_KEY:
    client_ai = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
    logger.info("AI client initialized.")
else:
    logger.warning("No OPENROUTER_API_KEY found. Skipping AI enhancement and risk assessment.")

# ===============================
# AUTH CACHE FUNCTIONS (24-HOUR DAILY RESET)
# ===============================
def is_auth_cached() -> bool:
    """Check if auth is cached and valid for today (EAT timezone)."""
    try:
        with Path(AUTH_CACHE).open("r", encoding="utf-8") as f:
            cache = json.load(f)
        
        # Parse the cached valid_until timestamp
        valid_until = datetime.fromisoformat(cache.get("valid_until", "1970-01-01T00:00:00"))
        
        # Get current time in EAT
        eat = timezone(timedelta(hours=3))
        now_eat = datetime.now(eat)
        
        # Check if cache is still valid (before expiry AND same day)
        is_valid = now_eat < valid_until
        
        # Also verify it's for today (prevents stale cache from previous days)
        cache_date = valid_until.astimezone(eat).date()
        today_date = now_eat.date()
        
        if is_valid and cache_date == today_date:
            logger.debug(f"Auth cache valid until {valid_until} (same day)")
            return True
        else:
            logger.debug(f"Auth cache expired or from different day")
            return False
            
    except Exception as e:
        logger.debug(f"Auth cache check failed: {e}")
        return False


def update_auth_cache():
    """Update auth cache valid until end of day (11:59 PM EAT)."""
    eat = timezone(timedelta(hours=3))
    now_eat = datetime.now(eat)
    
    # Set expiry to end of today (11:59:59 PM EAT)
    end_of_day = now_eat.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    cache = {
        "valid_until": end_of_day.isoformat(),
        "cached_at": now_eat.isoformat(),
        "auth_date": now_eat.date().isoformat()
    }
    
    try:
        with Path(AUTH_CACHE).open("w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        logger.info(f"✓ Auth cached until end of day: {end_of_day.strftime('%Y-%m-%d %H:%M:%S EAT')}")
    except Exception as e:
        logger.warning(f"Failed to update auth cache: {e}")


def clear_expired_auth_cache():
    """Clear auth cache if it's from a previous day (called at start of main)."""
    try:
        if not Path(AUTH_CACHE).exists():
            return
            
        with Path(AUTH_CACHE).open("r", encoding="utf-8") as f:
            cache = json.load(f)
        
        eat = timezone(timedelta(hours=3))
        now_eat = datetime.now(eat)
        today = now_eat.date()
        
        # Check if cache is from a previous day
        cache_date_str = cache.get("auth_date")
        if cache_date_str:
            cache_date = datetime.fromisoformat(cache_date_str).date() if isinstance(cache_date_str, str) else cache_date_str
            if cache_date < today:
                # Clear the cache for a fresh start
                logger.info(f"Clearing auth cache from previous day ({cache_date})")
                Path(AUTH_CACHE).unlink()
        
    except Exception as e:
        logger.debug(f"Error checking/clearing expired cache: {e}")

# ===============================
# FILTER CHECK
# ===============================
def is_allowed_tweet(text: str, filters: Dict[str, Any]) -> Tuple[bool, str]:
    lower_text = text.lower().strip()
    reasons = []

    for word in filters["blocked_keywords"]:
        if word in lower_text:
            reasons.append(f"blocked keyword: '{word}'")
            break

    for pattern in filters["thread_patterns"]:
        if re.search(pattern, lower_text, re.IGNORECASE):
            reasons.append(f"thread pattern: '{pattern}'")
            break

    if any(x in lower_text for x in ["http", "@", "#"]):
        reasons.append("contains link/mention/hashtag")

    if re.search(rf"[^{filters['allow_symbols']}]", text):
        reasons.append("contains disallowed symbols")

    for word in filters["personal_words"]:
        if re.search(rf"\b{re.escape(word)}\b", lower_text):
            reasons.append(f"personal word: '{word}'")
            break

    if lower_text.startswith("@"):
        reasons.append("reply-style tweet")

    if reasons:
        return False, "; ".join(reasons)
    return True, "Allowed"

# ===============================
# AI BLOCK RISK ASSESSMENT
# ===============================
def assess_block_risk(text: str) -> Tuple[float, str]:
    if not client_ai:
        return 0.0, "AI unavailable"

    prompt = (
        "You are an X policy expert. Analyze this post for potential violations of X rules (e.g., spam, duplicates, misleading content), "
        "high block risk from automated posting, or matches to these filters: blocked_keywords=['we'll', 'we will', 'join us', ... 'tonight'], "
        "personal_words=['i ', 'my ', ...], no links/hashtags/mentions, no threads, under 280 chars, no special symbols. "
        "Score risk 0-10 (0=safe, 10=high block risk). If >3, suggest a fix to reduce risk.\n\n"
        f"Post: {text}\n\n"
        "Response format: SCORE: X/10\nSUGGESTION: [brief suggestion or 'None']"
    )
    
    for attempt in range(AI_RETRY_ATTEMPTS):
        try:
            res = client_ai.chat.completions.create(
                model=AI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=AI_MAX_TOKENS,
                temperature=AI_TEMPERATURE,
            )
            response = res.choices[0].message.content.strip()
            score_match = re.search(r"SCORE:\s*(\d+(?:\.\d+)?)/10", response, re.IGNORECASE)
            score = float(score_match.group(1)) if score_match else 5.0
            sugg_match = re.search(r"SUGGESTION:\s*(.+)", response, re.IGNORECASE)
            suggestion = sugg_match.group(1).strip() if sugg_match else "None"
            logger.info(f"AI risk assessment: score={score}, suggestion='{suggestion}'")
            return score, suggestion
        except Exception as e:
            logger.warning(f"AI risk attempt {attempt + 1} failed: {e}")
            time.sleep(2 ** attempt)

    return 5.0, "Assessment failed"

# ===============================
# ROBUST LOGGING
# ===============================
def _atomic_json_append(log_file: str, entry: Dict[str, Any]):
    temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
    try:
        data = []
        if Path(log_file).exists():
            with Path(log_file).open("r", encoding="utf-8") as f:
                data = json.load(f)
        data.append(entry)
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.move(temp_path, log_file)
        logger.debug(f"Atomically appended to {log_file}")
    except Exception as e:
        os.close(temp_fd)
        os.unlink(temp_path)
        logger.error(f"Failed to append to {log_file}: {e}")
        raise

def log_posted_tweet(original: str, posted: str, tweet_id: Optional[str], ai_used: bool = False):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "original": original,
        "posted": posted,
        "tweet_id": tweet_id,
        "ai_used": ai_used,
    }
    try:
        _atomic_json_append(POSTED_LOG, entry)
        logger.info(f"Logged posted tweet: {posted[:50]}... (ID: {tweet_id})")
    except Exception as e:
        logger.error(f"Could not log posted tweet: {e}")

def log_skipped_tweet(tweet: str, reason: str):
    entry = {"timestamp": datetime.now().isoformat(), "tweet": tweet, "reason": reason}
    try:
        _atomic_json_append(SKIPPED_LOG, entry)
        logger.info(f"Logged skipped tweet: {tweet[:50]}... ({reason})")
    except Exception as e:
        logger.error(f"Could not log skipped tweet: {e}")

def get_all_processed_tweets() -> set:
    processed = set()
    try:
        if Path(POSTED_LOG).exists():
            with Path(POSTED_LOG).open("r", encoding="utf-8") as f:
                for d in json.load(f):
                    processed.add(d["original"])
        if Path(SKIPPED_LOG).exists():
            with Path(SKIPPED_LOG).open("r", encoding="utf-8") as f:
                data = json.load(f)
                eat = timezone(timedelta(hours=3))
                today = datetime.now(eat).date()
                for d in data:
                    ts = datetime.fromisoformat(d["timestamp"])
                    if ts.astimezone(eat).date() == today:
                        processed.add(d["tweet"])
    except Exception as e:
        logger.warning(f"Error reading processed logs: {e}")
    return processed

def get_today_posts_count() -> int:
    eat = timezone(timedelta(hours=3))
    today = datetime.now(eat).date()
    count = 0
    try:
        if Path(POSTED_LOG).exists():
            with Path(POSTED_LOG).open("r", encoding="utf-8") as f:
                data = json.load(f)
            for entry in data:
                ts = datetime.fromisoformat(entry["timestamp"])
                if ts.astimezone(eat).date() == today:
                    count += 1
    except Exception as e:
        logger.warning(f"Error counting today's posts: {e}")
    return count

# ===============================
# FEED STORAGE/LOAD FUNCTIONS
# ===============================
def clear_old_feed_data(feeds: List[Dict[str, Any]]):
    """Clear feed data from previous days, keeping only today's data."""
    eat = timezone(timedelta(hours=3))
    today = datetime.now(eat).date()
    for feed in feeds:
        file_path = feed["file"]
        if not Path(file_path).exists():
            continue
        try:
            with Path(file_path).open("r", encoding="utf-8") as f:
                data = json.load(f)
            data["fetched_tweets"] = [
                batch for batch in data["fetched_tweets"]
                if datetime.fromisoformat(batch["fetch_timestamp"]).astimezone(eat).date() == today
            ]
            with Path(file_path).open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Cleared old data from {file_path}; kept {len(data['fetched_tweets'])} batches for today")
        except Exception as e:
            logger.error(f"Failed to clear old data in {file_path}: {e}")

def store_feed_tweets(feed: Dict[str, Any], tweets: List[str]):
    """Store newly fetched tweets to feed file."""
    file_path = feed["file"]
    entry = {
        "fetch_timestamp": datetime.now().isoformat(),
        "tweets": [{"timestamp": datetime.now().isoformat(), "text": t, "ai_parsed": False} for t in tweets]
    }
    try:
        data = {"url": feed["url"], "fetched_tweets": []}
        if Path(file_path).exists():
            with Path(file_path).open("r", encoding="utf-8") as f:
                data = json.load(f)
        data["fetched_tweets"].append(entry)
        with Path(file_path).open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Stored {len(tweets)} tweets to {file_path}")
    except Exception as e:
        logger.error(f"Failed to store to {file_path}: {e}")

def update_ai_parsed_status(feed: Dict[str, Any], original_text: str, parsed: bool):
    """Update ai_parsed flag for a specific tweet."""
    file_path = feed["file"]
    try:
        with Path(file_path).open("r", encoding="utf-8") as f:
            data = json.load(f)
        updated = False
        for batch in data["fetched_tweets"]:
            for tweet in batch["tweets"]:
                if tweet["text"] == original_text and tweet["ai_parsed"] != parsed:
                    tweet["ai_parsed"] = parsed
                    updated = True
                    break
            if updated:
                break
        if updated:
            with Path(file_path).open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Updated ai_parsed for '{original_text[:30]}...' in {file_path}")
    except Exception as e:
        logger.warning(f"Failed to update ai_parsed in {file_path}: {e}")

def load_stored_tweets(feeds: List[Dict[str, Any]]) -> List[Tuple[str, bool, Dict[str, Any]]]:
    """Load all stored tweets from today across all feeds."""
    all_tweets = []
    seen_texts = set()
    eat = timezone(timedelta(hours=3))
    today = datetime.now(eat).date()
    for feed in feeds:
        file_path = feed["file"]
        if not Path(file_path).exists():
            continue
        try:
            with Path(file_path).open("r", encoding="utf-8") as f:
                data = json.load(f)
            for batch in data["fetched_tweets"]:
                fetch_ts = datetime.fromisoformat(batch["fetch_timestamp"])
                if fetch_ts.astimezone(eat).date() == today:
                    for tweet in batch["tweets"]:
                        text = tweet["text"]
                        if text not in seen_texts:
                            all_tweets.append((text, tweet["ai_parsed"], feed))
                            seen_texts.add(text)
        except Exception as e:
            logger.warning(f"Error loading {file_path}: {e}")
    logger.info(f"Loaded {len(all_tweets)} unique stored tweets from feeds")
    return all_tweets

# ===============================
# AI ENHANCEMENT
# ===============================
def enhance_tweet_with_ai(text: str, feed: Dict[str, Any]) -> Tuple[str, bool]:
    if not client_ai:
        logger.warning("AI unavailable; truncating original.")
        formatted = truncate_and_format(text)
        update_ai_parsed_status(feed, text, True)
        return formatted, False

    prompt = (
        "You are a professional social media manager. Rewrite this post to be clear, concise, and engaging. "
        "MUST be UNDER 250 CHARACTERS. Summarize if needed. No links, hashtags, emojis. "
        "Avoid first-person pronouns such as I, we, us, our, my, me. "
        "Avoid promotional or event-related words like join, host, event, today, tomorrow. "
        "End with a period. Format: One sentence per line with line breaks.\n\n"
        f"Original (do not exceed 250 chars): {text}\n\n"
        "Rewritten (count chars, <=249): "
    )
    
    for attempt in range(AI_RETRY_ATTEMPTS):
        try:
            res = client_ai.chat.completions.create(
                model=AI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=AI_MAX_TOKENS,
                temperature=AI_TEMPERATURE,
            )
            enhanced = res.choices[0].message.content.strip()
            if len(enhanced) < X_CHAR_LIMIT and len(enhanced) > 10 and enhanced.lower() != text.lower():
                update_ai_parsed_status(feed, text, True)
                logger.info(f"AI enhancement successful on attempt {attempt + 1} (len: {len(enhanced)}).")
                return enhanced, True
            else:
                logger.warning(f"AI output invalid on attempt {attempt + 1}: len={len(enhanced)}")
        except Exception as e:
            logger.warning(f"AI attempt {attempt + 1} failed: {e}")
            time.sleep(2 ** attempt)

    logger.info("AI failed; falling back to truncation.")
    formatted = truncate_and_format(text)
    update_ai_parsed_status(feed, text, True)
    return formatted, False

def truncate_and_format(text: str) -> str:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    formatted = []
    current_len = 0
    for sent in sentences:
        sent_len = len(sent) + 1  # +1 for newline
        if current_len + sent_len > X_CHAR_LIMIT - 3:
            break
        formatted.append(sent)
        current_len += sent_len
    result = '\n'.join(formatted)
    if len(result) > X_CHAR_LIMIT - 3:
        result = result[:X_CHAR_LIMIT - 3] + "..."
    return result

# ===============================
# FETCH RSS
# ===============================
def get_today_tweets(feed_url: str, limit: int) -> List[str]:
    """Fetch today's tweets from RSS feed URL."""
    try:
        logger.info(f"Fetching from RSS: {feed_url}")
        r = requests.get(feed_url, timeout=30)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
        
        if df.empty:
            logger.warning(f"RSS feed returned empty dataframe: {feed_url}")
            return []
        
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"])
        
        eat = timezone(timedelta(hours=3))
        today = datetime.now(eat).date()
        df_today = df[df["Date"].dt.date == today]
        
        tweets = df_today["Title"].dropna().head(limit).tolist()
        logger.info(f"✓ Fetched {len(tweets)} tweets from {feed_url} for today ({today})")
        return tweets
    except Exception as e:
        logger.error(f"RSS fetch error for {feed_url}: {e}")
        return []

# ===============================
# POST TWEET
# ===============================
def post_tweet(client_v2, text: str, dry_run: bool = False) -> Optional[str]:
    if dry_run:
        logger.info(f"[DRY RUN] Would post: {text}")
        with Path(DRY_RUN_LOG).open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()}: {text}\n")
        return "dry-run"

    max_retries = MAX_RETRIES
    wait_seconds = RATE_LIMIT_WAIT

    for attempt in range(max_retries):
        try:
            r = client_v2.create_tweet(text=text)
            tweet_id = r.data['id']
            logger.info(f"Posted tweet ID: {tweet_id}")
            return tweet_id
        except tweepy.TooManyRequests as e:
            reset_time = e.response.headers.get('x-rate-limit-reset', 0)
            wait = int(reset_time) - int(time.time()) + 10 if reset_time else wait_seconds
            logger.warning(f"429 Too Many Requests. Waiting {wait} seconds. Attempt {attempt+1}/{max_retries}")
            time.sleep(wait)
        except Exception as e:
            logger.error(f"Tweet post failed on attempt {attempt+1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(10 * (attempt + 1))
    logger.error("Max retries exceeded for posting.")
    return None

# ===============================
# MAIN
# ===============================
def main():
    logger.info("=" * 60)
    logger.info("Starting RSS X Bot - OPTIMIZED AI USAGE")
    logger.info("RSS fetching does NOT count against X API rate limits")
    logger.info(f"AI Request Limit: {MAX_AI_REQUESTS_PER_RUN} per run")
    logger.info("=" * 60)
    
    # Clear any expired auth cache from previous days
    clear_expired_auth_cache()

    if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
        logger.error("Missing X API keys.")
        return

    # Create client
    try:
        client_v2 = tweepy.Client(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )
        logger.info("X client created.")
    except Exception as e:
        logger.error(f"X client creation failed: {e}")
        return

    today_posts = get_today_posts_count()
    if today_posts >= DAILY_POST_LIMIT:
        logger.info(f"Daily post limit ({DAILY_POST_LIMIT}) reached today ({today_posts} posts). Skipping run.")
        return

    # Clear old feed data from previous days
    clear_old_feed_data(FEEDS)

    eat = timezone(timedelta(hours=3))
    today = datetime.now(eat).date()

    # ALWAYS FETCH FROM RSS (doesn't hit X API)
    logger.info("🔄 Fetching fresh tweets from RSS feeds (no API limits)...")
    all_fetched_tweets = []
    for feed in FEEDS:
        tweets = get_today_tweets(feed["url"], feed["limit"])
        if tweets:
            store_feed_tweets(feed, tweets)
            all_fetched_tweets.extend(tweets)
            logger.info(f"  └─ Stored {len(tweets)} tweets from: {feed['url']}")
        else:
            logger.warning(f"  └─ No tweets found for today from: {feed['url']}")
    
    if not all_fetched_tweets:
        logger.info("❌ No new tweets fetched from any RSS feed today. Check feed sources.")
        return
    
    logger.info(f"✓ Total fetched: {len(all_fetched_tweets)} tweets from all feeds")

    # Reload stored tweets after fetching
    temp_tweets = load_stored_tweets(FEEDS)
    logger.info(f"📋 Total unique tweets in storage: {len(temp_tweets)}")

    # Filter to only unprocessed tweets
    processed = get_all_processed_tweets()
    unprocessed = [t for t in temp_tweets if t[0] not in processed]

    if not unprocessed:
        logger.info("✅ All fetched tweets have already been processed.")
        return

    logger.info(f"🔍 Found {len(unprocessed)} unprocessed tweets to evaluate")

    # Pre-filter tweets BEFORE AI processing (saves AI calls!)
    logger.info("🔍 Pre-filtering tweets before AI processing...")
    unparsed_first = sorted(unprocessed, key=lambda x: x[1])
    prioritized_unprocessed = [item for item in unparsed_first]
    random.shuffle(prioritized_unprocessed)

    filtered_candidates = []
    for idx, item in enumerate(prioritized_unprocessed, 1):
        tweet, ai_parsed, feed = item
        logger.debug(f"  Pre-filtering {idx}/{len(prioritized_unprocessed)}: {tweet[:50]}...")
        
        # STEP 1: Length check and truncation BEFORE AI
        if len(tweet) > X_CHAR_LIMIT:
            truncated = truncate_and_format(tweet)
            if len(truncated) > X_CHAR_LIMIT:
                log_skipped_tweet(tweet, f"too long even after truncation ({len(truncated)} chars)")
                continue
            tweet = truncated
        
        # STEP 2: Basic filter check on original text (NO AI yet)
        allowed, reason = is_allowed_tweet(tweet, FILTER_CONFIG)
        if not allowed:
            log_skipped_tweet(tweet, reason)
            continue
        
        # STEP 3: Passed pre-filtering, add to AI processing queue
        filtered_candidates.append((tweet, ai_parsed, feed))

    logger.info(f"✅ {len(filtered_candidates)} tweets passed pre-filtering (out of {len(prioritized_unprocessed)})")

    if not filtered_candidates:
        logger.info("❌ No tweets passed pre-filtering.")
        return

    # Now process with AI (only the good candidates)
    postable_tweets = []
    ai_requests_used = 0
    logger.info(f"🤖 Processing tweets through AI (limit: {MAX_AI_REQUESTS_PER_RUN} requests)...")
    
    for idx, (tweet, ai_parsed, feed) in enumerate(filtered_candidates, 1):
        # Check if we've hit AI request limit
        if ai_requests_used >= MAX_AI_REQUESTS_PER_RUN:
            logger.warning(f"⚠️ Hit AI request limit ({MAX_AI_REQUESTS_PER_RUN}), stopping AI processing")
            logger.info(f"   Remaining {len(filtered_candidates) - idx + 1} tweets will be processed on next run")
            break
        
        logger.debug(f"  AI processing {idx}/{len(filtered_candidates)}: {tweet[:50]}...")
        
        # AI enhancement
        final_text, ai_used = enhance_tweet_with_ai(tweet, feed)
        ai_requests_used += 1  # Count the enhancement call
        
        # Double-check length after AI
        if len(final_text) > X_CHAR_LIMIT:
            reason = f"still too long after enhancement ({len(final_text)} > {X_CHAR_LIMIT})"
            log_skipped_tweet(final_text, reason)
            update_ai_parsed_status(feed, tweet, True)
            continue

        # Re-check filters after AI (in case AI added bad words)
        allowed, reason = is_allowed_tweet(final_text, FILTER_CONFIG)
        if not allowed:
            log_skipped_tweet(final_text, f"failed filter after AI: {reason}")
            update_ai_parsed_status(feed, tweet, True)
            continue

        # Risk assessment (only if not disabled by high threshold)
        if BLOCK_RISK_THRESHOLD < 10.0 and ai_requests_used < MAX_AI_REQUESTS_PER_RUN:
            risk_score, suggestion = assess_block_risk(final_text)
            ai_requests_used += 1  # Count the risk assessment call
            if risk_score > BLOCK_RISK_THRESHOLD:
                skip_reason = f"High block risk (score: {risk_score}/10); suggestion: {suggestion}"
                log_skipped_tweet(final_text, skip_reason)
                update_ai_parsed_status(feed, tweet, True)
                continue
        else:
            logger.debug(f"  Skipping risk assessment (threshold: {BLOCK_RISK_THRESHOLD})")

        postable_tweets.append((final_text, ai_used, tweet, feed))
        logger.info(f"  ✓ Tweet {idx} ready to post (AI requests used: {ai_requests_used}/{MAX_AI_REQUESTS_PER_RUN})")

    logger.info(f"📊 AI Usage Summary: {ai_requests_used}/{MAX_AI_REQUESTS_PER_RUN} requests used")

    if not postable_tweets:
        logger.info("❌ No postable tweets after applying filters and AI enhancement.")
        return

    max_posts = min(POSTS_PER_RUN, DAILY_POST_LIMIT - today_posts, len(postable_tweets))
    logger.info(f"📤 Preparing to post up to {max_posts} tweets (from {len(postable_tweets)} candidates)")

    # Single auth check after all parsing (with cache)
    if is_auth_cached():
        logger.info("✓ Using cached auth (valid until end of day).")
    else:
        logger.info("🔐 Authenticating with X API...")
        try:
            client_v2.get_me()
            update_auth_cache()
            logger.info("✓ X auth successful; cached until end of day.")
        except tweepy.TooManyRequests as e:
            reset_time = e.response.headers.get('x-rate-limit-reset', 0)
            wait = int(reset_time) - int(time.time()) + 10 if reset_time else RATE_LIMIT_WAIT
            logger.warning(f"⚠️ 429 on auth. Waiting {wait}s then skipping posts.")
            time.sleep(wait)
            logger.error("❌ Auth failed; skipping all posts.")
            return
        except Exception as e:
            logger.error(f"❌ Auth failed: {e}; skipping all posts.")
            return

    # Now post (no more auth checks)
    posts_attempted = 0
    logger.info("🚀 Starting posting sequence...")
    for idx, (final_text, ai_used, tweet, feed) in enumerate(postable_tweets[:max_posts], 1):
        logger.info(f"📝 Posting tweet {idx}/{max_posts}...")
        tweet_id = post_tweet(client_v2, final_text, dry_run=DRY_RUN)
        if tweet_id and tweet_id != "dry-run":
            log_posted_tweet(tweet, final_text, tweet_id, ai_used=ai_used)
            posts_attempted += 1
            logger.info(f"✅ Successfully posted tweet {idx}/{max_posts} (ID: {tweet_id})")
            if posts_attempted < max_posts:
                logger.info(f"⏳ Sleeping {SLEEP_BETWEEN_POSTS}s before next post...")
                time.sleep(SLEEP_BETWEEN_POSTS)
        elif tweet_id == "dry-run":
            log_posted_tweet(tweet, final_text, "dry-run", ai_used=ai_used)
            posts_attempted += 1
            logger.info(f"✅ [DRY RUN] Logged tweet {idx}/{max_posts}")
        else:
            logger.error(f"❌ Failed to post tweet {idx}/{max_posts}; skipping log.")

    logger.info("=" * 60)
    logger.info(f"✅ Run complete!")
    logger.info(f"   AI requests used: {ai_requests_used}/{MAX_AI_REQUESTS_PER_RUN}")
    logger.info(f"   Posts attempted: {posts_attempted}/{max_posts}")
    logger.info(f"   Total today: {today_posts + posts_attempted}/{DAILY_POST_LIMIT}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()