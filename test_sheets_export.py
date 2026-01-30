#!/usr/bin/env python3
"""Demo script for testing Google Sheets export functionality.

This script:
1. Authenticates with Google Sheets API
2. Initializes spreadsheet with headers and formatting
3. Exports sample job matches
4. Displays spreadsheet URL for verification
"""

from datetime import datetime
from src.integrations.sheets_connector import SheetsConnector
from src.config import get_config


def create_sample_matches():
    """Create sample job matches for testing."""
    return [
        {
            'job_title': 'Senior Product Manager - AI/ML',
            'company': 'TechCorp Inc.',
            'location': 'San Francisco, CA (Remote)',
            'url': 'https://www.linkedin.com/jobs/view/12345',
            'overall_score': 0.92,
            'skills_score': 0.95,
            'experience_score': 0.88,
            'matching_skills': [
                'Product Management', 'Product Strategy', 'Agile', 'Scrum',
                'SQL', 'Data Analysis', 'A/B Testing', 'User Research',
                'Stakeholder Management', 'Roadmap Planning', 'KPIs'
            ],
            'skill_gaps': ['Machine Learning', 'TensorFlow'],
            'match_id': 1,
            'resume_id': 1,
        },
        {
            'job_title': 'Product Manager - SaaS Platform',
            'company': 'CloudSolutions Ltd',
            'location': 'New York, NY',
            'url': 'https://www.linkedin.com/jobs/view/23456',
            'overall_score': 0.85,
            'skills_score': 0.82,
            'experience_score': 0.88,
            'matching_skills': [
                'Product Management', 'SaaS', 'API Management',
                'Agile', 'Backlog Management', 'Cloud Platforms',
                'Product Analytics', 'Go-to-Market Strategy'
            ],
            'skill_gaps': ['AWS', 'Kubernetes', 'Microservices'],
            'match_id': 2,
            'resume_id': 1,
        },
        {
            'job_title': 'Technical Product Manager',
            'company': 'StartupXYZ',
            'location': 'Austin, TX (Hybrid)',
            'url': 'https://www.linkedin.com/jobs/view/34567',
            'overall_score': 0.78,
            'skills_score': 0.75,
            'experience_score': 0.82,
            'matching_skills': [
                'Technical Product Management', 'Product Strategy',
                'Agile', 'Sprint Planning', 'User Stories',
                'Mobile Products', 'Web Products'
            ],
            'skill_gaps': ['React Native', 'GraphQL', 'Docker'],
            'match_id': 3,
            'resume_id': 1,
        },
        {
            'job_title': 'Product Manager - E-commerce',
            'company': 'RetailTech',
            'location': 'Seattle, WA',
            'url': 'https://www.linkedin.com/jobs/view/45678',
            'overall_score': 0.72,
            'skills_score': 0.70,
            'experience_score': 0.75,
            'matching_skills': [
                'Product Management', 'Product Analytics', 'A/B Testing',
                'User Research', 'Feature Prioritization', 'OKRs'
            ],
            'skill_gaps': ['E-commerce Platforms', 'Payment Systems', 'Conversion Optimization'],
            'match_id': 4,
            'resume_id': 1,
        },
        {
            'job_title': 'Junior Product Manager',
            'company': 'GrowthCo',
            'location': 'Boston, MA',
            'url': 'https://www.linkedin.com/jobs/view/56789',
            'overall_score': 0.65,
            'skills_score': 0.60,
            'experience_score': 0.70,
            'matching_skills': [
                'Product Management', 'Agile', 'User Stories',
                'Market Research', 'Customer Development'
            ],
            'skill_gaps': ['SQL', 'Data Analysis', 'Product Analytics', 'Roadmap Planning'],
            'match_id': 5,
            'resume_id': 1,
        }
    ]


