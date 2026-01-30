import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useJobs } from '@/services/api';
import type { Job } from '@/services/api';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import {
    Search as SearchIcon,
    AlertCircle,
    CheckCircle2,
    ChevronDown,
    XCircle,
    MapPin,
    Building2,
    Calendar,
    Sparkles,
    TrendingUp,
    TrendingDown,
    ExternalLink,
    Briefcase,
} from 'lucide-react';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';

// Radial Progress Component - The hero visual element
function RadialScore({ score, size = 72, strokeWidth = 6 }: { score: number; size?: number; strokeWidth?: number }) {
    const radius = (size - strokeWidth) / 2;
    const circumference = radius * 2 * Math.PI;
    const offset = circumference - (score / 100) * circumference;

    // Dynamic gradient based on score
    const getGradientColors = () => {
        if (score >= 75) return { start: '#10b981', end: '#34d399' }; // Emerald
        if (score >= 60) return { start: '#f59e0b', end: '#fbbf24' }; // Amber
        return { start: '#ef4444', end: '#f87171' }; // Red
    };

    const colors = getGradientColors();
    const gradientId = `score-gradient-${score}-${Math.random().toString(36).substr(2, 9)}`;

    return (
        <div className="relative" style={{ width: size, height: size }}>
            <svg width={size} height={size} className="-rotate-90">
                <defs>
                    <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor={colors.start} />
                        <stop offset="100%" stopColor={colors.end} />
                    </linearGradient>
                </defs>
                {/* Background circle */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={strokeWidth}
                    className="text-muted/30"
                />
                {/* Progress circle */}
                <motion.circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke={`url(#${gradientId})`}
                    strokeWidth={strokeWidth}
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    initial={{ strokeDashoffset: circumference }}
                    animate={{ strokeDashoffset: offset }}
                    transition={{ duration: 0.8, ease: "easeOut", delay: 0.2 }}
                />
            </svg>
            {/* Center score */}
            <div className="absolute inset-0 flex items-center justify-center">
                <motion.span
                    className="text-lg font-bold tabular-nums tracking-tight"
                    initial={{ opacity: 0, scale: 0.5 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.3, delay: 0.5 }}
                >
                    {Math.round(score)}
                </motion.span>
            </div>
        </div>
    );
}

// Compact horizontal stacked bar for breakdown
function BreakdownBar({ skills, experience, domains }: { skills: number; experience: number; domains: number }) {
    const total = skills + experience + domains;
    const skillsWidth = total > 0 ? (skills / total) * 100 : 33;
    const expWidth = total > 0 ? (experience / total) * 100 : 33;
    const domainsWidth = total > 0 ? (domains / total) * 100 : 34;

    return (
        <div className="space-y-1.5">
            <div className="flex h-2 rounded-full overflow-hidden bg-muted/30">
                <motion.div
                    className="bg-gradient-to-r from-blue-500 to-blue-400"
                    initial={{ width: 0 }}
                    animate={{ width: `${skillsWidth}%` }}
                    transition={{ duration: 0.5, delay: 0.3 }}
                    title={`Skills: ${Math.round(skillsWidth)}%`}
                />
                <motion.div
                    className="bg-gradient-to-r from-violet-500 to-violet-400"
                    initial={{ width: 0 }}
                    animate={{ width: `${expWidth}%` }}
                    transition={{ duration: 0.5, delay: 0.4 }}
                    title={`Experience: ${Math.round(expWidth)}%`}
                />
                <motion.div
                    className="bg-gradient-to-r from-cyan-500 to-cyan-400"
                    initial={{ width: 0 }}
                    animate={{ width: `${domainsWidth}%` }}
                    transition={{ duration: 0.5, delay: 0.5 }}
                    title={`Domains: ${Math.round(domainsWidth)}%`}
                />
            </div>
            <div className="flex justify-between text-[10px] text-muted-foreground font-mono">
                <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-sm bg-blue-500" />
                    Skills
                </span>
                <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-sm bg-violet-500" />
                    Exp
                </span>
                <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-sm bg-cyan-500" />
                    Domain
                </span>
            </div>
        </div>
    );
}

function formatDate(dateString?: string) {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
    });
}

