"""Google Sheets connector module for exporting job matches."""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config import get_config


# Google Sheets API scopes
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


class SheetsConnector:
    """Google Sheets connector for exporting job match data.

    This class handles:
    - Google Sheets OAuth 2.0 authentication
    - Spreadsheet initialization and formatting
    - Exporting job matches to spreadsheet
    - Batch operations for efficiency
    """

    def __init__(self):
        """Initialize Sheets connector with configuration."""
        self.config = get_config()
        self.enabled = self.config.get("sheets.enabled", False)
        self.service = None

        if self.enabled:
            self.spreadsheet_id = self.config.get("sheets.spreadsheet_id")
            self.sheet_name = self.config.get("sheets.sheet_name", "Job Matches")
            self.credentials_path = self.config.get("sheets.credentials_path", "credentials.json")
            self.token_path = self.config.get("sheets.token_path", "sheets_token.json")

            # Export settings
            self.export_min_score = self.config.get("sheets.export_min_score", 0.7)
            self.auto_export = self.config.get("sheets.auto_export", True)
            self.include_skill_gaps = self.config.get("sheets.include_skill_gaps", True)
            self.include_matching_skills = self.config.get("sheets.include_matching_skills", True)
            self.max_skills_display = self.config.get("sheets.max_skills_display", 10)

    def authenticate(self) -> bool:
        """Authenticate with Google Sheets API using OAuth 2.0.

        Returns:
            bool: True if authentication successful, False otherwise
        """
        if not self.enabled:
            return False

        creds = None

        # Check if token file exists
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception as e:
                print(f"Error loading token: {e}")

        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    creds = None

            if not creds:
                # Check if credentials file exists
                if not os.path.exists(self.credentials_path):
                    print(f"Credentials file not found: {self.credentials_path}")
                    print("Please download OAuth credentials from Google Cloud Console")
                    return False

                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    print(f"Error during OAuth flow: {e}")
                    return False

            # Save the credentials for the next run
            try:
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                print(f"Error saving token: {e}")

        try:
            self.service = build('sheets', 'v4', credentials=creds)
            return True
        except Exception as e:
            print(f"Error building Sheets service: {e}")
            return False

    def initialize_spreadsheet(self) -> bool:
        """Initialize spreadsheet with headers and formatting.

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.service:
            print("Sheets service not initialized. Call authenticate() first.")
            return False

        try:
            # Define header row
            headers = [
                'Export Date',
                'Job Title',
                'Company',
                'Location',
                'Overall Score (%)',
                'Skills Score (%)',
                'Experience Score (%)',
            ]

            if self.include_matching_skills:
                headers.append('Matching Skills')

            if self.include_skill_gaps:
                headers.append('Skill Gaps')

            headers.extend([
                'Required Domains',
                'Job URL',
                'Match ID',
                'Resume ID',
                'Status'
            ])

            # Check if sheet exists, if not create it
            try:
                sheet_metadata = self.service.spreadsheets().get(
                    spreadsheetId=self.spreadsheet_id
                ).execute()

                # Check if our sheet exists
                sheet_exists = False
                for sheet in sheet_metadata.get('sheets', []):
                    if sheet['properties']['title'] == self.sheet_name:
                        sheet_exists = True
                        break

                if not sheet_exists:
                    # Create the sheet
                    request_body = {
                        'requests': [{
                            'addSheet': {
                                'properties': {
                                    'title': self.sheet_name
                                }
                            }
                        }]
                    }
                    self.service.spreadsheets().batchUpdate(
                        spreadsheetId=self.spreadsheet_id,
                        body=request_body
                    ).execute()

            except HttpError as error:
                print(f"Error checking/creating sheet: {error}")
                return False

            # Write headers
            range_name = f"{self.sheet_name}!A1"
            body = {
                'values': [headers]
            }

            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()

            # Format headers
            self._format_headers()

            # Set up conditional formatting for scores
            self._setup_conditional_formatting()

            # Freeze header row
            self._freeze_header_row()

            return True

        except HttpError as error:
            print(f"An error occurred: {error}")
            return False

    def _format_headers(self):
        """Apply bold formatting to header row."""
        try:
            # Get sheet ID
            sheet_id = self._get_sheet_id()
            if sheet_id is None:
                return

            request_body = {
                'requests': [
                    {
                        'repeatCell': {
                            'range': {
                                'sheetId': sheet_id,
                                'startRowIndex': 0,
                                'endRowIndex': 1
                            },
                            'cell': {
                                'userEnteredFormat': {
                                    'backgroundColor': {
                                        'red': 0.2,
                                        'green': 0.4,
                                        'blue': 0.8
                                    },
                                    'textFormat': {
                                        'foregroundColor': {
                                            'red': 1.0,
                                            'green': 1.0,
                                            'blue': 1.0
                                        },
                                        'fontSize': 11,
                                        'bold': True
                                    }
                                }
                            },
                            'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                        }
                    }
                ]
            }

            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=request_body
            ).execute()

        except HttpError as error:
            print(f"Error formatting headers: {error}")

    def _setup_conditional_formatting(self):
        """Set up conditional formatting for score columns."""
        # Conditional formatting disabled - data rows use default black text, no background color
        pass

    def _freeze_header_row(self):
        """Freeze the header row."""
        try:
            sheet_id = self._get_sheet_id()
            if sheet_id is None:
                return

            request_body = {
                'requests': [{
                    'updateSheetProperties': {
                        'properties': {
                            'sheetId': sheet_id,
                            'gridProperties': {
                                'frozenRowCount': 1
                            }
                        },
                        'fields': 'gridProperties.frozenRowCount'
                    }
                }]
            }

            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=request_body
            ).execute()

        except HttpError as error:
            print(f"Error freezing header row: {error}")

    def _get_sheet_id(self) -> Optional[int]:
        """Get the sheet ID for the configured sheet name.

        Returns:
            Optional[int]: Sheet ID if found, None otherwise
        """
        try:
            sheet_metadata = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()

            for sheet in sheet_metadata.get('sheets', []):
                if sheet['properties']['title'] == self.sheet_name:
                    return sheet['properties']['sheetId']

            return None

        except HttpError as error:
            print(f"Error getting sheet ID: {error}")
            return None

    def export_match(self, match: Dict) -> bool:
        """Export a single job match to Google Sheets.

        Args:
            match: Match result dictionary from JobMatcher

        Returns:
            bool: True if export successful, False otherwise
        """
        if not self.enabled:
            return False

        # Check if match score exceeds threshold
        if match['overall_score'] < self.export_min_score:
            return False

        # Authenticate if not already authenticated
        if not self.service:
            if not self.authenticate():
                return False

        try:
            # Prepare row data
            row_data = self._prepare_row_data(match)

            # Append to spreadsheet
            range_name = f"{self.sheet_name}!A:A"
            body = {
                'values': [row_data]
            }

            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()

            return True

        except HttpError as error:
            print(f"An error occurred: {error}")
            return False

    def export_matches_batch(self, matches: List[Dict]) -> int:
        """Export multiple job matches to Google Sheets in batch.

        Args:
            matches: List of match result dictionaries

        Returns:
            int: Number of matches exported successfully
        """
        if not self.enabled:
            return 0

        # Authenticate if not already authenticated
        if not self.service:
            if not self.authenticate():
                return 0

        # Filter matches by score threshold
        filtered_matches = [
            m for m in matches
            if m['overall_score'] >= self.export_min_score
        ]

        if not filtered_matches:
            return 0

        try:
            # Prepare all rows
            rows = [self._prepare_row_data(match) for match in filtered_matches]

            # Batch append to spreadsheet
            range_name = f"{self.sheet_name}!A:A"
            body = {
                'values': rows
            }

            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()

            return len(rows)

        except HttpError as error:
            print(f"An error occurred: {error}")
            return 0

    def _prepare_row_data(self, match: Dict) -> List:
        """Prepare row data from match dictionary.

        Args:
            match: Match result dictionary

        Returns:
            List: Row data ready for Sheets API
        """
        # Format scores as percentages
        overall_score = round(match['overall_score'] * 100, 1)
        skills_score = round(match['skills_score'] * 100, 1)
        experience_score = round(match['experience_score'] * 100, 1)

        # Format skills lists
        matching_skills = ', '.join(match.get('matching_skills', [])[:self.max_skills_display])
        if len(match.get('matching_skills', [])) > self.max_skills_display:
            matching_skills += f" +{len(match['matching_skills']) - self.max_skills_display} more"

        skill_gaps = ', '.join(match.get('skill_gaps', [])[:self.max_skills_display])
        if len(match.get('skill_gaps', [])) > self.max_skills_display:
            skill_gaps += f" +{len(match['skill_gaps']) - self.max_skills_display} more"

        # Build row
        row = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            match.get('job_title', ''),
            match.get('company', ''),
            match.get('location', ''),
            overall_score,
            skills_score,
            experience_score,
        ]

        if self.include_matching_skills:
            row.append(matching_skills)

        if self.include_skill_gaps:
            row.append(skill_gaps)

        # Format required domains
        required_domains = match.get('required_domains', [])
        if required_domains:
            domains_str = ', '.join(d.replace('_', ' ').title() for d in required_domains[:5])
            if len(required_domains) > 5:
                domains_str += f" +{len(required_domains) - 5} more"
        else:
            domains_str = ''

        row.extend([
            domains_str,
            match.get('url', ''),
            match.get('match_id', ''),
            match.get('resume_id', ''),
            ''  # Status - empty by default
        ])

        return row

    def log_all_jobs_to_sheets(self, matches: List[Dict], sheet_name: str = "Logs") -> int:
        """Log all jobs with their match scores to a Logs sheet.

        This exports ALL jobs (not just high matches) for analysis and debugging.

        Args:
            matches: List of match result dictionaries
            sheet_name: Name of the sheet to log to (default: "Logs")

        Returns:
            int: Number of jobs logged
        """
        if not self.enabled or not matches:
            return 0

        if not self.authenticate():
            return 0

        try:
            # Prepare header row for Logs sheet (more detailed than main sheet)
            headers = [
                'Timestamp',
                'Job Title',
                'Company',
                'Location',
                'Match Score (%)',
                'Skills Score (%)',
                'Experience Score (%)',
                'Matching Skills',
                'Missing Skills',
                'Required Skills',
                'Experience Required (yrs)',
                'LinkedIn URL',
                'Job ID',
                'Resume ID',
                'Posted Date',
                'Description Preview',
                'Engine Version'
            ]

            # Check if this is first time writing to Logs sheet
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A1:Q1"
            ).execute()

            existing_headers = result.get('values', [[]])

            # If headers don't exist or are different, write them
            if not existing_headers or existing_headers[0] != headers:
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{sheet_name}!A1",
                    valueInputOption='RAW',
                    body={'values': [headers]}
                ).execute()

            # Prepare row data for all jobs
            rows_to_add = []
            for match in matches:
                # Format scores
                overall_score = round(match.get('overall_score', 0) * 100, 1)
                skills_score = round(match.get('skills_score', 0) * 100, 1)
                experience_score = round(match.get('experience_score', 0) * 100, 1)

                # Format skills
                matching_skills = ', '.join(match.get('matching_skills', [])[:15])
                if len(match.get('matching_skills', [])) > 15:
                    matching_skills += f" +{len(match['matching_skills']) - 15} more"

                missing_skills = ', '.join(match.get('skill_gaps', [])[:15])
                if len(match.get('skill_gaps', [])) > 15:
                    missing_skills += f" +{len(match['skill_gaps']) - 15} more"

                required_skills = ', '.join(match.get('required_skills', [])[:15])
                if len(match.get('required_skills', [])) > 15:
                    required_skills += f" +{len(match['required_skills']) - 15} more"

                # Truncate description
                description = match.get('description', '')
                description_preview = description[:200] + '...' if description and len(description) > 200 else description

                # Format posted date
                posted_date = match.get('posting_date', '')
                if posted_date and hasattr(posted_date, 'strftime'):
                    posted_date = posted_date.strftime('%Y-%m-%d')

                row = [
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    match.get('job_title', ''),
                    match.get('company', ''),
                    match.get('location', ''),
                    overall_score,
                    skills_score,
                    experience_score,
                    matching_skills,
                    missing_skills,
                    required_skills,
                    match.get('experience_required', ''),
                    match.get('url', ''),
                    match.get('job_id', ''),
                    match.get('resume_id', ''),
                    posted_date,
                    description_preview,
                    match.get('engine_version', '')
                ]

                rows_to_add.append(row)

            # Append all rows at once
            if rows_to_add:
                self.service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{sheet_name}!A2",
                    valueInputOption='RAW',
                    insertDataOption='INSERT_ROWS',
                    body={'values': rows_to_add}
                ).execute()

            print(f"✅ Logged {len(rows_to_add)} jobs to '{sheet_name}' sheet")
            return len(rows_to_add)

        except HttpError as error:
            print(f"Error logging jobs to sheets: {error}")
            return 0

    def _format_log_headers(self):
        """Apply formatting to Logs sheet header row."""
        try:
            sheet_id = self._get_sheet_id()
            if sheet_id is None:
                return

            request_body = {
                'requests': [
                    {
                        'repeatCell': {
                            'range': {
                                'sheetId': sheet_id,
                                'startRowIndex': 0,
                                'endRowIndex': 1
                            },
                            'cell': {
                                'userEnteredFormat': {
                                    'backgroundColor': {
                                        'red': 0.2,
                                        'green': 0.2,
                                        'blue': 0.2
                                    },
                                    'textFormat': {
                                        'foregroundColor': {
                                            'red': 1.0,
                                            'green': 1.0,
                                            'blue': 1.0
                                        },
                                        'fontSize': 10,
                                        'bold': True
                                    }
                                }
                            },
                            'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                        }
                    },
                    # Freeze header row
                    {
                        'updateSheetProperties': {
                            'properties': {
                                'sheetId': sheet_id,
                                'gridProperties': {
                                    'frozenRowCount': 1
                                }
                            },
                            'fields': 'gridProperties.frozenRowCount'
                        }
                    }
                ]
            }

            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=request_body
            ).execute()

        except HttpError as error:
            print(f"Error formatting log headers: {error}")

    def cleanup_old_matches(self, days: int = 7, sheet_name: str = None) -> Dict:
        """Remove job matches older than specified days from the sheet.

        Args:
            days: Number of days to keep (default: 7). Entries older than this are deleted.
            sheet_name: Name of the sheet to clean (default: self.sheet_name / "Job Matches")

        Returns:
            Dict with cleanup results:
                - deleted_count: Number of rows deleted
                - remaining_count: Number of rows remaining
                - success: Whether cleanup was successful
                - message: Status message
        """
        if not self.enabled:
            return {
                'deleted_count': 0,
                'remaining_count': 0,
                'success': False,
                'message': 'Google Sheets integration is disabled'
            }

        if not self.service:
            if not self.authenticate():
                return {
                    'deleted_count': 0,
                    'remaining_count': 0,
                    'success': False,
                    'message': 'Failed to authenticate with Google Sheets'
                }

        target_sheet = sheet_name or self.sheet_name
        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            # Read all data from the sheet
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{target_sheet}!A:A"  # Just read the date column
            ).execute()

            values = result.get('values', [])

            if len(values) <= 1:  # Only header or empty
                return {
                    'deleted_count': 0,
                    'remaining_count': 0,
                    'success': True,
                    'message': 'Sheet is empty (no data rows to clean)'
                }

            # Find rows to delete (skip header row at index 0)
            rows_to_delete = []
            for i, row in enumerate(values[1:], start=2):  # Start at row 2 (1-indexed, after header)
                if row:  # Check if row has data
                    try:
                        # Parse the date from first column
                        date_str = row[0]
                        row_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')

                        if row_date < cutoff_date:
                            rows_to_delete.append(i)
                    except (ValueError, IndexError):
                        # Skip rows with invalid or missing dates
                        continue

            if not rows_to_delete:
                return {
                    'deleted_count': 0,
                    'remaining_count': len(values) - 1,
                    'success': True,
                    'message': f'No entries older than {days} days found'
                }

            # Delete rows from bottom to top to avoid index shifting issues
            sheet_id = self._get_sheet_id_by_name(target_sheet)
            if sheet_id is None:
                return {
                    'deleted_count': 0,
                    'remaining_count': len(values) - 1,
                    'success': False,
                    'message': f'Could not find sheet: {target_sheet}'
                }

            # Build delete requests (must delete from bottom to top)
            delete_requests = []
            for row_index in sorted(rows_to_delete, reverse=True):
                delete_requests.append({
                    'deleteDimension': {
                        'range': {
                            'sheetId': sheet_id,
                            'dimension': 'ROWS',
                            'startIndex': row_index - 1,  # Convert to 0-indexed
                            'endIndex': row_index  # Delete single row
                        }
                    }
                })

            # Execute batch delete
            if delete_requests:
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={'requests': delete_requests}
                ).execute()

            deleted_count = len(rows_to_delete)
            remaining_count = len(values) - 1 - deleted_count

            print(f"🧹 Cleaned up {deleted_count} old entries from '{target_sheet}' sheet")

            return {
                'deleted_count': deleted_count,
                'remaining_count': remaining_count,
                'success': True,
                'message': f'Deleted {deleted_count} entries older than {days} days'
            }

        except HttpError as error:
            print(f"Error during cleanup: {error}")
            return {
                'deleted_count': 0,
                'remaining_count': 0,
                'success': False,
                'message': f'API error: {error}'
            }

    def _get_sheet_id_by_name(self, sheet_name: str) -> Optional[int]:
        """Get the sheet ID for a specific sheet name.

        Args:
            sheet_name: Name of the sheet

        Returns:
            Optional[int]: Sheet ID if found, None otherwise
        """
        try:
            sheet_metadata = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()

            for sheet in sheet_metadata.get('sheets', []):
                if sheet['properties']['title'] == sheet_name:
                    return sheet['properties']['sheetId']

            return None

        except HttpError as error:
            print(f"Error getting sheet ID: {error}")
            return None
