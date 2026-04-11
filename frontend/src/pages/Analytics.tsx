import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  useAnalyticsSummary,
  useAnalyticsSkills,
  useAnalyticsMarket,
  useAnalyticsTimeline,
  useScoreDistribution,
} from '@/services/api';
import { BarChartCard, TimelineChart, SalaryTab } from '@/components/analytics';
import { PerformanceTab } from '@/components/analytics/PerformanceTab';
import {
  Briefcase,
  Target,
  Sparkles,
  TrendingUp,
  AlertCircle,
  BarChart2,
  Activity,
  LayoutDashboard,
  DollarSign
} from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';

import { RadialScore } from '@/components/RadialScore';

export function Analytics() {
  const [activeTab, setActiveTab] = useState('analytics');
  const navigate = useNavigate();

  // Fetch all analytics data
  const { data: summary, isLoading: summaryLoading, error: summaryError } = useAnalyticsSummary();
  const { data: skills, isLoading: skillsLoading } = useAnalyticsSkills(10);
  const { data: market, isLoading: marketLoading } = useAnalyticsMarket(10, 60);
  const { data: timeline, isLoading: timelineLoading } = useAnalyticsTimeline(30);
  const { data: scoreDistribution, isLoading: scoreDistLoading } = useScoreDistribution();

  const isInitialLoading = summaryLoading && skillsLoading && marketLoading;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <motion.h1
            className="text-3xl font-bold tracking-tight"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            Analytics
          </motion.h1>
          <motion.p
            className="text-muted-foreground"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1 }}
          >
            Insights into your job search performance and market trends
          </motion.p>
        </div>

        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Tabs defaultValue="analytics" value={activeTab} onValueChange={setActiveTab} className="w-[400px]">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="analytics" className="flex items-center gap-2">
                <LayoutDashboard className="w-4 h-4" />
                <span>Overview</span>
              </TabsTrigger>
              <TabsTrigger value="salary" className="flex items-center gap-2">
                <DollarSign className="w-4 h-4" />
                <span>Salary</span>
              </TabsTrigger>
              <TabsTrigger value="performance" className="flex items-center gap-2">
                <Activity className="w-4 h-4" />
                <span>Performance</span>
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </motion.div>
      </div>


      {/* Analytics Content */}
      <Tabs value={activeTab} className="w-full">
        <TabsContent value="analytics" className="space-y-6 mt-0">

          {/* Stats Bar - Matching JobMatches design */}
          <motion.div
            className="grid grid-cols-2 lg:grid-cols-4 gap-4"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 border border-border/50">
              <div className="p-2 rounded-md bg-blue-500/10">
                <Briefcase className="w-4 h-4 text-blue-500" />
              </div>
              <div>
                {summaryLoading ? (
                  <div className="space-y-1">
                    <div className="h-7 w-12 bg-muted animate-pulse rounded" />
                    <div className="h-3 w-16 bg-muted animate-pulse rounded" />
                  </div>
                ) : (
                  <>
                    <p className="text-2xl font-bold tabular-nums">{summary?.total_jobs ?? 0}</p>
                    <p className="text-xs text-muted-foreground">Total Jobs</p>
                  </>
                )}
              </div>
            </div>

            <div
              className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 border border-border/50 cursor-pointer hover:bg-muted/50 hover:border-primary/30 transition-all"
              onClick={() => navigate('/matches?minScore=70')}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && navigate('/matches?minScore=70')}
            >
              <div className="p-2 rounded-md bg-emerald-500/10">
                <Target className="w-4 h-4 text-emerald-500" />
              </div>
              <div>
                {summaryLoading ? (
                  <div className="space-y-1">
                    <div className="h-7 w-12 bg-muted animate-pulse rounded" />
                    <div className="h-3 w-16 bg-muted animate-pulse rounded" />
                  </div>
                ) : (
                  <>
                    <p className="text-2xl font-bold tabular-nums">{summary?.high_matches ?? 0}</p>
                    <p className="text-xs text-muted-foreground">High Matches (70%+)</p>
                  </>
                )}
              </div>
            </div>

            <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 border border-border/50">
              <div className="p-2 rounded-md bg-violet-500/10">
                <Sparkles className="w-4 h-4 text-violet-500" />
              </div>
              <div>
                {summaryLoading ? (
                  <div className="space-y-1">
                    <div className="h-7 w-12 bg-muted animate-pulse rounded" />
                    <div className="h-3 w-16 bg-muted animate-pulse rounded" />
                  </div>
                ) : (
                  <>
                    <p className="text-2xl font-bold tabular-nums">{summary?.ai_analysed ?? 0}</p>
                    <p className="text-xs text-muted-foreground">AI Analysed</p>
                  </>
                )}
              </div>
            </div>

            <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 border border-border/50">
              <div className="shrink-0">
                <RadialScore score={summary?.avg_score || 0} size={52} strokeWidth={4} />
              </div>
              <div>
                {summaryLoading ? (
                  <div className="space-y-1">
                    <div className="h-7 w-12 bg-muted animate-pulse rounded" />
                    <div className="h-3 w-16 bg-muted animate-pulse rounded" />
                  </div>
                ) : (
                  <>
                    <p className="text-2xl font-bold tabular-nums text-transparent">
                      {/* Hidden text to maintain layout height matching others if needed, or just remove */}
                      <span className="opacity-0">00%</span>
                    </p>
                    <p className="text-xs text-muted-foreground -mt-6">Avg Score</p>
                  </>
                )}
              </div>
            </div>
          </motion.div>

          {/* Error State */}
          {summaryError && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center justify-center py-12 gap-2 text-destructive"
            >
              <AlertCircle className="w-8 h-8" />
              <p>Failed to load analytics. Please try again.</p>
            </motion.div>
          )}

          {/* Loading State */}
          {isInitialLoading && (
            <div className="flex flex-col items-center justify-center py-16 gap-4">
              <motion.div
                className="w-12 h-12 rounded-full border-2 border-primary border-t-transparent"
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              />
              <p className="text-muted-foreground">Loading analytics...</p>
            </div>
          )}

          {/* Self-Improvement Section */}
          {!isInitialLoading && !summaryError && (
            <>
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
              >
                <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
                  <Target className="w-4 h-4" />
                  Self-Improvement
                </h2>
                <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
                  {/* Score Distribution */}
                  <BarChartCard
                    title="Match Quality Distribution"
                    description="How your matches are distributed"
                    data={
                      scoreDistribution?.map((item) => ({
                        name: item.range,
                        count: item.count,
                      })) ?? []
                    }
                    isLoading={scoreDistLoading}
                    layout="vertical"
                    color="hsl(var(--primary))"
                    emptyMessage="Run some job searches to see distribution"
                  />

                  {/* Skill Gaps */}
                  <BarChartCard
                    title="Your Skill Gaps"
                    description="Skills missing from high-match jobs"
                    data={
                      skills?.skill_gaps.map((s) => ({
                        name: s.name,
                        count: s.count,
                      })) ?? []
                    }
                    isLoading={skillsLoading}
                    color="hsl(0 84.2% 60.2%)"
                    emptyMessage="No skill gaps identified yet"
                  />

                  {/* Matching Skills */}
                  <BarChartCard
                    title="Top Matching Skills"
                    description="Skills driving your matches"
                    data={
                      skills?.matching_skills.map((s) => ({
                        name: s.name,
                        count: s.count,
                      })) ?? []
                    }
                    isLoading={skillsLoading}
                    color="hsl(142.1 76.2% 36.3%)"
                    emptyMessage="No matching skills data yet"
                  />
                </div>
              </motion.div>

              {/* Market Research Section */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
              >
                <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
                  <BarChart2 className="w-4 h-4" />
                  Market Research
                </h2>
                <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
                  {/* In-Demand Skills */}
                  <BarChartCard
                    title="In-Demand Skills"
                    description="Most requested skills in job postings"
                    data={
                      skills?.in_demand_skills.map((s) => ({
                        name: s.name,
                        count: s.count,
                      })) ?? []
                    }
                    isLoading={skillsLoading}
                    color="hsl(217.2 91.2% 59.8%)"
                    emptyMessage="No job data yet"
                  />

                  {/* Top Companies */}
                  <BarChartCard
                    title="Top Companies"
                    description="Companies with most high-match jobs"
                    data={
                      market?.top_companies.map((c) => ({
                        name: c.name,
                        count: c.count,
                      })) ?? []
                    }
                    isLoading={marketLoading}
                    color="hsl(262.1 83.3% 57.8%)"
                    emptyMessage="No company data yet"
                  />

                  {/* Locations */}
                  <BarChartCard
                    title="Job Locations"
                    description="Where high-match jobs are located"
                    data={
                      market?.locations.map((l) => ({
                        name: l.name,
                        count: l.count,
                      })) ?? []
                    }
                    isLoading={marketLoading}
                    color="hsl(47.9 95.8% 53.1%)"
                    emptyMessage="No location data yet"
                  />
                </div>
              </motion.div>

              {/* Activity Timeline */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 }}
              >
                <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4" />
                  Activity Timeline
                </h2>
                <TimelineChart
                  title="Job Search Activity"
                  description="Jobs fetched and matches over the last 30 days"
                  data={timeline?.points ?? []}
                  isLoading={timelineLoading}
                />
              </motion.div>
            </>
          )}
        </TabsContent>

        <TabsContent value="salary" className="mt-0">
          <SalaryTab />
        </TabsContent>

        <TabsContent value="performance" className="mt-0">
          <PerformanceTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
