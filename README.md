# 🤖 RSS X Bot (formerly Twitter)

An intelligent, automated X bot that fetches content from RSS feeds, enhances it with AI, applies smart filters, and posts high-quality posts while respecting rate limits.

## ✨ Features

### Core Functionality
- **RSS Feed Integration**: Fetches posts from multiple RSS feed sources automatically
- **AI-Powered Enhancement**: Uses OpenRouter AI to rewrite and improve post quality
- **Smart Filtering**: Multi-layer filtering system to ensure post quality and compliance
- **Rate Limit Management**: Intelligent handling of both X API and OpenRouter API limits
- **Timezone Support**: Built-in East Africa Time (EAT) timezone handling
- **Duplicate Prevention**: Tracks processed posts to avoid reposts
- **Daily Post Limits**: Configurable limits to prevent spam behavior

### Advanced Features
- **Auth Caching**: Authenticates once per day to minimize API calls
- **Risk Assessment**: Optional AI-powered risk scoring for policy compliance
- **Atomic Logging**: Crash-resistant JSON logging with atomic file operations
- **Dry Run Mode**: Test the bot without posting to X
- **Feed-Specific Tracking**: Maintains separate storage for each RSS feed
- **Pre-filtering**: Filters posts before AI processing to save API credits

## 📋 Prerequisites

- Python 3.8+
- X Developer Account with API keys (formerly Twitter)
- OpenRouter API account (free tier available)
- RSS feed URLs (CSV format from rss.app or similar)

## 🚀 Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd twitter-bot
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install tweepy pandas requests openai python-dotenv
```

3. **Configure environment variables**

Copy the example file and fill in your credentials:
```bash
cp .env.example .env
```

Then edit `.env` with your actual values. See the [Configuration](#configuration) section for details on each variable.

**Alternative**: Export variables directly (not recommended for production):
```bash
export TWITTER_CONSUMER_KEY="your_key"
export RSS_FEED_1_URL="https://rss.app/feeds/YOUR_FEED_ID.csv"
# ... etc
```
```bash
# X API credentials (formerly Twitter)
TWITTER_CONSUMER_KEY=your_consumer_key
TWITTER_CONSUMER_SECRET=your_consumer_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret

# RSS Feed URLs
RSS_FEED_1_URL=https://rss.app/feeds/YOUR_FEED_1_ID.csv
RSS_FEED_2_URL=https://rss.app/feeds/YOUR_FEED_2_ID.csv
RSS_FEED_1_LIMIT=10
RSS_FEED_2_LIMIT=10

# OpenRouter AI configuration
OPENROUTER_API_KEY=your_openrouter_key
AI_MODEL=meta-llama/llama-3.2-3b-instruct:free

# Bot configuration
DAILY_POST_LIMIT=17
POSTS_PER_RUN=1
DRY_RUN=false
```

Or export them directly:
```bash
# X API credentials (formerly Twitter)
export TWITTER_CONSUMER_KEY="your_consumer_key"
export TWITTER_CONSUMER_SECRET="your_consumer_secret"
export TWITTER_ACCESS_TOKEN="your_access_token"
export TWITTER_ACCESS_TOKEN_SECRET="your_access_token_secret"

# RSS Feed URLs
export RSS_FEED_1_URL="https://rss.app/feeds/YOUR_FEED_1_ID.csv"
export RSS_FEED_2_URL="https://rss.app/feeds/YOUR_FEED_2_ID.csv"

# OpenRouter AI configuration
export OPENROUTER_API_KEY="your_openrouter_key"
export AI_MODEL="meta-llama/llama-3.2-3b-instruct:free"

