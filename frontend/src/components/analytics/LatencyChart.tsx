import { useApiLatency } from '@/services/api';
import { motion } from 'framer-motion';
import { Gauge } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

interface LatencyData {
  name: string;
  p50: number;
  p90: number;
  p99: number;
  count: number;
}

const API_LABELS: Record<string, string> = {
  gemini_rerank: 'Gemini Rerank',
  gemini_suggestions: 'Gemini Suggestions',
  apify_search: 'Apify Search',
  sheets_export: 'Sheets Export',
};

const API_COLORS: Record<string, { p50: string; p90: string }> = {
  gemini_rerank: { p50: '#8b5cf6', p90: '#c4b5fd' },
  gemini_suggestions: { p50: '#6366f1', p90: '#a5b4fc' },
  apify_search: { p50: '#3b82f6', p90: '#93c5fd' },
  sheets_export: { p50: '#10b981', p90: '#6ee7b7' },
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function LatencyChart() {
  const { data, isLoading, error } = useApiLatency(7);

  if (isLoading) {
    return (
      <Card className="border-border/50">
        <CardHeader className="pb-2">
          <div className="h-5 w-40 bg-muted animate-pulse rounded" />
          <div className="h-4 w-48 mt-1 bg-muted animate-pulse rounded" />
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="space-y-2">
                <div className="h-4 w-32 bg-muted animate-pulse rounded" />
                <div className="h-6 bg-muted animate-pulse rounded" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card className="border-border/50">
        <CardContent className="pt-6">
          <div className="text-center text-muted-foreground py-8">
            Failed to load API latency data
          </div>
        </CardContent>
      </Card>
    );
  }

  // Convert data to array and find max for scaling
  const latencies: LatencyData[] = Object.entries(data).map(([name, detail]) => ({
    name,
    ...detail,
  }));

  if (latencies.length === 0) {
    return (
      <Card className="border-border/50">
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <Gauge className="w-4 h-4 text-muted-foreground" />
            API Latency
          </CardTitle>
          <CardDescription>Response time percentiles (p50/p90)</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center text-muted-foreground py-8">
            No API latency data available
          </div>
        </CardContent>
      </Card>
    );
  }

  // Sort by p90 descending
  latencies.sort((a, b) => b.p90 - a.p90);

  // Find max p90 for scaling bars
  const maxP90 = Math.max(...latencies.map(l => l.p90));

  return (
    <Card className="border-border/50 overflow-hidden">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold flex items-center gap-2">
          <Gauge className="w-4 h-4 text-muted-foreground" />
          API Latency
        </CardTitle>
        <CardDescription>Response time percentiles (7 days)</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {latencies.map((item, idx) => {
            const colors = API_COLORS[item.name] || { p50: '#6b7280', p90: '#9ca3af' };
            const p50Width = (item.p50 / maxP90) * 100;
            const p90Width = (item.p90 / maxP90) * 100;

            return (
              <div key={item.name} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{API_LABELS[item.name] || item.name}</span>
                  <span className="text-xs text-muted-foreground">{item.count} calls</span>
                </div>

                {/* Stacked bar showing p50 and p90 */}
                <div className="h-6 bg-muted/30 rounded-md overflow-hidden relative">
                  {/* p90 bar (background) */}
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${p90Width}%` }}
                    transition={{ duration: 0.5, delay: idx * 0.1 }}
                    className="absolute inset-y-0 left-0 rounded-md"
                    style={{ backgroundColor: colors.p90 }}
                  />
                  {/* p50 bar (foreground) */}
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${p50Width}%` }}
                    transition={{ duration: 0.5, delay: idx * 0.1 + 0.1 }}
                    className="absolute inset-y-0 left-0 rounded-md"
                    style={{ backgroundColor: colors.p50 }}
                  />
                  {/* Labels */}
                  <div className="absolute inset-0 flex items-center justify-between px-2 text-xs font-medium">
                    <span className="text-white drop-shadow-sm">
                      p50: {formatDuration(item.p50)}
                    </span>
                    <span className="text-foreground/70">
                      p90: {formatDuration(item.p90)}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Legend */}
        <div className="mt-4 pt-4 border-t border-border/50 flex items-center justify-center gap-6 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm bg-violet-500" />
            <span>p50 (median)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm bg-violet-300" />
            <span>p90</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
