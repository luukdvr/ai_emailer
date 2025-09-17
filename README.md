# AI Emailer (Gmail)

A minimal cold emailer that:
- Sends emails via the Gmail API
- Keeps threads separated using Gmail Labels
- Generates emails from a simple template (no external AI required)
- Optional: Use OpenAI to generate personalized content

## Features
- Local config in `config.toml`
- Creates a Gmail Label if it doesn't exist and applies it to sent messages
- Rate limiting and retries

## Setup
1. Enable Gmail API and download OAuth credentials as `credentials.json` (Desktop app) and place it at the project root.
2. Create and fill `config.toml` (see below).
3. Install dependencies.

### Dependencies install (Windows cmd)
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On first run, a browser window will prompt you to authorize the app. A `token.json` will be created for subsequent runs.

## Config
Create `config.toml` at the project root:

```
[gmail]
from_name = "Your Name"
from_email = "you@gmail.com"
label = "AI-Emailer/Service-X"

[campaign]
service_name = "Webdesign"
value_prop = "We bouwen snelle, SEO-vriendelijke websites die leads genereren."
cta = "Zou je openstaan voor een korte call volgende week?"

[openai]
# Optional. Leave api_key empty to use the built-in template writer.
api_key = ""
model = "gpt-4o-mini"
```

## Run
Prepare a CSV with prospects at `data/prospects.csv` with headers:
```
company,contact_name,email,notes
Acme BV,Jan Jansen,jan@acme.nl,Heeft verouderde website
```

Then run:
```
.venv\Scripts\activate
python -m src.main --csv data/prospects.csv
```

## Notes
- This sends emails immediately. Consider using a test Gmail account first.
- Respect Gmail sending limits to avoid account issues.
- Threads: Each company gets a unique subject; the configured label is applied to all sent emails.
- Extend easily with follow-ups and batching.