# Bot configuration
export DAILY_POST_LIMIT="17"
export POSTS_PER_RUN="1"
export DRY_RUN="false"
```

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TWITTER_CONSUMER_KEY` | Required | X API consumer key |
| `TWITTER_CONSUMER_SECRET` | Required | X API consumer secret |
| `TWITTER_ACCESS_TOKEN` | Required | X API access token |
| `TWITTER_ACCESS_TOKEN_SECRET` | Required | X API access token secret |
| `OPENROUTER_API_KEY` | Required | OpenRouter API key |
| `AI_MODEL` | `meta-llama/llama-3.2-3b-instruct:free` | AI model to use |
| `AI_RETRY_ATTEMPTS` | `3` | Number of retry attempts for AI calls |
| `AI_MAX_TOKENS` | `150` | Maximum tokens for AI responses |
| `AI_TEMPERATURE` | `0.7` | AI creativity (0.0-1.0) |
| `BLOCK_RISK_THRESHOLD` | `10.0` | Risk score threshold (10.0 = disabled) |
| `MAX_AI_REQUESTS_PER_RUN` | `40` | Maximum AI requests per run |
| `RSS_FEED_1_URL` | Required | First RSS feed URL (CSV format) |
| `RSS_FEED_2_URL` | Required | Second RSS feed URL (CSV format) |
| `RSS_FEED_1_LIMIT` | `10` | Max posts to fetch from feed 1 |
| `RSS_FEED_2_LIMIT` | `10` | Max posts to fetch from feed 2 |
| `DRY_RUN` | `false` | Test mode (doesn't post to X) |
| `POSTS_PER_RUN` | `1` | Number of posts per execution |
| `DAILY_POST_LIMIT` | `17` | Maximum posts per day |
| `SLEEP_BETWEEN_POSTS` | `60` | Seconds to wait between posts |
| `RATE_LIMIT_WAIT` | `180` | Seconds to wait on rate limit |
| `MAX_RETRIES` | `3` | Max retries for posting |

### RSS Feed Configuration

Edit the environment variables to add your RSS sources:

```bash
# RSS Feed URLs (get these from rss.app or similar services)
export RSS_FEED_1_URL="https://rss.app/feeds/YOUR_FEED_1_ID.csv"
export RSS_FEED_2_URL="https://rss.app/feeds/YOUR_FEED_2_ID.csv"

# Optional: Set different limits per feed
export RSS_FEED_1_LIMIT="10"
export RSS_FEED_2_LIMIT="10"
```

Or add them to your `.env` file:
```bash
RSS_FEED_1_URL=https://rss.app/feeds/YOUR_FEED_1_ID.csv
RSS_FEED_2_URL=https://rss.app/feeds/YOUR_FEED_2_ID.csv
RSS_FEED_1_LIMIT=10
RSS_FEED_2_LIMIT=10
```

**Note**: The bot supports CSV-format RSS feeds. You can create these at [rss.app](https://rss.app/) by converting X accounts or hashtags to RSS feeds.

### Content Filters

The bot automatically filters out:

**Blocked Keywords:**
- Promotional terms: "join us", "register", "sign up", "link below"
- Event-related: "tomorrow", "today", "tonight", "tune in", "livestream"
- Time references: "8–9 pm", "morning", "evening", "next week"

**Content Rules:**
- No first-person pronouns (I, we, our, my, me)
- No links, mentions (@), or hashtags (#)
- No thread indicators (1/, 🧵, "thread")
- No special symbols (only alphanumeric and basic punctuation)
- Maximum 280 characters

## 📁 Project Structure

```
x-bot/
├── bot.py                 # Main bot script
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── .gitignore            # Git ignore file
├── logs/                  # Generated logs directory (gitignored)
│   ├── posted_log.json    # Record of posted content
│   ├── skipped_tweets.json # Record of filtered posts
│   ├── dry_run_log.txt    # Dry run test logs
│   ├── auth_cache.json    # Authentication cache
│   ├── feed1.json         # Feed 1 storage
│   └── feed2.json         # Feed 2 storage
├── bot.log               # Application logs (gitignored)
├── LICENSE               # License file
└── README.md             # This file
```

## 🎯 Usage

### Basic Usage

Run the bot once:
```bash
python bot.py
```

### Dry Run Mode (Testing)

Test without posting to X:
```bash
DRY_RUN=true python bot.py
```

### Scheduled Execution

Set up a cron job for automated posting:

```bash
# Edit crontab
crontab -e

# Run every 2 hours between 6 AM and 10 PM
0 6-22/2 * * * cd /path/to/bot && /usr/bin/python3 bot.py >> logs/cron.log 2>&1
```

### GitHub Actions (Optional)

Create `.github/workflows/bot.yml`:

```yaml
name: X Bot

on:
  schedule:
    - cron: '0 */2 * * *'  # Every 2 hours
  workflow_dispatch:  # Manual trigger

jobs:
  run-bot:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run bot
        env:
          TWITTER_CONSUMER_KEY: ${{ secrets.TWITTER_CONSUMER_KEY }}
          TWITTER_CONSUMER_SECRET: ${{ secrets.TWITTER_CONSUMER_SECRET }}
          TWITTER_ACCESS_TOKEN: ${{ secrets.TWITTER_ACCESS_TOKEN }}
          TWITTER_ACCESS_TOKEN_SECRET: ${{ secrets.TWITTER_ACCESS_TOKEN_SECRET }}
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
        run: python x-bot.py
```

## 🔍 How It Works

### Workflow

1. **Initialization**
   - Clears expired caches from previous days
   - Creates necessary log files
   - Initializes Twitter and AI clients

2. **RSS Fetching**
   - Fetches today's posts from all configured RSS feeds
   - Stores posts in feed-specific JSON files
   - No API rate limits (doesn't hit X API)

3. **Pre-filtering**
   - Checks post length
   - Applies keyword and pattern filters
   - Removes duplicates
   - Only posts that pass move to AI processing

4. **AI Enhancement** (if OpenRouter key provided)
   - Rewrites posts for clarity and engagement
   - Ensures compliance with character limits
   - Avoids promotional language
   - Tracks AI request usage

5. **Risk Assessment** (optional)
   - AI-powered policy compliance check
   - Scores risk from 0-10
   - Suggests improvements for high-risk content

6. **Authentication** (once per day)
   - Authenticates with X API
   - Caches credentials until midnight EAT
   - Minimizes API calls

7. **Posting**
   - Posts content with configured delays
   - Handles rate limits gracefully
   - Logs all posted and skipped content
   - Respects daily post limits

### AI Request Optimization

**For 17 posts/day:**
- With risk assessment disabled: ~17 AI requests/day
- With risk assessment enabled: ~34 AI requests/day
- Free tier limit: 50 requests/day ✅

**Optimization strategies:**
- Pre-filters posts before AI processing
- Tracks AI request usage per run
- Stops processing when approaching limits
- Processes remaining posts on next run

## 📊 Monitoring

### Check Posted Tweets
```bash
cat logs/posted_log.json | jq '.[-5:]'  # Last 5 posts
```

### Check Skipped Posts
```bash
cat logs/skipped_tweets.json | jq '.[-10:]'  # Last 10 skips
```

### View Today's Activity
```bash
grep "$(date +%Y-%m-%d)" bot.log
```

### Count Today's Posts
```bash
cat logs/posted_log.json | jq '[.[] | select(.timestamp | startswith("'$(date +%Y-%m-%d)'"))] | length'
```

## 🐛 Troubleshooting

### Issue: "Rate limit exceeded: free-models-per-day"

**Solution 1**: Disable risk assessment
```bash
export BLOCK_RISK_THRESHOLD="10.0"
```

**Solution 2**: Add $10 to OpenRouter account
- Unlocks 1,000 free requests/day
- Still uses free models

**Solution 3**: Wait until next day (resets at midnight UTC)

### Issue: "429 Too Many Requests" (X API)

The bot automatically handles this by:
- Waiting for rate limit reset
- Retrying with exponential backoff
- Caching authentication for 24 hours

### Issue: No posts being published

**Check:**
1. Are there posts in the RSS feed for today?
2. Are posts passing filters? Check `logs/skipped_tweets.json`
3. Have you hit the daily post limit?
4. Is `DRY_RUN` set to `true`?

**Debug:**
```bash
# Run in dry run mode to see what would be posted
DRY_RUN=true python bot.py

# Check the dry run log
cat logs/dry_run_log.txt
```

### Issue: AI enhancement not working

**Check:**
1. Is `OPENROUTER_API_KEY` set?
2. Do you have remaining free requests?
3. Check `bot.log` for AI errors

**Fallback:** Bot automatically falls back to truncation if AI fails

## 🔒 Security Best Practices

1. **Never commit API keys** to version control
   - Always use `.env` files (included in `.gitignore`)
   - Use environment variables for all secrets
   - Never share your `.env` file
   
2. **Protect your logs directory**
   - Logs contain post history and may include sensitive data
   - The `.gitignore` file excludes logs from git
   - Regularly review and clean old logs
   
3. **Rotate API keys** regularly
   - Change keys if you suspect they're compromised
   - Use X Developer Portal to regenerate keys
   
4. **Monitor bot activity** for unusual behavior
   - Check logs daily
   - Review posted and skipped content
   - Watch for policy violations
   
5. **Set reasonable rate limits** to avoid suspension
   - Don't exceed 17 posts/day
   - Maintain natural posting intervals
   
6. **Review logs regularly** for errors or policy violations
   - Check `bot.log` for errors
   - Review `skipped_tweets.json` for filtered content

## 📈 Rate Limit Summary

| Service | Free Tier | Bot Usage | Status |
|---------|-----------|-----------|--------|
| OpenRouter | 50 req/day | ~17-34 req/day | ✅ Safe |
| X Auth | 15 req/15min | 1 req/day (cached) | ✅ Safe |
| X Posting | 300 req/3hrs | 17 req/day | ✅ Safe |
| RSS Fetching | Unlimited | Unlimited | ✅ No limits |

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly (use dry run mode)
5. Submit a pull request

## 📝 License

[MIT License](LICENSE)

## ⚠️ Disclaimer

This bot is for educational and automation purposes. Always:
- Comply with X's Terms of Service
- Follow X's Automation Rules
- Respect content ownership and attribution
- Monitor your bot's activity regularly
- Use responsibly and ethically

## 🆘 Support

### Self-Help Resources
- **Issues**: Open an issue on GitHub
- **Questions**: Check existing issues or create a new one
- **X API**: [X Developer Portal](https://developer.x.com/) (formerly Twitter)
- **OpenRouter**: [OpenRouter Documentation](https://openrouter.ai/docs)
- **RSS Feeds**: [rss.app Documentation](https://rss.app/docs)

### Professional Setup Assistance

Need help setting up the bot? **Professional setup and configuration services are available for a fee.**

For inquiries about:
- Initial bot setup and configuration
- Custom RSS feed integration
- Deployment assistance (cron jobs, GitHub Actions, cloud hosting)
- Troubleshooting and optimization
- Custom feature development

**Contact**: [e@kipmyk.co.ke](mailto:e@kipmyk.co.ke)

*Note: Basic support through GitHub issues is free. Paid services cover hands-on setup, customization, and deployment.*

## 🎉 Acknowledgments

- [Tweepy](https://www.tweepy.org/) - Twitter API library
- [OpenRouter](https://openrouter.ai/) - AI API platform
- [rss.app](https://rss.app/) - RSS feed generation

---

**Made with ❤️ for automated, intelligent social media posting**
