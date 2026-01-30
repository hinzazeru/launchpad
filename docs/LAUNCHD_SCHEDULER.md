# macOS Launchd Scheduler Setup

This document describes the launchd-based scheduling system for automated LinkedIn job searches. This approach was implemented because the Python-based scheduler (APScheduler/JobQueue) cannot run when the Mac is asleep.

## Overview

**Problem:** Python schedulers are suspended when macOS sleeps, causing missed scheduled jobs.

**Solution:** Use macOS `launchd` which can wake the Mac from sleep to run scheduled tasks.

**Behavior:**
- Wakes Mac from sleep at scheduled times (if sleeping)
- Runs the job search
- Sends Telegram notifications
- Exports to Google Sheets
- Puts Mac back to sleep only if display is off (user not active)

## Schedule

Jobs run at the following times on **weekdays only** (Monday-Friday):
- 08:00
- 12:00
- 16:00
- 20:00

Weekend runs are automatically skipped.

## Files

| File | Location | Purpose |
|------|----------|---------|
| `run_scheduled_search.sh` | `scripts/` | Shell script that runs the job search |
| `com.linkedinjobmatcher.search.plist` | `scripts/` | launchd configuration file |
| Installed plist | `~/Library/LaunchAgents/` | Active launchd job |
| `launchd_search.log` | Project root | Job execution log |
| `launchd_stdout.log` | Project root | Standard output log |
| `launchd_stderr.log` | Project root | Error log |

## Management Commands

### Check Status
```bash
launchctl list | grep linkedinjobmatcher
```
Output: `- 0 com.linkedinjobmatcher.search`
- First column: PID (- means not running)
- Second column: Last exit code (0 = success)
- Third column: Job label

### Manually Trigger a Run
```bash
launchctl start com.linkedinjobmatcher.search
```

### View Logs
```bash
# Main execution log
tail -50 "/Users/hinza/Library/CloudStorage/OneDrive-Personal/[20] Project/ClaudeProjects/LinkedInJobSearch/launchd_search.log"

# Standard output
tail -50 "/Users/hinza/Library/CloudStorage/OneDrive-Personal/[20] Project/ClaudeProjects/LinkedInJobSearch/launchd_stdout.log"

# Errors
tail -50 "/Users/hinza/Library/CloudStorage/OneDrive-Personal/[20] Project/ClaudeProjects/LinkedInJobSearch/launchd_stderr.log"
```

## Rollback Instructions

### Option 1: Temporarily Disable (Recommended First Step)

Disable without removing - can easily re-enable:

```bash
# Disable the scheduler
launchctl unload ~/Library/LaunchAgents/com.linkedinjobmatcher.search.plist

# Verify it's disabled
launchctl list | grep linkedinjobmatcher
# Should return nothing
```

To re-enable:
```bash
launchctl load ~/Library/LaunchAgents/com.linkedinjobmatcher.search.plist
```

### Option 2: Complete Removal

Remove all launchd scheduler components:

```bash
# 1. Unload the job
launchctl unload ~/Library/LaunchAgents/com.linkedinjobmatcher.search.plist

# 2. Remove the installed plist
rm ~/Library/LaunchAgents/com.linkedinjobmatcher.search.plist

# 3. Verify removal
launchctl list | grep linkedinjobmatcher
# Should return nothing
```

The script files in `scripts/` can remain - they won't run without the launchd job.

### Option 3: Delete Everything

Complete removal including scripts and logs:

```bash
# 1. Unload and remove launchd job
launchctl unload ~/Library/LaunchAgents/com.linkedinjobmatcher.search.plist 2>/dev/null
rm ~/Library/LaunchAgents/com.linkedinjobmatcher.search.plist

# 2. Remove scripts
rm -rf "/Users/hinza/Library/CloudStorage/OneDrive-Personal/[20] Project/ClaudeProjects/LinkedInJobSearch/scripts/"

# 3. Remove logs
rm "/Users/hinza/Library/CloudStorage/OneDrive-Personal/[20] Project/ClaudeProjects/LinkedInJobSearch/launchd_search.log"
rm "/Users/hinza/Library/CloudStorage/OneDrive-Personal/[20] Project/ClaudeProjects/LinkedInJobSearch/launchd_stdout.log"
rm "/Users/hinza/Library/CloudStorage/OneDrive-Personal/[20] Project/ClaudeProjects/LinkedInJobSearch/launchd_stderr.log"
```

