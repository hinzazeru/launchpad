import { motion } from 'framer-motion';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  CartesianGrid,
} from 'recharts';
import { Bot } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useGeminiUsage } from '@/services/api';
import { formatDateShort } from '@/lib/utils';

const USAGE_COLORS = {
  matching: '#8b5cf6',    // violet-500
  rerank: '#3b82f6',      // blue-500
  suggestions: '#10b981', // emerald-500
};

// Custom tooltip for the chart
const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload) return null;

  const total = payload.reduce((sum: number, entry: any) => sum + (entry.value || 0), 0);

  return (
    <div className="bg-popover border border-border rounded-lg shadow-lg p-3 text-sm">
      <p className="font-semibold mb-2">{label}</p>
      <div className="space-y-1">
        {payload.map((entry: any) => (
          <div key={entry.dataKey} className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-sm"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-muted-foreground">{entry.name}</span>
            </div>
            <span className="font-medium">{entry.value}</span>
          </div>
        ))}
        <div className="border-t border-border mt-2 pt-2 flex justify-between">
          <span className="text-muted-foreground">Total</span>
          <span className="font-semibold">{total}</span>
        </div>
      </div>
    </div>
  );
};

interface GeminiUsageChartProps {
  days?: number;
}

export function GeminiUsageChart({ days = 30 }: GeminiUsageChartProps) {
  const { data, isLoading } = useGeminiUsage(days);

  // Loading state
  if (isLoading) {
    return (
      <Card className="border-border/50">
        <CardHeader className="pb-2">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-violet-500/10">
              <Bot className="w-4 h-4 text-violet-600 dark:text-violet-400" />
            </div>
            <div>
              <div className="h-5 w-32 bg-muted animate-pulse rounded" />
              <div className="h-4 w-48 mt-1 bg-muted animate-pulse rounded" />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-[250px] flex items-center justify-center">
            <div className="w-8 h-8 rounded-full border-2 border-violet-500 border-t-transparent animate-spin" />
          </div>
        </CardContent>
      </Card>
    );
  }

  const isEmpty = !data?.data.length || data.totals.total === 0;

  // Format data for the chart
  const chartData = data?.data.map((d) => ({
    ...d,
    formattedDate: formatDateShort(d.date),
  })) || [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
    >
      <Card className="border-border/50">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-violet-500/10">
                <Bot className="w-4 h-4 text-violet-600 dark:text-violet-400" />
              </div>
              <div>
                <CardTitle className="text-base font-semibold">Gemini API Usage</CardTitle>
                <CardDescription className="text-xs">
                  Last {days} days by operation type
                </CardDescription>
              </div>
            </div>
            {/* Totals badges */}
            {data && !isEmpty && (
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="text-xs bg-violet-500/10 text-violet-600 border-violet-500/20">
                  {data.totals.matching} Matching
                </Badge>
                <Badge variant="outline" className="text-xs bg-blue-500/10 text-blue-600 border-blue-500/20">
                  {data.totals.rerank} Re-rank
                </Badge>
                <Badge variant="outline" className="text-xs bg-emerald-500/10 text-emerald-600 border-emerald-500/20">
                  {data.totals.suggestions} Suggestions
                </Badge>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {isEmpty ? (
            <div className="h-[250px] flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <Bot className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>No Gemini API usage data available</p>
                <p className="text-xs mt-1">Usage will appear here once Gemini features are used</p>
              </div>
            </div>
          ) : (
            <div className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={chartData}
                  margin={{ top: 10, right: 10, left: 0, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted/30" vertical={false} />
                  <XAxis
                    dataKey="formattedDate"
                    tickLine={false}
                    axisLine={false}
                    tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                    minTickGap={40}
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                    allowDecimals={false}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend
                    wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }}
                    iconType="square"
                    iconSize={10}
                  />
                  <Bar
                    dataKey="matching"
                    name="Matching"
                    stackId="gemini"
                    fill={USAGE_COLORS.matching}
                    radius={[0, 0, 0, 0]}
                  />
                  <Bar
                    dataKey="rerank"
                    name="Re-rank"
                    stackId="gemini"
                    fill={USAGE_COLORS.rerank}
                    radius={[0, 0, 0, 0]}
                  />
                  <Bar
                    dataKey="suggestions"
                    name="Bullet Suggestions"
                    stackId="gemini"
                    fill={USAGE_COLORS.suggestions}
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
