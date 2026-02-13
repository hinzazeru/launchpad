import { useScheduledSearchSummary } from '@/services/api';
import { motion } from 'framer-motion';
import {
  CalendarClock,
  CheckCircle2,
  AlertCircle,
  Bot,
  SkipForward,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatDateTime(isoString: string | null): string {
  if (!isoString) return '--';
  const date = new Date(isoString);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

export function ScheduledSearchSummary() {
  const { data, isLoading } = useScheduledSearchSummary(30);

  // Don't render anything if no scheduled searches exist
  if (!isLoading && (!data || data.schedules.length === 0)) {
    return null;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15 }}
    >
      <Card className="border-border/50">
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <CalendarClock className="w-4 h-4 text-muted-foreground" />
            Scheduled Search Performance
          </CardTitle>
          <CardDescription>
            Per-schedule metrics over the last 30 days
            {data && (
              <span className="ml-2 text-xs">
                ({data.total_scheduled_runs_30d} runs, {Math.round(data.overall_success_rate * 100)}% success)
              </span>
            )}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {[1, 2].map((i) => (
                <div key={i} className="h-12 bg-muted animate-pulse rounded" />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/50">
                    <th className="text-left py-2 px-2 font-medium text-muted-foreground">Name</th>
                    <th className="text-right py-2 px-2 font-medium text-muted-foreground">Runs</th>
                    <th className="text-right py-2 px-2 font-medium text-muted-foreground">Success</th>
                    <th className="text-right py-2 px-2 font-medium text-muted-foreground">Avg Duration</th>
                    <th className="text-right py-2 px-2 font-medium text-muted-foreground">Avg High</th>
                    <th className="text-center py-2 px-2 font-medium text-muted-foreground">AI Rate</th>
                    <th className="text-right py-2 px-2 font-medium text-muted-foreground">Skipped</th>
                    <th className="text-left py-2 px-2 font-medium text-muted-foreground">Last Run</th>
                  </tr>
                </thead>
                <tbody>
                  {data!.schedules.map((schedule) => {
                    const successRate = schedule.total_runs > 0
                      ? Math.round((schedule.successful_runs / schedule.total_runs) * 100)
                      : 0;

                    return (
                      <tr
                        key={schedule.schedule_id}
                        className="border-b border-border/30 hover:bg-muted/30 transition-colors"
                      >
                        <td className="py-2 px-2 font-medium max-w-[160px] truncate" title={schedule.schedule_name}>
                          {schedule.schedule_name}
                        </td>
                        <td className="py-2 px-2 text-right">{schedule.total_runs}</td>
                        <td className="py-2 px-2 text-right">
                          <span className={`font-mono ${
                            successRate >= 90 ? 'text-emerald-500' :
                            successRate >= 70 ? 'text-amber-500' : 'text-destructive'
                          }`}>
                            {successRate}%
                          </span>
                        </td>
                        <td className="py-2 px-2 text-right font-mono">
                          {formatDuration(schedule.avg_duration_ms)}
                        </td>
                        <td className="py-2 px-2 text-right font-medium text-emerald-500">
                          {schedule.avg_high_matches.toFixed(1)}
                        </td>
                        <td className="py-2 px-2 text-center">
                          {schedule.avg_gemini_success_rate != null ? (
                            <span className="inline-flex items-center gap-1" title={`Gemini success rate: ${Math.round(schedule.avg_gemini_success_rate * 100)}%`}>
                              <Bot className="w-3 h-3 text-violet-500" />
                              <span className="text-xs font-mono text-violet-500">
                                {Math.round(schedule.avg_gemini_success_rate * 100)}%
                              </span>
                            </span>
                          ) : (
                            <span className="text-xs text-muted-foreground">--</span>
                          )}
                        </td>
                        <td className="py-2 px-2 text-right">
                          {schedule.total_jobs_skipped > 0 ? (
                            <span className="inline-flex items-center gap-1 text-muted-foreground" title={`${schedule.total_jobs_skipped} jobs skipped via smart rematch`}>
                              <SkipForward className="w-3 h-3" />
                              {schedule.total_jobs_skipped}
                            </span>
                          ) : (
                            <span className="text-xs text-muted-foreground">0</span>
                          )}
                        </td>
                        <td className="py-2 px-2 whitespace-nowrap">
                          {schedule.last_status === 'success' ? (
                            <span className="inline-flex items-center gap-1 text-emerald-500" title={formatDateTime(schedule.last_run_at)}>
                              <CheckCircle2 className="w-3 h-3" />
                              <span className="text-xs">{formatDateTime(schedule.last_run_at)}</span>
                            </span>
                          ) : schedule.last_status === 'error' ? (
                            <span className="inline-flex items-center gap-1 text-destructive" title={formatDateTime(schedule.last_run_at)}>
                              <AlertCircle className="w-3 h-3" />
                              <span className="text-xs">{formatDateTime(schedule.last_run_at)}</span>
                            </span>
                          ) : (
                            <span className="text-xs text-muted-foreground">
                              {formatDateTime(schedule.last_run_at)}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
