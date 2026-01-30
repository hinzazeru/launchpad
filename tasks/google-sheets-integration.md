# Google Sheets Integration - Task Breakdown

## Overview

Integrate Google Sheets API to automatically export high-scoring job matches to a spreadsheet for review and quality control.

## Benefits

- **Centralized tracking**: All high-scoring matches in one place
- **Easy sharing**: Share spreadsheet with mentors, career coaches, or accountability partners
- **Historical data**: Track job matches over time
- **Quality control**: Review and verify match accuracy
- **Analytics**: Analyze trends in job market and matching performance

## Task Breakdown

### Task 1: Install Dependencies

**Objective**: Install Google Sheets API Python client libraries

**Steps**:
1. Install google-api-python-client (already installed for Gmail)
2. Install google-auth-oauthlib (already installed for Gmail)
3. Verify installation

**Acceptance Criteria**:
- [x] Dependencies installed successfully
- [x] No version conflicts with existing packages

**Estimated Time**: 5 minutes (already complete)

---

### Task 2: Configuration Setup

**Objective**: Add Google Sheets settings to config.yaml

**Steps**:
1. Add sheets section to config.yaml
2. Define spreadsheet ID, sheet name, credentials path
3. Set export threshold (e.g., only export matches >= 70%)
4. Update config.yaml.example

**Configuration Structure**:
```yaml
sheets:
  enabled: false
  spreadsheet_id: "YOUR_SPREADSHEET_ID_HERE"
  sheet_name: "Job Matches"
  credentials_path: "credentials.json"  # Reuse Gmail OAuth credentials
  token_path: "sheets_token.json"

  # Export settings
  export_min_score: 0.7  # Only export matches >= 70%
  auto_export: true      # Automatically export high matches
  include_skill_gaps: true
  include_matching_skills: true
```

**Acceptance Criteria**:
- [ ] Config schema defined
- [ ] Example config created
- [ ] Config validation added

**Estimated Time**: 15 minutes

---

### Task 3: Google Sheets Connector Module

**Objective**: Create connector module for Google Sheets API

**Steps**:
1. Create `src/integrations/` directory
2. Create `src/integrations/__init__.py`
3. Create `src/integrations/sheets_connector.py`
4. Implement SheetsConnector class with:
   - OAuth 2.0 authentication
   - Spreadsheet initialization
   - Row append functionality
   - Batch write support

**Key Methods**:
```python
class SheetsConnector:
    def authenticate() -> bool
    def initialize_spreadsheet() -> bool
    def write_match(match: Dict) -> bool
    def write_matches_batch(matches: List[Dict]) -> int
    def format_spreadsheet() -> bool
```

**Acceptance Criteria**:
- [ ] SheetsConnector class created
- [ ] Authentication implemented
- [ ] Write operations implemented
- [ ] Error handling in place

**Estimated Time**: 60 minutes

---

### Task 4: OAuth 2.0 Authentication

**Objective**: Implement Google Sheets API authentication using OAuth 2.0

**Steps**:
1. Reuse Gmail OAuth credentials (same Google Cloud project)
2. Add Sheets API scope: `https://www.googleapis.com/auth/spreadsheets`
3. Implement token storage/refresh
4. Handle authentication errors

**OAuth Scopes Needed**:
- `https://www.googleapis.com/auth/spreadsheets` - Read/write spreadsheets

**Acceptance Criteria**:
- [ ] OAuth flow working
- [ ] Token persisted to sheets_token.json
- [ ] Token refresh implemented
- [ ] Graceful error handling

**Estimated Time**: 30 minutes

---

### Task 5: Export Functions

**Objective**: Create functions to export job matches to Google Sheets

**Steps**:
1. Implement `export_match(match)` - Single match export
2. Implement `export_matches_batch(matches)` - Batch export
3. Add filtering by score threshold
4. Include metadata (export date, resume ID, match ID)

**Spreadsheet Columns**:
| Column | Description |
|--------|-------------|
| Export Date | When the match was exported |
| Job Title | Job posting title |
| Company | Company name |
| Location | Job location |
| Overall Score | Combined match score (%) |
| Skills Score | Skills match score (%) |
| Experience Score | Experience match score (%) |
| Matching Skills | List of matching skills |
| Skill Gaps | List of skills to develop |
| Job URL | Direct link to posting |
| Match ID | Database match ID |
| Resume ID | Database resume ID |
| Status | Applied / Interviewing / Rejected / Offer |

