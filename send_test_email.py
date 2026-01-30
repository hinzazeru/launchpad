#!/usr/bin/env python
"""Simple script to send a test email notification."""

from src.notifications.email_notifier import EmailNotifier

def main():
    print("=" * 80)
    print("  SENDING TEST EMAIL NOTIFICATION")
    print("=" * 80)

    # Create sample job match
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

    print("\nSample Match:")
    print(f"  Title: {sample_match['job_title']}")
    print(f"  Company: {sample_match['company']}")
    print(f"  Score: {sample_match['overall_score']:.0%}")

    # Initialize notifier
    notifier = EmailNotifier()

    if not notifier.enabled:
        print("\nX Email notifications are disabled in config.yaml")
        return

    print(f"\nSending test email to: {notifier.to_address}")

    # Authenticate
    if not notifier.authenticate():
        print("X Authentication failed")
        return

    print("* Authentication successful")

    # Send notification
    if notifier.send_job_match_notification(sample_match):
        print("* Test email sent successfully!")
        print(f"\nCheck your inbox at {notifier.to_address}")
        print("Note: Check spam folder if you don't see it in inbox")
    else:
        print("X Failed to send email")

if __name__ == "__main__":
    main()
