import { useState } from 'react';
import { useSeniorityProfile } from '@/services/api';
import { motion } from 'framer-motion';
import { AlertCircle, TrendingUp, Layers, Briefcase, Target, Info } from 'lucide-react';
import type { RankedItem, ComparisonRow, TierProfile } from '@/services/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

/** Every figure carries its sample size. A number from 323 postings and one
 *  from 12 must not look alike. */
function SampleSize({ n, label = 'postings' }: { n: number; label?: string }) {
  return (
    <span className="text-xs text-muted-foreground font-normal ml-2 tabular-nums">
      n={n} {label}
    </span>
  );
}

function Caveat({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex items-start gap-1.5 text-xs text-muted-foreground mt-3 leading-relaxed">
      <Info className="h-3.5 w-3.5 shrink-0 mt-0.5" />
      <span>{children}</span>
    </p>
  );
}

/** Two bars per row: the tier against its baseline. Showing the tier alone
 *  would be uninterpretable — "product management 93.7%" only means something
 *  next to Senior's 91.7%. */
function ComparisonBars({
  items,
  baselineLookup,
  tierLabel,
  baselineLabel,
}: {
  items: RankedItem[];
  baselineLookup: Map<string, number>;
  tierLabel: string;
  baselineLabel: string;
}) {
  if (!items.length) {
    return <p className="text-sm text-muted-foreground py-4">No data in this window.</p>;
  }
  const max = Math.max(...items.map((i) => i.pct), 1);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-2 rounded-sm bg-violet-500" /> {tierLabel}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-2 rounded-sm bg-slate-400" /> {baselineLabel}
        </span>
      </div>
      {items.map((item) => {
        const basePct = baselineLookup.get(item.name) ?? 0;
        return (
          <div key={item.name}>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-foreground truncate pr-2">{item.name}</span>
              <span className="text-muted-foreground tabular-nums shrink-0">
                {item.pct}% <span className="text-muted-foreground/60">vs {basePct}%</span>
              </span>
            </div>
            <div className="space-y-0.5">
              <div className="h-2 bg-muted rounded-sm overflow-hidden">
                <motion.div
                  className="h-full bg-violet-500"
                  initial={{ width: 0 }}
                  animate={{ width: `${(item.pct / max) * 100}%` }}
                  transition={{ duration: 0.4 }}
                />
              </div>
              <div className="h-1.5 bg-muted rounded-sm overflow-hidden">
                <motion.div
                  className="h-full bg-slate-400"
                  initial={{ width: 0 }}
                  animate={{ width: `${(basePct / max) * 100}%` }}
                  transition={{ duration: 0.4 }}
                />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DistinctiveList({ rows }: { rows: ComparisonRow[] }) {
  if (!rows.length) {
    return <p className="text-sm text-muted-foreground py-4">Nothing separates the two cohorts here.</p>;
  }
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.name} className="flex items-center justify-between gap-3 text-sm">
          <span className="text-foreground truncate">{r.name}</span>
          <span className="shrink-0 tabular-nums">
            <span className="text-emerald-600 font-medium">+{r.delta}pp</span>
            <span className="text-muted-foreground ml-2">
              {r.tier_pct}% vs {r.baseline_pct}%
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}

function ExperienceCard({ tier, baseline, tierLabel, baselineLabel }: {
  tier: TierProfile; baseline: TierProfile; tierLabel: string; baselineLabel: string;
}) {
  const t = tier.experience;
  const b = baseline.experience;
  const gap = t.median != null && b.median != null ? t.median - b.median : null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Briefcase className="h-4 w-4" /> Years of experience required
          <SampleSize n={t.n} label="with a stated minimum" />
        </CardTitle>
      </CardHeader>
      <CardContent>
        {t.median == null ? (
          <p className="text-sm text-muted-foreground">No stated minimums in this window.</p>
        ) : (
          <div className="space-y-4">
            <div className="flex items-baseline gap-3">
              <span className="text-4xl font-bold tabular-nums">{t.median}</span>
              <span className="text-sm text-muted-foreground">
                median years &middot; middle half {t.p25}&ndash;{t.p75}
              </span>
            </div>
            {gap !== null && (
              <div className="text-sm">
                <span className="text-muted-foreground">{baselineLabel} median is </span>
                <span className="font-medium tabular-nums">{b.median}</span>
                <span className="text-muted-foreground"> &mdash; a </span>
                <span className="font-medium text-violet-600 tabular-nums">
                  {gap > 0 ? '+' : ''}{gap} year
                </span>
                <span className="text-muted-foreground"> step up to {tierLabel}.</span>
              </div>
            )}
            <Caveat>
              Only {t.n} of {tier.n_usable} postings state a minimum, and extraction
              rounds to whole years.
            </Caveat>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function FocusCard({ tier, baseline, tierLabel, baselineLabel }: {
  tier: TierProfile; baseline: TierProfile; tierLabel: string; baselineLabel: string;
}) {
  const order = ['strategic', 'hybrid', 'technical'];
  const colors: Record<string, string> = {
    strategic: 'bg-violet-500', hybrid: 'bg-blue-400', technical: 'bg-emerald-500',
  };
  const render = (p: TierProfile, label: string) => (
    <div>
      <div className="flex justify-between text-sm mb-1.5">
        <span className="font-medium">{label}</span>
        <SampleSize n={p.n_usable} />
      </div>
      <div className="flex h-6 rounded-md overflow-hidden">
        {order.map((k) => {
          const pct = p.focus_pct[k] ?? 0;
          if (!pct) return null;
          return (
            <div
              key={k}
              className={`${colors[k]} flex items-center justify-center`}
              style={{ width: `${pct}%` }}
              title={`${k}: ${pct}%`}
            >
              {pct > 12 && <span className="text-[10px] text-white font-medium">{pct}%</span>}
            </div>
          );
        })}
      </div>
    </div>
  );

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Target className="h-4 w-4" /> How the role is framed
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {render(tier, tierLabel)}
        {render(baseline, baselineLabel)}
        <div className="flex gap-4 text-xs text-muted-foreground">
          {order.map((k) => (
            <span key={k} className="flex items-center gap-1.5">
              <span className={`inline-block w-3 h-2 rounded-sm ${colors[k]}`} /> {k}
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export function SeniorityTab() {
  const [days, setDays] = useState(90);
  const { data, isLoading, error } = useSeniorityProfile('principal', 'senior', days);

  if (isLoading) {
    return <div className="py-12 text-center text-muted-foreground">Loading seniority analysis…</div>;
  }
  if (error || !data) {
    return (
      <div className="py-12 text-center">
        <AlertCircle className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
        <p className="text-muted-foreground">Could not load seniority analytics.</p>
      </div>
    );
  }

  const { tier_profile: tp, baseline_profile: bp, comparison, caveats } = data;
  const lookup = (items: RankedItem[]) => new Map(items.map((i) => [i.name, i.pct]));

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-lg font-semibold">
            {data.tier_label} <span className="text-muted-foreground font-normal">vs {data.baseline_label}</span>
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {tp.n_postings} {data.tier_label} and {bp.n_postings} {data.baseline_label} postings
            matching &ldquo;{data.title_filter}&rdquo; in the last {data.days} days.
          </p>
        </div>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="text-sm border border-border rounded-md px-2 py-1 bg-background"
        >
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
          <option value={180}>Last 180 days</option>
        </select>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <ExperienceCard tier={tp} baseline={bp} tierLabel={data.tier_label} baselineLabel={data.baseline_label} />
        <FocusCard tier={tp} baseline={bp} tierLabel={data.tier_label} baselineLabel={data.baseline_label} />
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <TrendingUp className="h-4 w-4" /> What sets {data.tier_label} apart
          </CardTitle>
        </CardHeader>
        <CardContent>
          <DistinctiveList rows={comparison.must_have?.distinctive_to_tier ?? []} />
          <Caveat>
            Percentage-point gap against {data.baseline_label}. Cohorts differ ~5x in size,
            so these compare share of postings, not raw counts.
          </Caveat>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Layers className="h-4 w-4" /> Must-have skills
              <SampleSize n={tp.n_usable} />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ComparisonBars items={tp.must_have} baselineLookup={lookup(bp.must_have)}
              tierLabel={data.tier_label} baselineLabel={data.baseline_label} />
            <Caveat>
              Skill labels are folded to canonical names (data/skill_canonical_map.json);
              unmapped variants count under their raw text.
            </Caveat>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Layers className="h-4 w-4" /> Nice-to-have skills
              <SampleSize n={tp.n_usable} />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ComparisonBars items={tp.nice_to_have} baselineLookup={lookup(bp.nice_to_have)}
              tierLabel={data.tier_label} baselineLabel={data.baseline_label} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Domains
              <SampleSize n={tp.n_usable} />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ComparisonBars items={tp.domains} baselineLookup={lookup(bp.domains)}
              tierLabel={data.tier_label} baselineLabel={data.baseline_label} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Responsibility themes
              <SampleSize n={tp.n_usable} />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ComparisonBars items={tp.responsibility_themes}
              baselineLookup={lookup(bp.responsibility_themes)}
              tierLabel={data.tier_label} baselineLabel={data.baseline_label} />
            <Caveat>
              Themes are keyword-matched and cover {caveats.responsibility_coverage_pct}% of
              responsibility statements &mdash; percentages are of postings with at least one
              match, not of all responsibilities.
            </Caveat>
          </CardContent>
        </Card>
      </div>

      <Card className="bg-muted/30">
        <CardContent className="pt-6 space-y-2 text-sm text-muted-foreground">
          <p className="font-medium text-foreground">How to read this</p>
          <p>{caveats.snapshot_only}</p>
          <p>
            The cohort is defined by job title. Gemini&rsquo;s reading of the description
            disagrees on <span className="font-medium text-foreground tabular-nums">
            {caveats.title_vs_gemini_disagreement}</span> of {tp.n_usable} postings
            ({caveats.title_vs_gemini_pct}%) &mdash; titles carrying more seniority than the
            job describes. These are kept, since an inflated title is itself market signal.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