**Acceptance Criteria**:
- [ ] Single export working
- [ ] Batch export working
- [ ] All columns populated
- [ ] Filtering by threshold working

**Estimated Time**: 45 minutes

---

### Task 6: Spreadsheet Formatting

**Objective**: Add professional formatting to the Google Sheet

**Steps**:
1. Create header row with bold formatting
2. Apply conditional formatting for scores:
   - Green: >= 80%
   - Yellow: 70-79%
   - Orange: 60-69%
   - Red: < 60%
3. Freeze header row
4. Set column widths
5. Add data validation for Status column
6. Format URLs as hyperlinks

**Acceptance Criteria**:
- [ ] Headers formatted
- [ ] Conditional formatting applied
- [ ] Column widths optimized
- [ ] Professional appearance

**Estimated Time**: 30 minutes

---

### Task 7: Testing

**Objective**: Write comprehensive tests for Sheets integration

**Steps**:
1. Create `src/integrations/test_sheets_connector.py`
2. Write unit tests for:
   - Authentication
   - Spreadsheet initialization
   - Single write
   - Batch write
   - Formatting
   - Error handling
3. Mock Google Sheets API calls

**Test Coverage**:
- [ ] Test initialization
- [ ] Test authentication (mocked)
- [ ] Test write operations (mocked)
- [ ] Test error scenarios
- [ ] Test filtering logic

**Acceptance Criteria**:
- [ ] 10+ tests written
- [ ] All tests passing
- [ ] Mock-based (no actual API calls)

**Estimated Time**: 45 minutes

---

### Task 8: Demo Script

**Objective**: Create demo script to test Google Sheets export

**Steps**:
1. Create `test_sheets_export.py`
2. Check if Sheets is enabled in config
3. Authenticate with Google Sheets
4. Create/verify spreadsheet
5. Export sample matches
6. Display confirmation and spreadsheet URL

**Features**:
- Interactive setup wizard
- Sample data export
- Spreadsheet URL output
- Error handling and troubleshooting

**Acceptance Criteria**:
- [ ] Demo script created
- [ ] Interactive prompts working
- [ ] Sample export successful
- [ ] Clear user feedback

**Estimated Time**: 30 minutes

---

### Task 9: Documentation

**Objective**: Create comprehensive Google Sheets setup guide

**Steps**:
1. Create `docs/SHEETS_SETUP.md`
2. Document Google Cloud Console setup
3. Explain spreadsheet creation
4. Provide configuration examples
5. Include troubleshooting section

**Documentation Sections**:
1. Overview
2. Prerequisites
3. Google Cloud Console setup
4. Enable Google Sheets API
5. Update OAuth consent screen (add Sheets scope)
6. Create Google Spreadsheet
7. Configuration guide
8. Testing the integration
9. Troubleshooting
10. Usage examples

**Acceptance Criteria**:
- [ ] Complete setup guide
- [ ] Step-by-step instructions
- [ ] Screenshots/examples
- [ ] Troubleshooting section

**Estimated Time**: 45 minutes

---

## Total Estimated Time: 4-5 hours

## Dependencies

- Google Sheets API enabled in Google Cloud Console
- OAuth 2.0 credentials (can reuse Gmail credentials)
- Google Spreadsheet created
- google-api-python-client package (already installed)

## Integration Points

The Google Sheets connector will integrate with:

1. **Job Matching Pipeline**: Auto-export after matching
2. **Email Notifications**: Export before/after sending email
3. **Database**: Read matches from MatchResult table
4. **Config System**: Use existing config.yaml

## Future Enhancements

- **Automatic spreadsheet creation**: Create spreadsheet if it doesn't exist
- **Multiple sheet support**: Separate sheets for different resumes
- **Data visualization**: Add charts and pivot tables
- **Sync status**: Update Status column based on database
- **Archiving**: Move old matches to archive sheet
- **Template support**: Use predefined spreadsheet templates

## Success Criteria

- [x] Tasks defined
- [ ] All dependencies installed
- [ ] Configuration complete
- [ ] Connector module working
- [ ] Tests passing
- [ ] Demo successful
- [ ] Documentation complete
- [ ] User can export high-scoring matches to Google Sheets
- [ ] Spreadsheet is professionally formatted
- [ ] Integration is reliable and error-free
