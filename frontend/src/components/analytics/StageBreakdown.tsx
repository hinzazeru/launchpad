import { usePerformanceBreakdown } from '@/services/api';
import { motion } from 'framer-motion';
import { Layers } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

interface StageData {
  name: string;
  avg_ms: number;
  pct: number;
  color: string;
}

const STAGE_COLORS: Record<string, string> = {
  initialize: '#6366f1', // indigo
  fetch: '#3b82f6',      // blue
  import: '#10b981',     // emerald
  match: '#f59e0b',      // amber
  export: '#8b5cf6',     // violet
};

const STAGE_LABELS: Record<string, string> = {
  initialize: 'Initialize',
  fetch: 'Fetch Jobs',
  import: 'Import',
  match: 'Match & Score',
  export: 'Export',
};

export function StageBreakdown() {
  const { data, isLoading, error } = usePerformanceBreakdown(7);

  if (isLoading) {
    return (
      <Card className="border-border/50">
        <CardHeader className="pb-2">
          <div className="h-5 w-40 bg-muted animate-pulse rounded" />
          <div className="h-4 w-56 mt-1 bg-muted animate-pulse rounded" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="h-4 w-24 bg-muted animate-pulse rounded" />
                <div className="flex-1 h-6 bg-muted animate-pulse rounded" />
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
            Failed to load stage breakdown
          </div>
        </CardContent>
      </Card>
    );
  }

  // Convert stages object to sorted array
  const stageOrder = ['initialize', 'fetch', 'import', 'match', 'export'];
  const stages: StageData[] = stageOrder
    .filter(key => data.stages[key])
    .map(key => ({
      name: key,
      avg_ms: data.stages[key].avg_ms,
      pct: data.stages[key].pct,
      color: STAGE_COLORS[key] || '#6b7280',
    }));

  const hasData = stages.some(s => s.avg_ms > 0);

  if (!hasData) {
    return (
      <Card className="border-border/50">
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <Layers className="w-4 h-4 text-muted-foreground" />
            Stage Breakdown
          </CardTitle>
          <CardDescription>Time spent per pipeline stage</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center text-muted-foreground py-8">
            Run some searches to see stage breakdown
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border/50 overflow-hidden">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold flex items-center gap-2">
          <Layers className="w-4 h-4 text-muted-foreground" />
          Stage Breakdown
        </CardTitle>
        <CardDescription>Time spent per pipeline stage (7 days)</CardDescription>
      </CardHeader>
      <CardContent>
        {/* Stacked Bar */}
        <div className="mb-4">
          <div className="h-8 rounded-md overflow-hidden flex">
            {stages.map((stage, idx) => (
              <motion.div
                key={stage.name}
                initial={{ width: 0 }}
                animate={{ width: `${stage.pct}%` }}
                transition={{ duration: 0.5, delay: idx * 0.1 }}
                style={{ backgroundColor: stage.color }}
                className="h-full relative group"
                title={`${STAGE_LABELS[stage.name]}: ${stage.pct.toFixed(1)}%`}
              >
                {stage.pct > 10 && (
                  <span className="absolute inset-0 flex items-center justify-center text-xs font-medium text-white">
                    {stage.pct.toFixed(0)}%
                  </span>
                )}
              </motion.div>
            ))}
          </div>
        </div>

        {/* Legend */}
        <div className="space-y-2">
          {stages.map((stage) => (
            <div key={stage.name} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-sm"
                  style={{ backgroundColor: stage.color }}
                />
                <span className="text-muted-foreground">{STAGE_LABELS[stage.name]}</span>
              </div>
              <div className="flex items-center gap-4">
                <span className="font-mono text-xs text-muted-foreground">
                  {stage.avg_ms < 1000
                    ? `${Math.round(stage.avg_ms)}ms`
                    : `${(stage.avg_ms / 1000).toFixed(1)}s`}
                </span>
                <span className="font-medium w-12 text-right">{stage.pct.toFixed(1)}%</span>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
