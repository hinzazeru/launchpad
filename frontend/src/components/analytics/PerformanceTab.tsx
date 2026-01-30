import {
  usePerformanceSummary,
  usePerformanceTimeline,
  useRecentSearches,
} from '@/services/api';
import { motion } from 'framer-motion';
import {
  Clock,
  CheckCircle2,
  Server,
  Zap,
  TrendingUp,
  AlertCircle,
  Search,
  User,
  CalendarClock,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { StageBreakdown } from './StageBreakdown';
import { LatencyChart } from './LatencyChart';

// Format date for display
function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// Format duration for display
function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return '--';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

// Format date and time (e.g., "Jan 26, 9:38 PM")
function formatDateTime(isoString: string): string {
  if (!isoString) return '--';
  const date = new Date(isoString);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true
  });
}

export function PerformanceTab() {
  const { data: performance, isLoading: summaryLoading, error: summaryError } = usePerformanceSummary();
  const { data: timeline, isLoading: timelineLoading } = usePerformanceTimeline(30);
  const { data: recentSearches, isLoading: searchesLoading } = useRecentSearches(10);

  if (summaryLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-4">
        <motion.div
          className="w-12 h-12 rounded-full border-2 border-primary border-t-transparent"
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
        />
        <p className="text-muted-foreground">Loading performance metrics...</p>
      </div>
    );
  }

  if (summaryError) {
    return (
      <div className="p-8 text-center text-destructive bg-destructive/10 rounded-lg">
        <AlertCircle className="w-8 h-8 mx-auto mb-2" />
        <p>Failed to load performance metrics.</p>
      </div>
    );
  }

  if (!performance) return null;

  // Format timeline data
  const timelineData = timeline?.points.map((p) => ({
    date: formatDate(p.date),
    duration: p.avg_ms / 1000, // Convert to seconds
    count: p.count,
  })) || [];

  const hasTimelineData = timelineData.some((p) => p.duration > 0);

  return (
    <div className="space-y-6">
      {/* Top Cards */}
      <motion.div
        className="grid grid-cols-2 lg:grid-cols-4 gap-4"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex items-center gap-3 p-4 rounded-lg bg-card border shadow-sm">
          <div className="p-2 rounded-md bg-blue-500/10">
            <Clock className="w-5 h-5 text-blue-500" />
          </div>
          <div>
            <p className="text-2xl font-bold">
              {(performance.avg_search_duration_ms / 1000).toFixed(1)}s
            </p>
            <p className="text-xs text-muted-foreground">Avg Search Time</p>
          </div>
        </div>

        <div className="flex items-center gap-3 p-4 rounded-lg bg-card border shadow-sm">
          <div className="p-2 rounded-md bg-violet-500/10">
            <Zap className="w-5 h-5 text-violet-500" />
          </div>
          <div>
            <p className="text-2xl font-bold">
              {(performance.avg_gemini_latency_ms / 1000).toFixed(1)}s
            </p>
            <p className="text-xs text-muted-foreground">Avg AI Response</p>
          </div>
        </div>

        <div className="flex items-center gap-3 p-4 rounded-lg bg-card border shadow-sm">
          <div className="p-2 rounded-md bg-emerald-500/10">
            <CheckCircle2 className="w-5 h-5 text-emerald-500" />
          </div>
          <div>
            <p className="text-2xl font-bold">
              {Math.round(performance.search_success_rate * 100)}%
            </p>
            <p className="text-xs text-muted-foreground">Success Rate</p>
          </div>
        </div>

        <div className="flex items-center gap-3 p-4 rounded-lg bg-card border shadow-sm">
          <div className="p-2 rounded-md bg-orange-500/10">
            <Server className="w-5 h-5 text-orange-500" />
          </div>
          <div>
            <p className="text-2xl font-bold">{performance.total_searches_30d}</p>
            <p className="text-xs text-muted-foreground">Searches (30d)</p>
          </div>
        </div>
      </motion.div>

      {/* Duration Timeline Chart */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-muted-foreground" />
              Search Duration Trend
            </CardTitle>
            <CardDescription>Average search duration over 30 days</CardDescription>
          </CardHeader>
          <CardContent>
            {timelineLoading ? (
              <div className="h-[200px] flex items-center justify-center">
                <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
              </div>
            ) : !hasTimelineData ? (
              <div className="h-[200px] flex items-center justify-center text-muted-foreground">
                Run some searches to see duration trends
              </div>
            ) : (
              <div className="h-[200px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={timelineData}>
                    <XAxis
                      dataKey="date"
                      tickLine={false}
                      axisLine={false}
                      tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                    />
                    <YAxis
                      tickLine={false}
                      axisLine={false}
                      tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                      tickFormatter={(v) => `${v}s`}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--popover))',
                        borderColor: 'hsl(var(--border))',
                        borderRadius: '6px',
                        fontSize: '12px',
                      }}
                      formatter={(value) => [`${Number(value).toFixed(1)}s`, 'Duration']}
                    />
                    <Line
                      type="monotone"
                      dataKey="duration"
                      stroke="hsl(var(--primary))"
                      strokeWidth={2}
                      dot={{ fill: 'hsl(var(--primary))', strokeWidth: 0, r: 3 }}
                      activeDot={{ r: 5 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>

      {/* Stage Breakdown and API Latency */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <motion.div
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
        >
          <StageBreakdown />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: 10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3 }}
        >
          <LatencyChart />
        </motion.div>
      </div>

      {/* Recent Searches Table */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Search className="w-4 h-4 text-muted-foreground" />
              Recent Searches
            </CardTitle>
            <CardDescription>Latest search operations and their results</CardDescription>
          </CardHeader>
          <CardContent>
            {searchesLoading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-12 bg-muted animate-pulse rounded" />
                ))}
              </div>
            ) : !recentSearches?.searches.length ? (
              <div className="text-center text-muted-foreground py-8">
                No recent searches found
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border/50">
                      <th className="text-left py-2 px-2 font-medium text-muted-foreground">Time</th>
                      <th className="text-center py-2 px-2 font-medium text-muted-foreground">Source</th>
                      <th className="text-right py-2 px-2 font-medium text-muted-foreground">Duration</th>
                      <th className="text-right py-2 px-2 font-medium text-muted-foreground">Jobs</th>
                      <th className="text-right py-2 px-2 font-medium text-muted-foreground">Matches</th>
                      <th className="text-right py-2 px-2 font-medium text-muted-foreground">High</th>
                      <th className="text-left py-2 px-2 font-medium text-muted-foreground">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentSearches.searches.map((search) => (
                      <tr
                        key={search.search_id}
                        className="border-b border-border/30 hover:bg-muted/30 transition-colors"
                      >
                        <td className="py-2 px-2 text-muted-foreground whitespace-nowrap">
                          {formatDateTime(search.created_at)}
                        </td>
                        <td className="py-2 px-2 text-center">
                          {search.trigger_source === 'scheduled' ? (
                            <span className="inline-flex items-center gap-1 text-blue-500" title="Scheduled run">
                              <CalendarClock className="w-4 h-4" />
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-muted-foreground" title="Manual run">
                              <User className="w-4 h-4" />
                            </span>
                          )}
                        </td>
                        <td className="py-2 px-2 text-right font-mono">
                          {formatDuration(search.total_duration_ms)}
                        </td>
                        <td className="py-2 px-2 text-right">{search.jobs_fetched}</td>
                        <td className="py-2 px-2 text-right">{search.jobs_matched}</td>
                        <td className="py-2 px-2 text-right font-medium text-emerald-500">
                          {search.high_matches}
                        </td>
                        <td className="py-2 px-2">
                          {search.status === 'success' ? (
                            <span className="inline-flex items-center gap-1 text-emerald-500">
                              <CheckCircle2 className="w-3 h-3" />
                              Success
                            </span>
                          ) : (
                            <span
                              className="inline-flex items-center gap-1 text-destructive cursor-help"
                              title={search.error_message || 'Unknown error'}
                            >
                              <AlertCircle className="w-3 h-3" />
                              {search.status}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