## Reinstallation

If you've removed the scheduler and want to reinstall:

```bash
cd "/Users/hinza/Library/CloudStorage/OneDrive-Personal/[20] Project/ClaudeProjects/LinkedInJobSearch"

# Copy plist to LaunchAgents
cp scripts/com.linkedinjobmatcher.search.plist ~/Library/LaunchAgents/

# Load the job
launchctl load ~/Library/LaunchAgents/com.linkedinjobmatcher.search.plist

# Verify
launchctl list | grep linkedinjobmatcher
```

## Troubleshooting

### Job Not Running

1. Check if loaded:
   ```bash
   launchctl list | grep linkedinjobmatcher
   ```

2. Check logs for errors:
   ```bash
   tail -20 "/Users/hinza/Library/CloudStorage/OneDrive-Personal/[20] Project/ClaudeProjects/LinkedInJobSearch/launchd_stderr.log"
   ```

3. Test manually:
   ```bash
   launchctl start com.linkedinjobmatcher.search
   ```

### Power/Battery Concerns

If you notice excessive battery drain or the Mac waking too often:

1. **Check wake reasons:**
   ```bash
   pmset -g log | grep -i wake | tail -20
   ```

2. **Temporarily disable:**
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.linkedinjobmatcher.search.plist
   ```

3. **Reduce frequency** by editing the plist to fewer times per day

### Mac Not Going Back to Sleep

The script only puts Mac to sleep if the display is off. If the display is on (user active), the Mac follows its normal sleep schedule.

To force sleep after jobs regardless of display state, edit `run_scheduled_search.sh` and replace the display check with:
```bash
# Always sleep after job
sleep 30
pmset sleepnow
```

**Warning:** This may interrupt active work if you're using the computer.

## Modifying the Schedule

To change scheduled times:

1. Edit the plist file:
   ```bash
   nano "/Users/hinza/Library/CloudStorage/OneDrive-Personal/[20] Project/ClaudeProjects/LinkedInJobSearch/scripts/com.linkedinjobmatcher.search.plist"
   ```

2. Modify the `StartCalendarInterval` section. Each `<dict>` block is one scheduled time:
   ```xml
   <dict>
       <key>Hour</key>
       <integer>9</integer>  <!-- Change hour here -->
       <key>Minute</key>
       <integer>30</integer> <!-- Change minute here -->
   </dict>
   ```

3. Reload:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.linkedinjobmatcher.search.plist
   cp "/Users/hinza/Library/CloudStorage/OneDrive-Personal/[20] Project/ClaudeProjects/LinkedInJobSearch/scripts/com.linkedinjobmatcher.search.plist" ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.linkedinjobmatcher.search.plist
   ```

## Comparison: launchd vs Python Scheduler

| Feature | launchd | Python (JobQueue) |
|---------|---------|-------------------|
| Runs when Mac sleeps | ✅ Yes (wakes Mac) | ❌ No (suspended) |
| Telegram bot commands | ❌ No | ✅ Yes |
| Real-time interaction | ❌ No | ✅ Yes |
| System integration | ✅ Native macOS | ❌ Separate process |
| Power efficient | ✅ Yes | ❌ Keeps process running |

**Recommendation:** Use launchd for automated scheduling, keep Telegram bot running for manual commands (`/search`, `/status`, `/matches`, etc.)

## Related Documentation

- [Scheduler Overview](SCHEDULER.md)
- [Telegram Bot](TELEGRAM_BOT.md)
- [Architecture](ARCHITECTURE.md)
