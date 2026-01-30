"""Email notification module using Gmail API with OAuth 2.0."""

import os
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config import get_config


# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.send']


class EmailNotifier:
    """Email notifier using Gmail API with OAuth 2.0.

    This class handles:
    - Gmail OAuth 2.0 authentication
    - Sending HTML/text email notifications
    - Email templates for job matches
    """

    def __init__(self):
        """Initialize email notifier with configuration."""
        self.config = get_config()
        self.enabled = self.config.get("email.enabled", False)
        self.service = None

        if self.enabled:
            self.credentials_path = self.config.get("email.credentials_path", "credentials.json")
            self.token_path = self.config.get("email.token_path", "token.json")
            self.from_address = self.config.get("email.from_address")
            self.to_address = self.config.get("email.to_address")
            self.subject_template = self.config.get("email.subject_template",
                                                   "New Job Match: {job_title} at {company}")
            self.notify_min_score = self.config.get("email.notify_min_score", 0.7)

    def authenticate(self) -> bool:
        """Authenticate with Gmail API using OAuth 2.0.

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
                    print("https://console.cloud.google.com/apis/credentials")
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
            self.service = build('gmail', 'v1', credentials=creds)
            return True
        except Exception as e:
            print(f"Error building Gmail service: {e}")
            return False

    def create_message(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ) -> Dict:
        """Create a message for an email.

        Args:
            to: Email address of recipient
            subject: Subject of the email
            html_body: HTML body of the email
            text_body: Plain text body (optional, falls back to HTML if not provided)

        Returns:
            Dict: Message object suitable for Gmail API
        """
        message = MIMEMultipart('alternative')
        message['to'] = to
        message['from'] = self.from_address
        message['subject'] = subject

        # Attach plain text version
        if text_body:
            part1 = MIMEText(text_body, 'plain')
            message.attach(part1)

        # Attach HTML version
        part2 = MIMEText(html_body, 'html')
        message.attach(part2)

        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        return {'raw': raw_message}

    def send_message(self, message: Dict) -> bool:
        """Send an email message.

        Args:
            message: Message object from create_message()

        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.service:
            print("Gmail service not initialized. Call authenticate() first.")
            return False

        try:
            self.service.users().messages().send(
                userId='me',
                body=message
            ).execute()
            return True
        except HttpError as error:
            print(f"An error occurred: {error}")
            return False

    def generate_job_match_html(self, match: Dict) -> str:
        """Generate HTML email body for a job match.

        Args:
            match: Match result dictionary from JobMatcher

        Returns:
            str: HTML email body
        """
        score_color = "#28a745" if match['overall_score'] >= 0.8 else "#ffc107" if match['overall_score'] >= 0.7 else "#17a2b8"

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: {score_color}; color: white; padding: 20px; border-radius: 5px; }}
                .score {{ font-size: 2em; font-weight: bold; }}
                .job-details {{ background-color: #f8f9fa; padding: 15px; margin: 15px 0; border-radius: 5px; }}
                .section {{ margin: 20px 0; }}
                .skills {{ display: flex; flex-wrap: wrap; gap: 5px; }}
                .skill {{ background-color: #007bff; color: white; padding: 5px 10px; border-radius: 3px; font-size: 0.9em; }}
                .gap {{ background-color: #dc3545; color: white; padding: 5px 10px; border-radius: 3px; font-size: 0.9em; }}
                .btn {{ display: inline-block; background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 10px; }}
                .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6; font-size: 0.9em; color: #6c757d; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>New Job Match Found!</h1>
                    <div class="score">{match['overall_score']:.0%} Match</div>
                </div>

                <div class="job-details">
                    <h2>{match['job_title']}</h2>
                    <p><strong>Company:</strong> {match['company']}</p>
                    <p><strong>Location:</strong> {match['location']}</p>
                </div>

                <div class="section">
                    <h3>Match Breakdown</h3>
                    <p>Skills Match: <strong>{match['skills_score']:.0%}</strong></p>
                    <p>Experience Match: <strong>{match['experience_score']:.0%}</strong></p>
                </div>
        """

        # Add matching skills
        if match.get('matching_skills'):
            html += """
                <div class="section">
                    <h3>Your Matching Skills</h3>
                    <div class="skills">
            """
            for skill in match['matching_skills'][:10]:
                html += f'<span class="skill">{skill}</span>'

            if len(match['matching_skills']) > 10:
                html += f'<span class="skill">+{len(match["matching_skills"]) - 10} more</span>'

            html += """
                    </div>
                </div>
            """

        # Add skill gaps
        if match.get('skill_gaps'):
            html += """
                <div class="section">
                    <h3>Skills to Develop</h3>
                    <div class="skills">
            """
            for gap in match['skill_gaps'][:5]:
                html += f'<span class="gap">{gap}</span>'

            if len(match['skill_gaps']) > 5:
                html += f'<span class="gap">+{len(match["skill_gaps"]) - 5} more</span>'

            html += """
                    </div>
                </div>
            """

        # Add apply button
        if match.get('url'):
            html += f"""
                <div class="section">
                    <a href="{match['url']}" class="btn">View Job Posting</a>
                </div>
            """

        # Footer
        html += """
                <div class="footer">
                    <p>This email was sent by LinkedIn Job Matcher</p>
                    <p>You received this because a job match score exceeded your notification threshold</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def generate_job_match_text(self, match: Dict) -> str:
        """Generate plain text email body for a job match.

        Args:
            match: Match result dictionary from JobMatcher

        Returns:
            str: Plain text email body
        """
        text = f"""
NEW JOB MATCH FOUND!

Match Score: {match['overall_score']:.0%}

Job Details:
- Title: {match['job_title']}
- Company: {match['company']}
- Location: {match['location']}

Match Breakdown:
- Skills Match: {match['skills_score']:.0%}
- Experience Match: {match['experience_score']:.0%}
"""

        if match.get('matching_skills'):
            text += f"\nYour Matching Skills ({len(match['matching_skills'])}):\n"
            for skill in match['matching_skills'][:10]:
                text += f"  - {skill}\n"
            if len(match['matching_skills']) > 10:
                text += f"  ... and {len(match['matching_skills']) - 10} more\n"

        if match.get('skill_gaps'):
            text += f"\nSkills to Develop ({len(match['skill_gaps'])}):\n"
            for gap in match['skill_gaps'][:5]:
                text += f"  - {gap}\n"
            if len(match['skill_gaps']) > 5:
                text += f"  ... and {len(match['skill_gaps']) - 5} more\n"

        if match.get('url'):
            text += f"\nView Job Posting:\n{match['url']}\n"

        text += "\n---\nThis email was sent by LinkedIn Job Matcher\n"

        return text

    def send_job_match_notification(self, match: Dict) -> bool:
        """Send email notification for a job match.

        Args:
            match: Match result dictionary from JobMatcher

        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.enabled:
            return False

        # Check if match score exceeds threshold
        if match['overall_score'] < self.notify_min_score:
            return False

        # Authenticate if not already authenticated
        if not self.service:
            if not self.authenticate():
                return False

        # Generate subject
        subject = self.subject_template.format(
            job_title=match['job_title'],
            company=match['company'],
            score=f"{match['overall_score']:.0%}"
        )

        # Generate email bodies
        html_body = self.generate_job_match_html(match)
        text_body = self.generate_job_match_text(match)

        # Create and send message
        message = self.create_message(
            to=self.to_address,
            subject=subject,
            html_body=html_body,
            text_body=text_body
        )

        return self.send_message(message)

    def send_batch_notifications(self, matches: List[Dict]) -> int:
        """Send email notifications for multiple job matches.

        Args:
            matches: List of match result dictionaries

        Returns:
            int: Number of emails sent successfully
        """
        if not self.enabled:
            return 0

        # Authenticate once
        if not self.service:
            if not self.authenticate():
                return 0

        sent_count = 0
        for match in matches:
            if self.send_job_match_notification(match):
                sent_count += 1

        return sent_count
