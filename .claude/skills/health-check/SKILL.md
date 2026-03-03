Check the health and status of the LaunchPad Railway deployment by running
curl requests against the following endpoints and reporting results in a
clear summary table:

- https://launchpad-production-1ce9.up.railway.app/api/health
- https://launchpad-production-1ce9.up.railway.app/ (frontend)
- https://launchpad-production-1ce9.up.railway.app/api/jobs?limit=1
- https://launchpad-production-1ce9.up.railway.app/api/resumes
- https://launchpad-production-1ce9.up.railway.app/api/analytics/market
- https://launchpad-production-1ce9.up.railway.app/api/scheduler/schedules

For each endpoint report: HTTP status code and response time.
Parse and pretty-print the /api/health JSON so the database and gemini
status are clearly visible.
Then check Railway logs for any recent ERROR or WARNING entries:
  railway logs --service launchpad 2>&1 | grep -E "(ERROR|WARNING|exception)" | tail -10
Flag any non-200 responses or log errors prominently.
