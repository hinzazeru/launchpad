# Email Notification Setup Guide

This guide explains how to set up Gmail email notifications for job matches using OAuth 2.0 authentication.

## Overview

The LinkedIn Job Matcher can automatically send you email notifications when it finds jobs that match your resume above a certain threshold (default: 70%). Notifications include:

- Match score breakdown (skills + experience)
- Matching skills from your resume
- Skill gaps to develop
- Direct link to the job posting
- Professional HTML formatting

## Prerequisites

- A Gmail account
- Access to Google Cloud Console
- Python environment with dependencies installed

## Step 1: Google Cloud Console Setup

### 1.1 Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter project name (e.g., "LinkedIn Job Matcher")
4. Click "Create"

### 1.2 Enable Gmail API

1. In your project, go to "APIs & Services" → "Library"
2. Search for "Gmail API"
3. Click on "Gmail API"
4. Click "Enable"

### 1.3 Configure OAuth Consent Screen

1. Go to "APIs & Services" → "OAuth consent screen"
2. Select "External" (unless you have a Google Workspace account)
3. Click "Create"
4. Fill in required fields:
   - App name: "LinkedIn Job Matcher"
   - User support email: Your email
   - Developer contact: Your email
5. Click "Save and Continue"
6. On "Scopes" page, click "Add or Remove Scopes"
7. Search for "Gmail API" and select:
   - `.../auth/gmail.send` (Send email on your behalf)
8. Click "Update" → "Save and Continue"
9. On "Test users" page, add your Gmail address
10. Click "Save and Continue"

### 1.4 Create OAuth 2.0 Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Application type: **Desktop app**
4. Name: "LinkedIn Job Matcher Desktop"
5. Click "Create"
6. Click "Download JSON" to download the credentials file
7. Save the file as `credentials.json` in your project root directory

## Step 2: Update Configuration

Edit your `config.yaml` file:

```yaml
email:
  enabled: true  # Enable email notifications
  service: "gmail"
  credentials_path: "credentials.json"  # Path to downloaded credentials
  token_path: "token.json"  # OAuth token will be saved here

  # Email settings
  from_address: "your-email@gmail.com"  # Your Gmail address
  to_address: "your-email@gmail.com"    # Where to send notifications
  subject_template: "New Job Match: {job_title} at {company}"

  # Notification threshold
  notify_min_score: 0.7  # Only send emails for matches >= 70%
```

## Step 3: Test Email Notifications

Run the test script to verify setup:

```bash
python scripts/test_email_notifications.py
```

The script will:
1. Check if email is enabled in config
2. Authenticate with Gmail (opens browser first time)
3. Create a sample job match
4. Show email preview
5. Ask if you want to send a test email
6. Optionally test batch notifications

### First-Time Authentication

The first time you run the script:
1. A browser window will open
2. Log in to your Gmail account
3. Click "Continue" when warned about unverified app
4. Grant permission to send emails
5. The browser will show "The authentication flow has completed"
6. A `token.json` file will be created locally
7. Future runs won't require browser authentication

## Step 4: Integrate with Job Matching

### Send notifications during matching:

```python
from src.database.db import SessionLocal, init_db
from src.resume.storage import get_resume_by_id
from src.database import crud
from src.matching.engine import JobMatcher
from src.notifications.email_notifier import EmailNotifier

# Initialize
init_db()
db = SessionLocal()

# Get resume and jobs
resume = get_resume_by_id(db, resume_id=1)
jobs = crud.get_job_postings(db)

# Match jobs
matcher = JobMatcher()
matches = matcher.match_jobs(resume, jobs, min_score=0.0)

# Send notifications for high matches
notifier = EmailNotifier()
if notifier.enabled:
    notifier.authenticate()
    sent_count = notifier.send_batch_notifications(matches)
    print(f"Sent {sent_count} email notifications")

db.close()
```

### Or send notification for a single match:

```python
from src.notifications.email_notifier import EmailNotifier

notifier = EmailNotifier()
notifier.authenticate()

# match is a dictionary from JobMatcher.match_job()
if notifier.send_job_match_notification(match):
    print("Notification sent successfully")
```

## Configuration Options

### Email Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `false` | Enable/disable email notifications |
| `service` | `"gmail"` | Email service (only Gmail supported) |
| `credentials_path` | `"credentials.json"` | Path to OAuth credentials file |
| `token_path` | `"token.json"` | Path to store OAuth token |
| `from_address` | Required | Your Gmail address |
| `to_address` | Required | Recipient email address |
| `subject_template` | Template | Email subject (supports placeholders) |
| `notify_min_score` | `0.7` | Minimum match score to trigger email |

### Subject Template Placeholders

Available placeholders in `subject_template`:
- `{job_title}` - Job title
- `{company}` - Company name
- `{score}` - Match score as percentage

Example:
```yaml
subject_template: "🎯 {score} Match: {job_title} at {company}"
```

## Troubleshooting

### "Credentials file not found"
- Ensure `credentials.json` is in the project root
- Update `credentials_path` in config.yaml if file is elsewhere

### "Authentication failed"
- Delete `token.json` and re-authenticate
- Verify your Gmail address is added as a test user in Google Cloud Console
- Check that Gmail API is enabled

### "Email not sent"
- Check `email.enabled` is `true` in config.yaml
- Verify match score exceeds `notify_min_score` threshold
- Check for error messages in console output

### Emails go to spam
- First email from a new app may go to spam
- Mark as "Not Spam" to train Gmail
- Consider verifying your app in Google Cloud Console (for production use)

### OAuth consent screen shows "unverified app" warning
- This is normal for apps in testing mode
- Click "Advanced" → "Go to [App Name] (unsafe)" to proceed
- For production, submit app for verification

## Security Notes

1. **Never commit credentials.json or token.json to version control**
   - Both files are in `.gitignore`
   - Keep them secure and private

2. **OAuth token expiration**
   - Tokens expire after some time
   - The system automatically refreshes expired tokens
   - If refresh fails, delete `token.json` and re-authenticate

3. **Revoke access**
   - Go to [Google Account Security](https://myaccount.google.com/security)
   - Click "Third-party apps with account access"
   - Remove "LinkedIn Job Matcher" to revoke access

## Email Template Customization

The email templates are defined in `src/notifications/email_notifier.py`:

- **HTML template**: `generate_job_match_html()` - Full HTML with styling
- **Text template**: `generate_job_match_text()` - Plain text fallback

To customize templates, edit these methods in the `EmailNotifier` class.

## Next Steps

After setting up email notifications:

1. **Test with real job matches**: Run `python scripts/run_matching_demo.py`
2. **Adjust threshold**: Set `notify_min_score` to your preference (0.6-0.9)
3. **Set up scheduling**: Configure automated job searches (Task 8)
4. **Monitor your inbox**: Check for job match notifications

## Support

For issues or questions:
- Check this documentation
- Review error messages in console output
- Verify all configuration settings
- Test with `python scripts/test_email_notifications.py`
