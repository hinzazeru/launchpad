import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { Maximize2, X } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface BarChartData {
  name: string;
  count: number;
}

interface BarChartCardProps {
  title: string;
  description?: string;
  data: BarChartData[];
  isLoading?: boolean;
  color?: string;
  layout?: 'horizontal' | 'vertical';
  emptyMessage?: string;
}

// Custom tick component for intelligent label handling
const CustomYAxisTick = (props: any) => {
  const { x, y, payload } = props;
  const label = payload.value;
  const maxLength = 15; // Max characters before truncation
  const displayText = label.length > maxLength ? label.substring(0, maxLength) + '...' : label;

  return (
    <g transform={`translate(${x},${y})`}>
      <text
        x={0}
        y={0}
        dy={4}
        textAnchor="end"
        fill="currentColor"
        className="text-[11px] fill-muted-foreground font-medium"
      >
        <title>{label}</title> {/* Native tooltip on hover */}
        {displayText}
      </text>
    </g>
  );
};

export function BarChartCard({
  title,
  description,
  data,
  isLoading = false,
  color = 'hsl(var(--primary))',
  // layout prop is kept for API compatibility but chart is always vertical
  layout: _layout = 'horizontal',
  emptyMessage = 'No data available',
}: BarChartCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Loading skeleton
  if (isLoading) {
    return (
      <Card className="border-border/50 overflow-hidden">
        <CardHeader className="pb-2">
          <div className="h-5 w-32 bg-muted animate-pulse rounded" />
          {description && <div className="h-4 w-48 mt-1 bg-muted animate-pulse rounded" />}
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="h-4 w-20 bg-muted animate-pulse rounded" />
                <motion.div
                  className="h-6 bg-muted rounded"
                  initial={{ width: 0 }}
                  animate={{ width: `${100 - i * 15}%` }}
                  transition={{ duration: 0.5, delay: i * 0.1 }}
                />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  const isEmpty = !data || data.length === 0;

  // Chart rendering logic (reused for both modes)
  const renderChart = (expanded: boolean) => {
    const height = expanded ? 500 : 250;

    // Sort data for better visualization
    const sortedData = [...data].sort((a, b) => b.count - a.count);

    return (
      <div style={{ height: expanded ? '100%' : height }} className="w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={sortedData}
            layout="vertical"
            margin={{ top: 5, right: 30, left: expanded ? 40 : 10, bottom: 5 }}
            barCategoryGap={expanded ? 4 : 2}
          >
            <XAxis type="number" tickLine={false} axisLine={false} fontSize={11} hide={!expanded} />
            <YAxis
              type="category"
              dataKey="name"
              width={expanded ? 180 : 100}
              tickLine={false}
              axisLine={false}
              tick={expanded ? { fontSize: 13, fill: 'currentColor' } : <CustomYAxisTick />}
              interval={0} // Show all ticks
            />
            <Tooltip
              contentStyle={{
                background: 'hsl(var(--background))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '8px',
                fontSize: '12px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
              }}
              labelStyle={{ color: 'hsl(var(--foreground))', fontWeight: 600 }}
              cursor={{ fill: 'hsl(var(--muted)/0.2)' }}
            />
            <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={expanded ? 40 : 24}>
              {sortedData.map((_, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={color}
                  fillOpacity={expanded ? 0.9 : 1 - index * 0.05} // Consistent opacity in expanded mode
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  };

  return (
    <>
      <Card className="border-border/50 overflow-hidden transition-all duration-300 hover:shadow-lg hover:shadow-primary/5 group relative">
        <CardHeader className="pb-2 pr-12"> {/* Padding to avoid title overlap with button */}
          <CardTitle className="text-base font-semibold truncate" title={title}>{title}</CardTitle>
          {description && (
            <CardDescription className="text-xs truncate">{description}</CardDescription>
          )}
          {/* Maximize Button */}
          {!isEmpty && (
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-2 top-2 h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-muted"
              onClick={() => setIsExpanded(true)}
            >
              <Maximize2 className="h-4 w-4 text-muted-foreground" />
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {isEmpty ? (
            <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
              {emptyMessage}
            </div>
          ) : (
            renderChart(false)
          )}
        </CardContent>
      </Card>

      {/* Expanded Modal Overlay */}
      <AnimatePresence>
        {isExpanded && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 md:p-8">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-4xl h-[80vh] bg-background rounded-xl border border-border shadow-2xl flex flex-col relative overflow-hidden"
            >
              <div className="flex items-center justify-between p-6 border-b border-border">
                <div>
                  <h2 className="text-2xl font-bold">{title}</h2>
                  <p className="text-muted-foreground">{description}</p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="rounded-full hover:bg-muted"
                  onClick={() => setIsExpanded(false)}
                >
                  <X className="h-5 w-5" />
                </Button>
              </div>
              <div className="flex-1 p-6 overflow-hidden">
                {renderChart(true)}
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}
