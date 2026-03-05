# Google Sheets Integration Setup Guide

This guide walks you through setting up Google Sheets integration for the LinkedIn Job Matcher. With this integration enabled, high-scoring job matches (≥70% by default) are automatically exported to a Google Spreadsheet for easy review and quality control.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Google Cloud Console Setup](#google-cloud-console-setup)
3. [Create Google Spreadsheet](#create-google-spreadsheet)
4. [Configure the Application](#configure-the-application)
5. [First-Time Authentication](#first-time-authentication)
6. [Testing the Integration](#testing-the-integration)
7. [Understanding the Spreadsheet](#understanding-the-spreadsheet)
8. [Troubleshooting](#troubleshooting)
9. [Configuration Options](#configuration-options)

## Prerequisites

Before you begin, ensure you have:

- ✅ Completed the Gmail API setup (we'll reuse the same credentials)
- ✅ A Google account (the same one used for Gmail setup)
- ✅ `credentials.json` file in your project root directory
- ✅ Internet connection for OAuth authentication

**Note**: If you haven't set up Gmail integration yet, follow the [Email Setup Guide](EMAIL_SETUP.md) first to create the OAuth credentials.

## Google Cloud Console Setup

### Step 1: Enable Google Sheets API

1. Go to the [Google Cloud Console](https://console.cloud.google.com)

2. Select your existing project (the one you created for Gmail)

3. Navigate to **APIs & Services** > **Library**

4. Search for "Google Sheets API"

5. Click on **Google Sheets API** in the results

6. Click the **Enable** button

### Step 2: Update OAuth Consent Screen (Add Sheets Scope)

1. Navigate to **APIs & Services** > **OAuth consent screen**

2. Click **Edit App** at the bottom

3. Click **Save and Continue** through the first two screens (App information and App domain)

4. On the **Scopes** screen:
   - Click **Add or Remove Scopes**
   - Search for "sheets"
   - Check the box next to `https://www.googleapis.com/auth/spreadsheets`
   - You should now have two scopes:
     - `.../auth/gmail.send` (from Gmail setup)
     - `.../auth/spreadsheets` (newly added)
   - Click **Update** at the bottom

5. Click **Save and Continue**

6. Review and click **Back to Dashboard**

**Note**: You don't need to create new credentials. The existing `credentials.json` file will work for both Gmail and Sheets APIs.

## Create Google Spreadsheet

### Step 1: Create a New Spreadsheet

1. Go to [Google Sheets](https://sheets.google.com)

2. Click **+ Blank** to create a new spreadsheet

3. Rename it to something meaningful like "LinkedIn Job Matches" or "Job Search Results"

### Step 2: Get the Spreadsheet ID

The spreadsheet ID is found in the URL:

```
https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_HERE/edit#gid=0
                                       ^^^^^^^^^^^^^^^^^^^^
                                       This is your spreadsheet ID
```

**Example**:
```
URL: https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit

Spreadsheet ID: 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms
```

Copy this ID - you'll need it in the next step.

## Configure the Application

### Step 1: Update config.yaml

Open `config.yaml` and update the `sheets` section:

```yaml
# Google Sheets Integration Configuration
sheets:
  enabled: true  # Change from false to true
  spreadsheet_id: "YOUR_SPREADSHEET_ID_HERE"  # Paste your spreadsheet ID
  sheet_name: "Job Matches"  # Name of the sheet tab (will be created automatically)
  credentials_path: "credentials.json"  # Same file as Gmail
  token_path: "sheets_token.json"  # Separate token file for Sheets

  # Export settings
  export_min_score: 0.7  # Only export matches with score >= 70%
  auto_export: true  # Automatically export during job matching
  include_skill_gaps: true  # Show missing skills
  include_matching_skills: true  # Show matching skills
  max_skills_display: 10  # Max skills to show before truncating
```

**Required Changes**:
1. Set `enabled: true`
2. Replace `YOUR_SPREADSHEET_ID_HERE` with your actual spreadsheet ID

**Optional Customization**:
- `sheet_name`: Change if you want a different tab name
- `export_min_score`: Adjust threshold (0.0 to 1.0)
- `max_skills_display`: Show more or fewer skills per cell

### Step 2: Verify credentials.json

Ensure `credentials.json` is in your project root:

```bash
ls -l credentials.json
```

If it's missing, download it again from Google Cloud Console:
1. Go to **APIs & Services** > **Credentials**
2. Find your OAuth 2.0 Client ID
3. Click the download icon
4. Save as `credentials.json` in the project root

## First-Time Authentication

### Step 1: Run the Demo Script

The first time you use Sheets integration, you'll need to authenticate:

```bash
python scripts/test_sheets_export.py
```

### Step 2: Complete OAuth Flow

1. A browser window will open automatically

2. Select your Google account

3. You'll see a warning: "Google hasn't verified this app"
   - Click **Advanced**
   - Click **Go to [Your App Name] (unsafe)**

4. Review the permissions:
   - ✓ View and manage spreadsheets in Google Sheets
   - Click **Continue**

5. The browser will show "The authentication flow has completed"

6. Return to your terminal - authentication is complete!

### Step 3: Verify Token Creation

After successful authentication, a new file `sheets_token.json` will be created:

```bash
ls -l sheets_token.json
```

**Security Note**: `sheets_token.json` is automatically excluded from git via `.gitignore`. Never commit this file to version control.

## Testing the Integration

### Run the Demo Script

```bash
python scripts/test_sheets_export.py
```

**Expected Output**:
```
================================================================================
Google Sheets Export Demo
================================================================================

✓ Google Sheets integration is enabled

✓ Spreadsheet ID: 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms

Initializing Sheets connector...
Authenticating with Google Sheets API...

✓ Authentication successful

Initializing spreadsheet with headers and formatting...
✓ Spreadsheet initialized successfully

Formatting applied:
  • Bold blue header row with white text
  • Frozen header row
  • Conditional formatting for scores:
    - Green for ≥ 80%
    - Yellow for 70-79%
    - Orange for 60-69%

Creating sample job matches...
✓ Created 5 sample matches

Exporting matches with score ≥ 70%...
✓ Successfully exported 4 matches

================================================================================
View your results:
📊 https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms
================================================================================

✓ Google Sheets export demo completed successfully!
```

### Verify in Google Sheets

1. Click the spreadsheet URL from the output

2. Check that you see:
   - **Header Row**: Blue background, white text, bold
   - **Color-Coded Scores**: Green for high scores, yellow for medium, orange for lower
   - **Frozen Header**: Header stays visible when scrolling
   - **Sample Data**: 4 job matches exported

## Understanding the Spreadsheet

### Column Structure

| Column | Description | Format |
|--------|-------------|--------|
| Export Date | When the match was exported | YYYY-MM-DD HH:MM:SS |
| Job Title | Title of the job position | Text |
| Company | Company name | Text |
| Location | Job location | Text |
| Overall Score (%) | Combined match score | Number (0-100) with color |
| Skills Score (%) | Skills match score | Number (0-100) with color |
| Experience Score (%) | Experience match score | Number (0-100) with color |
| Matching Skills | Skills you have that match | Comma-separated list |
| Skill Gaps | Skills required but missing | Comma-separated list |
| Job URL | Link to LinkedIn job posting | URL |
| Match ID | Database match ID | Number |
| Resume ID | Database resume ID | Number |
| Status | Track application status | Text (empty by default) |

### Color Coding

Score columns are automatically color-coded:

- 🟢 **Green** (≥80%): Excellent match
- 🟡 **Yellow** (70-79%): Good match
- 🟠 **Orange** (60-69%): Fair match

Matches below the `export_min_score` threshold (70% by default) are not exported.

### Using the Status Column

The Status column is empty by default. Use it to track your application progress:

- "Applied"
- "Interview Scheduled"
- "Rejected"
- "Offer Received"
- etc.

### Skill Truncation

If a job has more than 10 matching skills or skill gaps (configurable), the list is truncated:

```
Python, SQL, Product Management, Agile, Scrum, User Research, A/B Testing, KPIs, Roadmap Planning, Data Analysis +5 more
```

Adjust `max_skills_display` in config.yaml to show more or fewer skills.

## Troubleshooting

### Error: "Sheets service not initialized"

**Cause**: Sheets integration is disabled or authentication failed.

**Solution**:
1. Check that `sheets.enabled: true` in config.yaml
2. Verify `spreadsheet_id` is correct
3. Run authentication: `python scripts/test_sheets_export.py`

### Error: "The caller does not have permission"

**Cause**: The Google Sheets API is not enabled or the spreadsheet doesn't exist.

**Solution**:
1. Enable Google Sheets API in Google Cloud Console
2. Verify the spreadsheet ID is correct
3. Ensure you have edit access to the spreadsheet

### Error: "Invalid authentication credentials"

**Cause**: The OAuth token has expired or been revoked.

**Solution**:
1. Delete `sheets_token.json`
2. Run `python scripts/test_sheets_export.py` to re-authenticate

### Error: "Credentials file not found"

**Cause**: `credentials.json` is missing.

**Solution**:
1. Download OAuth credentials from Google Cloud Console
2. Save as `credentials.json` in project root
3. Verify: `ls -l credentials.json`

### No Matches Exported

**Cause**: All matches are below the `export_min_score` threshold.

**Solution**:
1. Check match scores in the job matching output
2. Lower `export_min_score` in config.yaml (e.g., to 0.6)
3. Run the job matching again

### Duplicate Rows

**Cause**: Running exports multiple times with the same matches.

**Solution**:
- The system appends rows each time
- This is intentional for quality control and tracking over time
- Manually remove duplicates if needed, or clear the sheet before re-running tests

## Configuration Options

### Export Threshold

Control which matches get exported:

```yaml
export_min_score: 0.7  # Only export matches >= 70%
```

**Recommended Values**:
- `0.8`: Only excellent matches (may miss good opportunities)
- `0.7`: Good and excellent matches (recommended)
- `0.6`: Include fair matches (more data, more noise)

### Auto Export

Enable or disable automatic export during job matching:

```yaml
auto_export: true  # Automatically export when matching jobs
```

- `true`: Matches are exported automatically during job search
- `false`: Manual export only (use SheetsConnector programmatically)

### Skill Display

Control how many skills are shown:

```yaml
include_matching_skills: true  # Show skills you have
include_skill_gaps: true  # Show skills you're missing
max_skills_display: 10  # Maximum skills before truncation
```

**Examples**:
- Set to `5` for concise display
- Set to `20` for comprehensive skill lists
- Set to `100` to show all skills (may make cells very wide)

### Sheet Name

Customize the tab name:

```yaml
sheet_name: "Job Matches"  # Name of the sheet tab
```

**Use Cases**:
- Multiple users: "John's Job Matches"
- Time-based: "November 2023 Jobs"
- Campaign-based: "Remote PM Jobs"

## Integration with Job Matching

Once configured, Sheets export works automatically during job searches:

```python
from src.matcher.job_matcher import JobMatcher
from src.integrations.sheets_connector import SheetsConnector

# Run job matching
matcher = JobMatcher()
matches = matcher.match_jobs(jobs, resume)

# Export high-scoring matches to Google Sheets
sheets = SheetsConnector()
if sheets.enabled and sheets.auto_export:
    exported_count = sheets.export_matches_batch(matches)
    print(f"Exported {exported_count} matches to Google Sheets")
```

## Best Practices

### 1. Regular Exports

- Run daily or weekly job searches
- Review spreadsheet regularly
- Update Status column to track applications

### 2. Data Management

- Create separate sheets for different job search campaigns
- Use filters and sorting in Google Sheets for analysis
- Export to CSV for long-term archival

### 3. Quality Control

- Review skill gaps to identify learning opportunities
- Compare match scores with your own assessment
- Adjust matching algorithm weights based on results

### 4. Security

- Keep `sheets_token.json` private
- Don't share the spreadsheet publicly (job search data is sensitive)
- Use Google Sheets sharing settings to control access

### 5. Performance

- Use batch export for large result sets (more efficient than single exports)
- Limit `max_skills_display` to keep cells readable
- Create new sheets periodically to avoid very large spreadsheets

## Next Steps

Now that Google Sheets integration is set up:

1. ✅ Run a real job search with `python main.py` (once CLI is implemented)
2. ✅ Review exported matches in your spreadsheet
3. ✅ Track applications using the Status column
4. ✅ Analyze trends in match scores and skill gaps

For more information on the matching algorithm, see the main project README.