// Skill Tag Component
function SkillTag({ skill, variant }: { skill: string; variant: 'matched' | 'gap' | 'domain' }) {
    const styles = {
        matched: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
        gap: 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20',
        domain: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
    };

    return (
        <span className={`inline-flex px-2 py-0.5 text-[11px] font-medium rounded-md border ${styles[variant]}`}>
            {skill}
        </span>
    );
}

// Job Card Component
function JobCard({ job, index }: { job: Job; index: number }) {
    const [isExpanded, setIsExpanded] = useState(false);

    // Parse experience
    let resumeYears = 0;
    const requiredYears = job.experience_required || 0;
    if (job.experience_alignment) {
        const match = job.experience_alignment.match(/Resume:\s*([\d.]+)\s*years/i);
        if (match) resumeYears = parseFloat(match[1]);
    }

    // Calculate approximate breakdown percentages (for visual purposes)
    const skillsPercent = job.skills_required_count > 0
        ? (job.skills_matched_count / job.skills_required_count) * 45
        : 22.5;
    const expPercent = requiredYears > 0
        ? Math.min(resumeYears / requiredYears, 1) * 35
        : 17.5;
    const domainPercent = ((job.domains?.length || 0) / Math.max((job.domains?.length || 0) + (job.missing_domains?.length || 0), 1)) * 20;

    const hasGaps = (job.skill_gaps?.length || 0) > 0;
    const hasMissingDomains = (job.missing_domains?.length || 0) > 0;

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: index * 0.05 }}
        >
            <Card
                className={`group relative overflow-hidden transition-all duration-300 cursor-pointer hover:shadow-lg hover:shadow-primary/5 border-border/50 ${isExpanded ? 'ring-1 ring-primary/20' : ''
                    }`}
                onClick={() => setIsExpanded(!isExpanded)}
            >
                {/* Score indicator strip */}
                <div
                    className={`absolute left-0 top-0 bottom-0 w-1 ${job.match_score >= 75 ? 'bg-gradient-to-b from-emerald-500 to-emerald-400' :
                            job.match_score >= 60 ? 'bg-gradient-to-b from-amber-500 to-amber-400' :
                                'bg-gradient-to-b from-red-500 to-red-400'
                        }`}
                />

                <CardContent className="p-0">
                    <div className="flex gap-4 p-4 pl-5">
                        {/* Score Gauge */}
                        <div className="flex-shrink-0 flex flex-col items-center gap-1">
                            <RadialScore score={job.match_score} />
                            {job.gemini_score !== undefined && job.gemini_score > 0 && (
                                <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                                    <Sparkles className="w-3 h-3 text-violet-500" />
                                    <span className="font-mono">{Math.round(job.gemini_score)}</span>
                                </div>
                            )}
                        </div>

                        {/* Main Content */}
                        <div className="flex-1 min-w-0 space-y-2">
                            {/* Header */}
                            <div className="space-y-1">
                                <div className="flex items-start justify-between gap-2">
                                    <a
                                        href={job.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        onClick={(e) => e.stopPropagation()}
                                        className="font-semibold text-[15px] leading-tight hover:text-primary transition-colors line-clamp-1 group-hover:underline decoration-primary/30 underline-offset-2"
                                    >
                                        {job.title}
                                    </a>
                                    <a
                                        href={job.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        onClick={(e) => e.stopPropagation()}
                                        className="flex-shrink-0 p-1 rounded-md hover:bg-muted/50 text-muted-foreground hover:text-primary transition-colors"
                                    >
                                        <ExternalLink className="w-4 h-4" />
                                    </a>
                                </div>
                                <div className="flex items-center gap-3 text-sm text-muted-foreground flex-wrap">
                                    <span className="flex items-center gap-1.5 font-medium">
                                        <Building2 className="w-3.5 h-3.5" />
                                        {job.company}
                                    </span>

                                    {/* Job Domains - Moved to Header */}
                                    {job.domains && job.domains.length > 0 && (
                                        <div className="flex items-center gap-1.5">
                                            {job.domains.map(domain => (
                                                <span key={domain} className="inline-flex px-2 py-0.5 text-[10px] font-medium rounded-md border bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20">
                                                    {domain}
                                                </span>
                                            ))}
                                        </div>
                                    )}

                                    {job.location && (
                                        <span className="flex items-center gap-1">
                                            <MapPin className="w-3.5 h-3.5" />
                                            <span className="truncate max-w-[120px]">{job.location}</span>
                                        </span>
                                    )}
                                    <span className="flex items-center gap-1 text-xs">
                                        <Calendar className="w-3 h-3" />
                                        {formatDate(job.posting_date)}
                                    </span>
                                </div>
                            </div>

                            {/* Breakdown Bar */}
                            <BreakdownBar
                                skills={skillsPercent}
                                experience={expPercent}
                                domains={domainPercent}
                            />

                            {/* Quick Stats Row */}
                            <div className="flex items-center gap-4 text-xs">
                                <div className="flex items-center gap-1.5">
                                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                                    <span className="text-muted-foreground">
                                        <span className="font-semibold text-foreground">{job.skills_matched_count}</span>
                                        /{job.skills_required_count} skills
                                    </span>
                                </div>
                                {hasGaps && (
                                    <div className="flex items-center gap-1.5">
                                        <XCircle className="w-3.5 h-3.5 text-red-500" />
                                        <span className="text-muted-foreground">
                                            <span className="font-semibold text-foreground">{job.skill_gaps?.length}</span> gaps
                                        </span>
                                    </div>
                                )}
                                {requiredYears > 0 && (
                                    <div className="flex items-center gap-1.5">
                                        {resumeYears >= requiredYears ? (
                                            <TrendingUp className="w-3.5 h-3.5 text-emerald-500" />
                                        ) : (
                                            <TrendingDown className="w-3.5 h-3.5 text-amber-500" />
                                        )}
                                        <span className="text-muted-foreground font-mono">
                                            {resumeYears}yr/{requiredYears}yr
                                        </span>
                                    </div>
                                )}
                                {job.salary && (
                                    <div className="flex items-center gap-1.5 ml-auto text-emerald-600 dark:text-emerald-400">
                                        <Briefcase className="w-3.5 h-3.5" />
                                        <span className="font-medium">{job.salary}</span>
                                    </div>
                                )}
                            </div>

                            {/* Expand indicator */}
                            <div className="flex items-center justify-center pt-1">
                                <motion.div
                                    animate={{ rotate: isExpanded ? 180 : 0 }}
                                    transition={{ duration: 0.2 }}
                                >
                                    <ChevronDown className="w-4 h-4 text-muted-foreground/50" />
                                </motion.div>
                            </div>
                        </div>
                    </div>

                    {/* Expanded Details */}
                    <AnimatePresence>
                        {isExpanded && (
                            <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                transition={{ duration: 0.3 }}
                                className="overflow-hidden"
                            >
                                <div className="px-5 pb-4 pt-2 border-t border-border/50 space-y-4 bg-muted/20">
                                    {/* Skills Section */}
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {/* Matched Skills */}
                                        {job.matching_skills.length > 0 && (
                                            <div className="space-y-2">
                                                <h4 className="text-xs font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                                                    <CheckCircle2 className="w-3.5 h-3.5" />
                                                    Matched Skills
                                                </h4>
                                                <div className="flex flex-wrap gap-1.5">
                                                    {job.matching_skills.map(skill => (
                                                        <SkillTag key={skill} skill={skill} variant="matched" />
                                                    ))}
                                                </div>
                                            </div>
                                        )}

                                        {/* Skill Gaps */}
                                        {hasGaps && (
                                            <div className="space-y-2">
                                                <h4 className="text-xs font-semibold uppercase tracking-wider text-red-600 dark:text-red-400 flex items-center gap-1.5">
                                                    <XCircle className="w-3.5 h-3.5" />
                                                    Skill Gaps
                                                </h4>
                                                <div className="flex flex-wrap gap-1.5">
                                                    {job.skill_gaps?.map(skill => (
                                                        <SkillTag key={skill} skill={skill} variant="gap" />
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>



                                    {/* Missing Domains */}
                                    {hasMissingDomains && (
                                        <div className="space-y-2">
                                            <h4 className="text-xs font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400 flex items-center gap-1.5">
                                                <AlertCircle className="w-3.5 h-3.5" />
                                                Missing Domain Experience
                                            </h4>
                                            <div className="flex flex-wrap gap-1.5">
                                                {job.missing_domains?.map(domain => (
                                                    <SkillTag key={domain} skill={domain} variant="domain" />
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* AI Analysis */}
                                    {job.gemini_reasoning && (
                                        <div className="space-y-2">
                                            <h4 className="text-xs font-semibold uppercase tracking-wider text-violet-600 dark:text-violet-400 flex items-center gap-1.5">
                                                <Sparkles className="w-3.5 h-3.5" />
                                                AI Analysis
                                            </h4>
                                            <p className="text-sm text-muted-foreground leading-relaxed">
                                                {job.gemini_reasoning}
                                            </p>
                                        </div>
                                    )}

                                    {/* AI Strengths & Gaps */}
                                    {((job.gemini_strengths?.length ?? 0) > 0 || (job.gemini_gaps?.length ?? 0) > 0) && (
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            {/* Strengths */}
                                            {(job.gemini_strengths?.length ?? 0) > 0 && (
                                                <div className="space-y-2">
                                                    <h4 className="text-xs font-semibold uppercase tracking-wider text-violet-600 dark:text-violet-400 flex items-center gap-1.5">
                                                        <TrendingUp className="w-3.5 h-3.5" />
                                                        AI-Identified Strengths
                                                    </h4>
                                                    <div className="flex flex-wrap gap-1.5">
                                                        {job.gemini_strengths?.map((s, i) => (
                                                            <span key={i} className="inline-flex px-2 py-0.5 text-[11px] font-medium rounded-md border bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/20">
                                                                {s}
                                                            </span>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Gaps */}
                                            {(job.gemini_gaps?.length ?? 0) > 0 && (
                                                <div className="space-y-2">
                                                    <h4 className="text-xs font-semibold uppercase tracking-wider text-orange-600 dark:text-orange-400 flex items-center gap-1.5">
                                                        <AlertCircle className="w-3.5 h-3.5" />
                                                        AI-Identified Gaps
                                                    </h4>
                                                    <div className="flex flex-wrap gap-1.5">
                                                        {job.gemini_gaps?.map((g, i) => (
                                                            <span key={i} className="inline-flex px-2 py-0.5 text-[11px] font-medium rounded-md border bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20">
                                                                {g}
                                                            </span>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Job Summary */}
                                    {job.summary && (
                                        <div className="space-y-2">
                                            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                                Job Summary
                                            </h4>
                                            <p className="text-sm text-muted-foreground leading-relaxed">
                                                {job.summary}
                                            </p>
                                        </div>
                                    )}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </CardContent>
            </Card>
        </motion.div>
    );
}

export function JobMatches() {
    const [minScore, setMinScore] = useState(0);
    const [maxScore, setMaxScore] = useState(100);
    const [search, setSearch] = useState('');
    const [recency, setRecency] = useState<string>('7');
    const [sortOrder, setSortOrder] = useState<string>('score_desc');

    const sortBy = sortOrder.startsWith('date') ? 'date' : 'score';
    const sortDirection = sortOrder.endsWith('asc') ? 'asc' : 'desc';

    const { data, isLoading, error } = useJobs({
        min_score: minScore,
        max_score: maxScore < 100 ? maxScore : undefined,
        search: search || undefined,
        recency_days: recency === 'all' ? undefined : Number(recency),
        limit: 100,
        sort_by: sortBy,
        sort_order: sortDirection,
    });

    // Stats
    const totalJobs = data?.jobs.length || 0;
    const highMatches = data?.jobs.filter(j => j.match_score >= 70).length || 0;
    const avgScore = totalJobs > 0
        ? Math.round(data!.jobs.reduce((sum, j) => sum + j.match_score, 0) / totalJobs)
        : 0;

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="space-y-1">
                <motion.h1
                    className="text-3xl font-bold tracking-tight"
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                >
                    Job Matches
                </motion.h1>
                <motion.p
                    className="text-muted-foreground"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.1 }}
                >
                    Analyze your match quality against job requirements
                </motion.p>
            </div>

            {/* Stats Bar */}
            {!isLoading && totalJobs > 0 && (
                <motion.div
                    className="grid grid-cols-3 gap-4"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                >
                    <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 border border-border/50">
                        <div className="p-2 rounded-md bg-primary/10">
                            <Briefcase className="w-4 h-4 text-primary" />
                        </div>
                        <div>
                            <p className="text-2xl font-bold tabular-nums">{totalJobs}</p>
                            <p className="text-xs text-muted-foreground">Total Matches</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 border border-border/50">
                        <div className="p-2 rounded-md bg-emerald-500/10">
                            <TrendingUp className="w-4 h-4 text-emerald-500" />
                        </div>
                        <div>
                            <p className="text-2xl font-bold tabular-nums">{highMatches}</p>
                            <p className="text-xs text-muted-foreground">High Quality (70%+)</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 border border-border/50">
                        <div className="p-2 rounded-md bg-violet-500/10">
                            <Sparkles className="w-4 h-4 text-violet-500" />
                        </div>
                        <div>
                            <p className="text-2xl font-bold tabular-nums">{avgScore}%</p>
                            <p className="text-xs text-muted-foreground">Average Score</p>
                        </div>
                    </div>
                </motion.div>
            )}

            {/* Filters */}
            <motion.div
                className="flex flex-col lg:flex-row gap-4 p-4 rounded-xl bg-card border border-border/50"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15 }}
            >
                {/* Search */}
                <div className="flex-1">
                    <div className="relative">
                        <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <Input
                            placeholder="Search jobs or companies..."
                            className="pl-9 bg-background/50"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>
                </div>

                {/* Score Range */}
                <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground whitespace-nowrap">Score:</span>
                    <Input
                        type="number"
                        value={minScore}
                        onChange={(e) => setMinScore(Number(e.target.value))}
                        className="w-16 h-9 text-center bg-background/50"
                        min={0}
                        max={100}
                    />
                    <span className="text-muted-foreground">—</span>
                    <Input
                        type="number"
                        value={maxScore}
                        onChange={(e) => setMaxScore(Number(e.target.value))}
                        className="w-16 h-9 text-center bg-background/50"
                        min={0}
                        max={100}
                    />
                </div>

                {/* Recency */}
                <Select value={recency} onValueChange={setRecency}>
                    <SelectTrigger className="w-[140px] bg-background/50">
                        <SelectValue placeholder="Period" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="1">Last 24 Hours</SelectItem>
                        <SelectItem value="3">Last 3 Days</SelectItem>
                        <SelectItem value="7">Last 7 Days</SelectItem>
                        <SelectItem value="14">Last 14 Days</SelectItem>
                        <SelectItem value="30">Last Month</SelectItem>
                        <SelectItem value="all">All Time</SelectItem>
                    </SelectContent>
                </Select>

                {/* Sort */}
                <Select value={sortOrder} onValueChange={setSortOrder}>
                    <SelectTrigger className="w-[150px] bg-background/50">
                        <SelectValue placeholder="Sort" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="score_desc">Score: High → Low</SelectItem>
                        <SelectItem value="score_asc">Score: Low → High</SelectItem>
                        <SelectItem value="date_desc">Date: Newest</SelectItem>
                        <SelectItem value="date_asc">Date: Oldest</SelectItem>
                    </SelectContent>
                </Select>
            </motion.div>

            {/* Job Cards */}
            <div className="space-y-3">
                {isLoading ? (
                    <div className="flex flex-col items-center justify-center py-16 gap-4">
                        <motion.div
                            className="w-12 h-12 rounded-full border-2 border-primary border-t-transparent"
                            animate={{ rotate: 360 }}
                            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                        />
                        <p className="text-muted-foreground">Loading matches...</p>
                    </div>
                ) : error ? (
                    <div className="flex flex-col items-center justify-center py-16 gap-2 text-destructive">
                        <AlertCircle className="w-8 h-8" />
                        <p>Failed to load matches. Please try again.</p>
                    </div>
                ) : data?.jobs.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-16 gap-2 text-muted-foreground">
                        <SearchIcon className="w-8 h-8" />
                        <p>No matches found. Try adjusting your filters.</p>
                    </div>
                ) : (
                    data?.jobs.map((job, index) => (
                        <JobCard key={job.id} job={job} index={index} />
                    ))
                )}
            </div>
        </div>
    );
}
