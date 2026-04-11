import { useState, useMemo } from 'react';
import { useSalaryAnalytics } from '@/services/api';
import { motion } from 'framer-motion';
import {
  DollarSign,
  MapPin,
  Building2,
  AlertCircle,
  TrendingUp,
  ChevronDown,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

function formatSalary(n: number): string {
  if (n >= 1000) return `$${Math.round(n / 1000)}K`;
  return `$${Math.round(n)}`;
}

function formatRange(min: number, max: number): string {
  return `${formatSalary(min)} - ${formatSalary(max)}`;
}

const COUNTRY_COLORS: Record<string, string> = {
  Canada: '#ef4444',
  US: '#3b82f6',
  Other: '#8b5cf6',
};

export function SalaryTab() {
  const [seniority, setSeniority] = useState('senior');
  const { data, isLoading, error } = useSalaryAnalytics('product manager', seniority, 90);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-4">
        <motion.div
          className="w-12 h-12 rounded-full border-2 border-primary border-t-transparent"
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
        />
        <p className="text-muted-foreground">Loading salary data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center text-destructive bg-destructive/10 rounded-lg">
        <AlertCircle className="w-8 h-8 mx-auto mb-2" />
        <p>Failed to load salary analytics.</p>
      </div>
    );
  }

  if (!data || data.parseable === 0) {
    return (
      <div className="p-8 text-center text-muted-foreground">
        <DollarSign className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p>No salary data available for the current filters.</p>
      </div>
    );
  }

  const canadaStats = data.by_country.find(c => c.country === 'Canada');
  const usStats = data.by_country.find(c => c.country === 'US');

  // Country comparison chart data
  const countryChartData = data.by_country
    .filter(c => c.country !== 'Other')
    .map(c => ({
      country: c.country,
      'Range Low': Math.round(c.median_min / 1000),
      'Range High': Math.round(c.median_max / 1000),
      mean_min: Math.round(c.mean_min / 1000),
      mean_max: Math.round(c.mean_max / 1000),
      count: c.count,
    }));

  // Domain chart data
  const DEFAULT_VISIBLE = 7;
  const [extraDomains, setExtraDomains] = useState<Set<string>>(new Set());
  const [showDomainPicker, setShowDomainPicker] = useState(false);

  const allDomainData = useMemo(() => data.by_domain.map(d => ({
    key: d.domain,
    name: d.display_name.length > 25 ? d.display_name.slice(0, 22) + '...' : d.display_name,
    fullName: d.display_name,
    min: Math.round(d.median_min / 1000),
    max: Math.round(d.median_max / 1000),
    range: Math.round((d.median_max - d.median_min) / 1000),
    count: d.count,
  })), [data.by_domain]);

  const remainingDomains = allDomainData.slice(DEFAULT_VISIBLE);

  const domainChartData = useMemo(() => {
    const top = allDomainData.slice(0, DEFAULT_VISIBLE);
    const extra = allDomainData.filter(d => extraDomains.has(d.key));
    // Merge, avoiding duplicates from top 7
    const topKeys = new Set(top.map(d => d.key));
    return [...top, ...extra.filter(d => !topKeys.has(d.key))];
  }, [allDomainData, extraDomains]);

  const toggleDomain = (key: string) => {
    setExtraDomains(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const seniorityOptions = [
    { value: 'senior', label: 'Senior' },
    { value: 'lead', label: 'Lead' },
    { value: 'principal', label: 'Principal' },
    { value: 'all', label: 'All Levels' },
  ];

  return (
    <div className="space-y-6">
      {/* Seniority filter */}
      <motion.div
        className="flex items-center gap-2"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <span className="text-sm text-muted-foreground">Seniority:</span>
        {seniorityOptions.map(opt => (
          <button
            key={opt.value}
            onClick={() => setSeniority(opt.value)}
            className={`px-3 py-1 text-xs rounded-full transition-colors ${
              seniority === opt.value
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted hover:bg-muted/80 text-muted-foreground'
            }`}
          >
            {opt.label}
          </button>
        ))}
        <span className="ml-auto text-xs text-muted-foreground">
          {data.parseable} jobs with salary data
        </span>
      </motion.div>

      {/* Top Stats */}
      <motion.div
        className="grid grid-cols-2 lg:grid-cols-4 gap-4"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex items-center gap-3 p-4 rounded-lg bg-card border shadow-sm">
          <div className="p-2 rounded-md bg-emerald-500/10">
            <DollarSign className="w-5 h-5 text-emerald-500" />
          </div>
          <div>
            <p className="text-lg font-bold">{formatRange(data.overall.median_min, data.overall.median_max)}</p>
            <p className="text-xs text-muted-foreground">Overall Median</p>
          </div>
        </div>

        <div className="flex items-center gap-3 p-4 rounded-lg bg-card border shadow-sm">
          <div className="p-2 rounded-md bg-blue-500/10">
            <TrendingUp className="w-5 h-5 text-blue-500" />
          </div>
          <div>
            <p className="text-lg font-bold">{formatSalary(data.overall.max_value)}</p>
            <p className="text-xs text-muted-foreground">Highest Salary</p>
          </div>
        </div>

        <div className="flex items-center gap-3 p-4 rounded-lg bg-card border shadow-sm">
          <div className="p-2 rounded-md bg-red-500/10">
            <MapPin className="w-5 h-5 text-red-500" />
          </div>
          <div>
            <p className="text-lg font-bold">
              {canadaStats ? formatRange(canadaStats.median_min, canadaStats.median_max) : '--'}
            </p>
            <p className="text-xs text-muted-foreground">Canada Median {canadaStats ? `(${canadaStats.count})` : ''}</p>
          </div>
        </div>

        <div className="flex items-center gap-3 p-4 rounded-lg bg-card border shadow-sm">
          <div className="p-2 rounded-md bg-blue-500/10">
            <MapPin className="w-5 h-5 text-blue-500" />
          </div>
          <div>
            <p className="text-lg font-bold">
              {usStats ? formatRange(usStats.median_min, usStats.median_max) : '--'}
            </p>
            <p className="text-xs text-muted-foreground">US Median {usStats ? `(${usStats.count})` : ''}</p>
          </div>
        </div>
      </motion.div>

      {/* Country Comparison */}
      {countryChartData.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <MapPin className="w-4 h-4" />
                Salary by Country (Median Range, $K)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[200px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={countryChartData} layout="vertical" margin={{ left: 10, right: 20 }}>
                    <XAxis type="number" tickFormatter={v => `$${v}K`} />
                    <YAxis type="category" dataKey="country" width={60} tick={{ fontSize: 12 }} />
                    <Tooltip
                      formatter={(value, name) => [`$${value}K`, name as string]}
                      labelFormatter={(label) => {
                        const item = countryChartData.find(d => d.country === label);
                        return `${label} (${item?.count} jobs)`;
                      }}
                    />
                    <Legend />
                    <Bar dataKey="Range Low" stackId="a" fill="#94a3b8" radius={[4, 0, 0, 4]} />
                    <Bar dataKey="Range High" stackId="a" radius={[0, 4, 4, 0]}>
                      {countryChartData.map((entry) => (
                        <Cell key={entry.country} fill={COUNTRY_COLORS[entry.country] || '#8b5cf6'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="text-xs text-muted-foreground mt-2 text-center">
                Note: Canadian salaries in CAD, US salaries in USD (not converted)
              </p>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Domain Breakdown */}
      {allDomainData.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Building2 className="w-4 h-4" />
                Median Salary by Industry ($K)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div style={{ height: Math.max(200, domainChartData.length * 40 + 40) }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={domainChartData} layout="vertical" margin={{ left: 20, right: 20 }}>
                    <XAxis type="number" tickFormatter={v => `$${v}K`} />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={150}
                      tick={{ fontSize: 11 }}
                    />
                    <Tooltip
                      formatter={(value, name) => [`$${value}K`, name as string]}
                      labelFormatter={(_label, payload) => {
                        const item = payload?.[0]?.payload;
                        return item ? `${item.fullName} (${item.count} jobs)` : '';
                      }}
                    />
                    <Legend />
                    <Bar dataKey="min" name="Median Low" fill="#94a3b8" radius={[4, 0, 0, 4]} />
                    <Bar dataKey="range" name="Median High" fill="#10b981" stackId="salary" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Domain picker for remaining industries */}
              {remainingDomains.length > 0 && (
                <div className="mt-4 border-t pt-3">
                  <button
                    onClick={() => setShowDomainPicker(!showDomainPicker)}
                    className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showDomainPicker ? 'rotate-180' : ''}`} />
                    {showDomainPicker ? 'Hide' : 'Show'} {remainingDomains.length} more industries
                    {extraDomains.size > 0 && (
                      <span className="ml-1 px-1.5 py-0.5 rounded-full bg-primary text-primary-foreground text-[10px]">
                        {extraDomains.size} selected
                      </span>
                    )}
                  </button>
                  {showDomainPicker && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {remainingDomains.map(d => (
                        <button
                          key={d.key}
                          onClick={() => toggleDomain(d.key)}
                          className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${
                            extraDomains.has(d.key)
                              ? 'bg-primary text-primary-foreground border-primary'
                              : 'bg-background hover:bg-muted border-border text-muted-foreground'
                          }`}
                        >
                          {d.fullName} ({d.count})
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
