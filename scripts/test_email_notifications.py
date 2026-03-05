#!/usr/bin/env python
"""Demo script to test email notifications with Gmail OAuth 2.0."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from src.notifications.email_notifier import EmailNotifier


def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_setup_instructions():
    """Print Gmail OAuth setup instructions."""
    print("""
To use Gmail notifications, you need to set up OAuth 2.0 credentials:

1. Go to Google Cloud Console:
   https://console.cloud.google.com/

2. Create a new project (or select existing)

3. Enable Gmail API:
   https://console.cloud.google.com/apis/library/gmail.googleapis.com

4. Create OAuth 2.0 credentials:
   - Go to APIs & Services > Credentials
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Desktop app"
   - Download the credentials JSON file
   - Save it as "credentials.json" in the project root

5. Update config.yaml:
   - Set email.enabled: true
   - Set email.from_address: your-email@gmail.com
   - Set email.to_address: your-email@gmail.com
   - Adjust email.notify_min_score if needed (default: 0.7)

6. Run this script again

The first time you authenticate, a browser window will open asking you to
authorize the application. After that, a token.json file will be created
and you won't need to authorize again (unless you revoke access).
""")


def main():
    """Run email notification demo."""

    print_header("EMAIL NOTIFICATION DEMO")

    # Check if email notifications are enabled
    notifier = EmailNotifier()

    if not notifier.enabled:
        print("X Email notifications are disabled in config.yaml")
        print_setup_instructions()
        sys.exit(1)

    print("* Email notifications are enabled")
    print(f"* From: {notifier.from_address}")
    print(f"* To: {notifier.to_address}")
    print(f"* Notification threshold: {notifier.notify_min_score:.0%}")

    # Test authentication
    print_header("Step 1: Authenticate with Gmail")
    print("Attempting to authenticate...")

    if notifier.authenticate():
        print("* Authentication successful!")
    else:
        print("X Authentication failed")
        print_setup_instructions()
        sys.exit(1)

    # Create sample job match
    print_header("Step 2: Create Sample Job Match")

    sample_match = {
        'job_title': 'Senior Product Manager',
        'company': 'TechCorp',
        'location': 'San Francisco, CA',
        'url': 'https://www.linkedin.com/jobs/view/example-job-123',
        'overall_score': 0.85,
        'skills_score': 0.9,
        'experience_score': 0.8,
        'matching_skills': [
            'Product Management',
            'Product Strategy',
            'Roadmap Planning',
            'Agile',
            'Scrum',
            'Data Analysis',
            'SQL',
            'Stakeholder Management'
        ],
        'skill_gaps': [
            'Machine Learning',
            'AWS',
            'Docker'
        ],
    }

    print("Sample match created:")
    print(f"  Title:          {sample_match['job_title']}")
    print(f"  Company:        {sample_match['company']}")
    print(f"  Overall Score:  {sample_match['overall_score']:.0%}")
    print(f"  Skills Score:   {sample_match['skills_score']:.0%}")
    print(f"  Experience:     {sample_match['experience_score']:.0%}")

    # Generate email preview
    print_header("Step 3: Email Preview")

    html_preview = notifier.generate_job_match_html(sample_match)
    text_preview = notifier.generate_job_match_text(sample_match)

    print("Plain text preview:")
    print("-" * 80)
    print(text_preview[:400] + "...")
    print("-" * 80)

    print(f"\nHTML email generated ({len(html_preview)} characters)")

    # Ask user if they want to send the email
    print_header("Step 4: Send Test Email")

    print("This will send a test email to:", notifier.to_address)
    response = input("\nDo you want to send the test email? (yes/no): ").strip().lower()

    if response not in ['yes', 'y']:
        print("\nTest email cancelled.")
        sys.exit(0)

    # Send the email
    print("\nSending email...")

    if notifier.send_job_match_notification(sample_match):
        print("* Email sent successfully!")
        print(f"\nCheck your inbox at {notifier.to_address}")
        print("Note: The email might be in your spam folder initially")
    else:
        print("X Failed to send email")
        sys.exit(1)

    # Test batch notification
    print_header("Step 5: Batch Notification Test (Optional)")

    response = input("Do you want to test batch notifications (3 emails)? (yes/no): ").strip().lower()

    if response in ['yes', 'y']:
        # Create sample matches with different scores
        matches = [
            {**sample_match, 'job_title': 'Product Manager - AI/ML', 'overall_score': 0.92, 'company': 'Google'},
            {**sample_match, 'job_title': 'Product Manager - Platform', 'overall_score': 0.78, 'company': 'Meta'},
            {**sample_match, 'job_title': 'Associate Product Manager', 'overall_score': 0.72, 'company': 'Amazon'},
        ]

        print(f"\nSending {len(matches)} batch notifications...")
        sent_count = notifier.send_batch_notifications(matches)

        print(f"* Sent {sent_count} out of {len(matches)} emails successfully")

    print_header("DEMO COMPLETED")

    print("Email notification system is working correctly!")
    print("\nNext steps:")
    print("  - Integrate email notifications into your job matching workflow")
    print("  - Adjust notify_min_score in config.yaml to control which matches trigger emails")
    print("  - Set up scheduled job searches (Task 8) for automated notifications")
    print()


if __name__ == "__main__":
    main()