def main():
    """Run the Sheets export demo."""
    print("=" * 80)
    print("Google Sheets Export Demo")
    print("=" * 80)
    print()

    # Load configuration
    config = get_config()

    # Check if Sheets is enabled
    if not config.get("sheets.enabled", False):
        print("❌ Google Sheets integration is NOT enabled in config.yaml")
        print()
        print("To enable:")
        print("1. Set sheets.enabled: true in config.yaml")
        print("2. Add your spreadsheet_id (get from spreadsheet URL)")
        print("3. Ensure credentials.json is in the project root")
        print()
        return

    print("✓ Google Sheets integration is enabled")
    print()

    # Get spreadsheet ID from config
    spreadsheet_id = config.get("sheets.spreadsheet_id")
    if not spreadsheet_id or spreadsheet_id == "YOUR_SPREADSHEET_ID_HERE":
        print("❌ Spreadsheet ID not configured")
        print()
        print("To configure:")
        print("1. Create a new Google Spreadsheet")
        print("2. Copy the ID from the URL:")
        print("   https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit")
        print("3. Add it to config.yaml under sheets.spreadsheet_id")
        print()
        return

    print(f"✓ Spreadsheet ID: {spreadsheet_id}")
    print()

    # Initialize connector
    print("Initializing Sheets connector...")
    connector = SheetsConnector()

    # Authenticate
    print("Authenticating with Google Sheets API...")
    print("(A browser window will open if this is your first time)")
    print()

    if not connector.authenticate():
        print("❌ Authentication failed")
        print()
        print("Troubleshooting:")
        print("1. Ensure credentials.json exists in project root")
        print("2. Check that Google Sheets API is enabled in Google Cloud Console")
        print("3. Verify OAuth consent screen is configured")
        print()
        return

    print("✓ Authentication successful")
    print()

    # Initialize spreadsheet
    print("Initializing spreadsheet with headers and formatting...")
    if connector.initialize_spreadsheet():
        print("✓ Spreadsheet initialized successfully")
        print()
        print("Formatting applied:")
        print("  • Bold blue header row with white text")
        print("  • Frozen header row")
        print("  • Data rows: black text, no background color")
        print()
    else:
        print("❌ Failed to initialize spreadsheet")
        return

    # Create sample matches
    print("Creating sample job matches...")
    matches = create_sample_matches()
    print(f"✓ Created {len(matches)} sample matches")
    print()

    # Display matches
    print("Sample Matches:")
    print("-" * 80)
    for match in matches:
        score_pct = int(match['overall_score'] * 100)
        print(f"  {match['job_title']}")
        print(f"  Company: {match['company']}")
        print(f"  Score: {score_pct}% (Overall: {score_pct}%, Skills: {int(match['skills_score']*100)}%, Experience: {int(match['experience_score']*100)}%)")
        print()
    print()

    # Export matches
    export_threshold = config.get("sheets.export_min_score", 0.7)
    print(f"Exporting matches with score ≥ {int(export_threshold * 100)}%...")

    exported_count = connector.export_matches_batch(matches)

    if exported_count > 0:
        print(f"✓ Successfully exported {exported_count} matches")
        print()

        # Display spreadsheet URL
        sheet_name = config.get("sheets.sheet_name", "Job Matches")
        spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

        print("=" * 80)
        print("View your results:")
        print(f"📊 {spreadsheet_url}")
        print("=" * 80)
        print()

        print("What to check:")
        print("  1. Header row should be bold with blue background and white text")
        print("  2. Data rows should have black text with no background color")
        print("  3. Header row should stay visible when scrolling")
        print(f"  4. Look for the '{sheet_name}' tab if multiple sheets exist")
        print()

        print("✓ Google Sheets export demo completed successfully!")
    else:
        print("❌ No matches were exported")
        print()
        print(f"Possible reasons:")
        print(f"  • All matches were below the threshold ({int(export_threshold * 100)}%)")
        print(f"  • There was an error during export")
        print()

    print()


if __name__ == '__main__':
    main()
