#!/usr/bin/env python3
"""Scheduler management script.

This script provides commands to control the job scheduler:
- start: Start the background scheduler
- stop: Stop the background scheduler
- status: Show scheduler status
- run-now: Run an immediate job search (outside of schedule)
"""

import sys
import time
import signal
from pathlib import Path

from src.scheduler.job_scheduler import JobScheduler
from src.config import get_config


def print_banner():
    """Print application banner."""
    print("=" * 80)
    print("LinkedIn Job Matcher - Scheduler Management")
    print("=" * 80)
    print()


def print_status(scheduler):
    """Print detailed scheduler status."""
    status = scheduler.get_status()

    if not status['enabled']:
        print("❌ Job scheduling is DISABLED in configuration")
        print()
        print("To enable:")
        print("1. Set scheduling.enabled: true in config.yaml")
        print("2. Configure search_keywords and other parameters")
        print()
        return

    print(f"✓ Scheduling enabled: {status['enabled']}")
    print(f"✓ Scheduler running: {status['running']}")
    print()

    print("Configuration:")
    print(f"  Interval: Every {status['interval_hours']} hours")
    if status['interval_hours'] == 24:
        print(f"  Start time: {status['start_time']} daily")
    print(f"  Search keywords: {', '.join(status['search_keywords']) if status['search_keywords'] else 'None'}")
    print(f"  Search location: {status['search_location'] or 'Default'}")
    print()

    if status['next_run']:
        print(f"Next scheduled run: {status['next_run']}")
    else:
        print("Next scheduled run: Not scheduled")
    print()

    stats = status['stats']
    print("Statistics:")
    print(f"  Total runs: {stats['total_runs']}")
    print(f"  Successful: {stats['successful_runs']}")
    print(f"  Failed: {stats['failed_runs']}")

    if stats['last_run']:
        print(f"  Last run: {stats['last_run']}")
    if stats['last_success']:
        print(f"  Last success: {stats['last_success']}")
    if stats['last_error']:
        print(f"  Last error: {stats['last_error']}")
    print()


def start_scheduler():
    """Start the scheduler in foreground mode."""
    print_banner()

    config = get_config()
    if not config.get("scheduling.enabled", False):
        print("❌ Job scheduling is disabled in configuration")
        print()
        print("To enable:")
        print("1. Set scheduling.enabled: true in config.yaml")
        print("2. Configure search_keywords and other parameters")
        print()
        return 1

    scheduler = JobScheduler()

    if not scheduler.start():
        print("❌ Failed to start scheduler")
        return 1

    print("✓ Scheduler started successfully")
    print()
    print_status(scheduler)

    print("=" * 80)
    print("Scheduler is running in foreground mode")
    print("Press Ctrl+C to stop")
    print("=" * 80)
    print()

    # Register signal handlers
    def signal_handler(sig, frame):
        print("\n\nStopping scheduler...")
        scheduler.stop()
        print("Scheduler stopped")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Keep the script running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping scheduler...")
        scheduler.stop()
        print("Scheduler stopped")
        return 0


def show_status():
    """Show scheduler status."""
    print_banner()

    scheduler = JobScheduler()
    print_status(scheduler)

    return 0


def run_now():
    """Run an immediate job search."""
    print_banner()

    config = get_config()
    if not config.get("scheduling.enabled", False):
        print("❌ Job scheduling is disabled in configuration")
        print()
        print("Note: You can still run immediate searches, but scheduler")
        print("must be configured for search parameters.")
        print()
        print("Using default search parameters...")
        print()

    scheduler = JobScheduler()

    print("Running immediate job search...")
    print("This may take several minutes...")
    print()

    scheduler.run_now()

    print()
    print("=" * 80)
    print("Immediate job search completed")
    print("=" * 80)

    return 0


def print_help():
    """Print help message."""
    print_banner()
    print("Usage: python manage_scheduler.py [command]")
    print()
    print("Commands:")
    print("  start      Start the scheduler (runs in foreground)")
    print("  status     Show scheduler status and statistics")
    print("  run-now    Run an immediate job search (outside of schedule)")
    print("  help       Show this help message")
    print()
    print("Examples:")
    print("  python manage_scheduler.py start")
    print("  python manage_scheduler.py status")
    print("  python manage_scheduler.py run-now")
    print()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print_help()
        return 1

    command = sys.argv[1].lower()

    if command == "start":
        return start_scheduler()
    elif command == "status":
        return show_status()
    elif command == "run-now":
        return run_now()
    elif command == "help":
        print_help()
        return 0
    else:
        print(f"Unknown command: {command}")
        print()
        print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
