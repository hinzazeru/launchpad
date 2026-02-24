import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useJobs, useAnalyticsMarket, useUpdateJobStatus } from '@/services/api';
import type { Job } from '@/services/api';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
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
    Lightbulb,
    Bot,
    Heart,
    EyeOff,
    SlidersHorizontal,
    Microscope,
} from 'lucide-react';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';

// Score breakdown for tooltip
interface ScoreBreakdown {
    skills_score?: number;
    experience_score?: number;
    seniority_fit?: number;
    domain_score?: number;
    match_engine?: string;
    match_confidence?: number;
}

// Radial Progress Component - The hero visual element
function RadialScore({
    score,
    size = 72,
    strokeWidth = 6,
    breakdown
}: {
    score: number;
    size?: number;
    strokeWidth?: number;
    breakdown?: ScoreBreakdown;
}) {
    const [showTooltip, setShowTooltip] = useState(false);

    // Dismiss on outside click — enables tap-to-show on mobile
    useEffect(() => {
        if (!showTooltip) return;
        const dismiss = () => setShowTooltip(false);
        document.addEventListener('click', dismiss);
        return () => document.removeEventListener('click', dismiss);
    }, [showTooltip]);

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

    const hasBreakdown = breakdown && (
        breakdown.skills_score !== undefined ||
        breakdown.experience_score !== undefined ||
        breakdown.domain_score !== undefined
    );

    return (
        <div
            className={`relative ${hasBreakdown ? 'cursor-pointer' : ''}`}
            style={{ width: size, height: size }}
            onMouseEnter={() => hasBreakdown && setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
            onClick={(e) => {
                if (hasBreakdown) {
                    e.stopPropagation(); // prevent card expand
                    setShowTooltip(v => !v);
                }
            }}
        >
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

            {/* Score Breakdown Tooltip */}
            <AnimatePresence>
                {showTooltip && hasBreakdown && (
                    <motion.div
                        initial={{ opacity: 0, y: 5, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 5, scale: 0.95 }}
                        transition={{ duration: 0.15 }}
                        className="absolute left-1/2 -translate-x-1/2 top-full mt-2 z-50 min-w-[160px] p-2.5 rounded-lg bg-popover border border-border shadow-lg"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="space-y-1.5">
                            <div className="flex items-center justify-between text-[11px] pb-1.5 border-b border-border/50">
                                <span className="font-semibold text-foreground">Score Breakdown</span>
                                {breakdown.match_engine && (
                                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium ${breakdown.match_engine === 'gemini'
                                        ? 'bg-violet-500/15 text-violet-500'
                                        : 'bg-blue-500/15 text-blue-500'
                                        }`}>
                                        {breakdown.match_engine === 'gemini' ? 'AI' : 'NLP'}
                                    </span>
                                )}
                            </div>
                            {breakdown.skills_score !== undefined && (
                                <div className="flex items-center justify-between text-[11px]">
                                    <span className="text-muted-foreground">Skills</span>
                                    <span className="font-mono font-medium text-blue-500">{breakdown.skills_score}</span>
                                </div>
                            )}
                            {breakdown.experience_score !== undefined && (
                                <div className="flex items-center justify-between text-[11px]">
                                    <span className="text-muted-foreground">Experience</span>
                                    <span className="font-mono font-medium text-violet-500">{breakdown.experience_score}</span>
                                </div>
                            )}
                            {breakdown.seniority_fit !== undefined && (
                                <div className="flex items-center justify-between text-[11px]">
                                    <span className="text-muted-foreground">Seniority</span>
                                    <span className="font-mono font-medium text-purple-500">{breakdown.seniority_fit}</span>
                                </div>
                            )}
                            {breakdown.domain_score !== undefined && (
                                <div className="flex items-center justify-between text-[11px]">
                                    <span className="text-muted-foreground">Domain</span>
                                    <span className="font-mono font-medium text-cyan-500">{breakdown.domain_score}</span>
                                </div>
                            )}
                            {breakdown.match_confidence !== undefined && (
                                <div className="flex items-center justify-between text-[10px] pt-1 border-t border-border/50 text-muted-foreground">
                                    <span>Confidence</span>
                                    <span className="font-mono">{Math.round(breakdown.match_confidence * 100)}%</span>
                                </div>
                            )}
                        </div>
                        {/* Tooltip arrow */}
                        <div className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-3 h-3 rotate-45 bg-popover border-l border-t border-border" />
                    </motion.div>
                )}
            </AnimatePresence>
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
function JobCard({ job, index, onStatusChange }: { job: Job; index: number; onStatusChange: (jobId: number, status: string | null) => void }) {
    const [isExpanded, setIsExpanded] = useState(false);
    const navigate = useNavigate();

    const handleAnalyze = (jobId: string) => {
        navigate('/analyze', { state: { jobId } });
    };

    // Parse experience
    let resumeYears = 0;
    const requiredYears = job.experience_required || 0;
    if (job.experience_alignment) {
        const match = job.experience_alignment.match(/Resume:\s*([\d.]+)\s*years/i);
        if (match) resumeYears = parseFloat(match[1]);
    }

    const isHearted = job.user_status === 'hearted';
    const isIgnored = job.user_status === 'ignored';
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
                    } ${isIgnored ? 'opacity-50' : ''}`}
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
                            <RadialScore
                                score={job.match_score}
                                breakdown={{
                                    skills_score: job.skills_score,
                                    experience_score: job.experience_score,
                                    seniority_fit: job.seniority_fit,
                                    domain_score: job.domain_score,
                                    match_engine: job.match_engine,
                                    match_confidence: job.match_confidence
                                }}
                            />
                            {job.gemini_score !== undefined && job.gemini_score > 0 && job.gemini_score <= 100 && (
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
                                    <div className="flex items-center gap-2 min-w-0">
                                        <a
                                            href={job.url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            onClick={(e) => e.stopPropagation()}
                                            className="font-semibold text-[15px] leading-tight hover:text-primary transition-colors line-clamp-1 group-hover:underline decoration-primary/30 underline-offset-2"
                                        >
                                            {job.title}
                                        </a>
                                        {/* AI/NLP Engine Badge */}
                                        {job.match_engine && (
                                            <span
                                                className={`flex-shrink-0 inline-flex items-center gap-1 px-1.5 py-0.5 text-[9px] font-semibold rounded-full uppercase tracking-wider ${job.match_engine === 'gemini'
                                                    ? 'bg-violet-500/15 text-violet-600 dark:text-violet-400 border border-violet-500/30'
                                                    : 'bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/30'
                                                    }`}
                                                title={job.match_engine === 'gemini' ? 'AI-powered matching with Gemini' : 'NLP-based matching'}
                                            >
                                                {job.match_engine === 'gemini' ? (
                                                    <>
                                                        <Bot className="w-2.5 h-2.5" />
                                                        AI
                                                    </>
                                                ) : (
                                                    'NLP'
                                                )}
                                            </span>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-1 flex-shrink-0">
                                        <button
                                            onClick={(e) => { e.stopPropagation(); onStatusChange(job.id, isHearted ? null : 'hearted'); }}
                                            className={`p-1 rounded-md transition-colors ${isHearted
                                                ? 'text-red-500 hover:text-red-600'
                                                : 'text-muted-foreground/40 hover:text-red-400'
                                                }`}
                                            title={isHearted ? 'Remove from favorites' : 'Add to favorites'}
                                        >
                                            <Heart className={`w-4 h-4 ${isHearted ? 'fill-current' : ''}`} />
                                        </button>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); onStatusChange(job.id, isIgnored ? null : 'ignored'); }}
                                            className={`p-1 rounded-md transition-colors ${isIgnored
                                                ? 'text-amber-500 hover:text-amber-600'
                                                : 'text-muted-foreground/40 hover:text-muted-foreground'
                                                }`}
                                            title={isIgnored ? 'Un-ignore' : 'Ignore this match'}
                                        >
                                            <EyeOff className="w-4 h-4" />
                                        </button>
                                        <a
                                            href={job.url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            onClick={(e) => e.stopPropagation()}
                                            className="p-1 rounded-md hover:bg-muted/50 text-muted-foreground hover:text-primary transition-colors"
                                        >
                                            <ExternalLink className="w-4 h-4" />
                                        </a>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleAnalyze(String(job.id)); }}
                                            className="p-1.5 rounded-full text-gray-400 hover:text-purple-500 hover:bg-purple-50 transition-colors"
                                            title="Analyze resume for this role"
                                        >
                                            <Microscope className="w-4 h-4" />
                                        </button>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3 text-sm text-muted-foreground flex-wrap">
                                    <span className="flex items-center gap-1.5 font-medium">
                                        <Building2 className="w-3.5 h-3.5" />
                                        {job.company}
                                    </span>

                                    {/* Job Domains - Moved to Header */}
                                    {job.domains && job.domains.length > 0 && (
                                        <div className="flex items-center gap-1.5">
                                            {job.domains.slice(0, 2).map(domain => (
                                                <span key={domain} className="inline-flex px-2 py-0.5 text-[10px] font-medium rounded-md border bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20">
                                                    {domain}
                                                </span>
                                            ))}
                                            {job.domains.length > 2 && (
                                                <span className="text-[10px] text-muted-foreground font-medium">
                                                    +{job.domains.length - 2}
                                                </span>
                                            )}
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
                                    {job.is_repost && (
                                        <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                                            ↺ Reposted{job.repost_count && job.repost_count > 1 ? ` ×${job.repost_count}` : ''}
                                        </span>
                                    )}
                                </div>
                            </div>

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

                                    {/* AI Analysis - New AI Matcher */}
                                    {job.match_engine === 'gemini' && (
                                        <div className="space-y-4">
                                            {/* Score Breakdown */}
                                            {(job.skills_score || job.experience_score || job.domain_score) && (
                                                <div className="grid grid-cols-4 gap-2 text-center">
                                                    <div className="p-2 rounded-md bg-background/50">
                                                        <p className="text-lg font-bold text-blue-500">{job.skills_score ?? '-'}</p>
                                                        <p className="text-[10px] text-muted-foreground">Skills</p>
                                                    </div>
                                                    <div className="p-2 rounded-md bg-background/50">
                                                        <p className="text-lg font-bold text-violet-500">{job.experience_score ?? '-'}</p>
                                                        <p className="text-[10px] text-muted-foreground">Experience</p>
                                                    </div>
                                                    <div className="p-2 rounded-md bg-background/50">
                                                        <p className="text-lg font-bold text-purple-500">{job.seniority_fit ?? '-'}</p>
                                                        <p className="text-[10px] text-muted-foreground">Seniority</p>
                                                    </div>
                                                    <div className="p-2 rounded-md bg-background/50">
                                                        <p className="text-lg font-bold text-cyan-500">{job.domain_score ?? '-'}</p>
                                                        <p className="text-[10px] text-muted-foreground">Domain</p>
                                                    </div>
                                                </div>
                                            )}

                                            {/* AI Strengths */}
                                            {(job.ai_strengths?.length ?? 0) > 0 && (
                                                <div className="space-y-2">
                                                    <h4 className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                                                        <TrendingUp className="w-3.5 h-3.5" />
                                                        Strengths
                                                    </h4>
                                                    <ul className="space-y-1">
                                                        {job.ai_strengths?.map((s, i) => (
                                                            <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                                                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 mt-0.5 flex-shrink-0" />
                                                                {s}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}

                                            {/* AI Concerns */}
                                            {(job.ai_concerns?.length ?? 0) > 0 && (
                                                <div className="space-y-2">
                                                    <h4 className="text-xs font-semibold text-amber-600 dark:text-amber-400 flex items-center gap-1.5">
                                                        <AlertCircle className="w-3.5 h-3.5" />
                                                        Concerns
                                                    </h4>
                                                    <ul className="space-y-1">
                                                        {job.ai_concerns?.map((c, i) => (
                                                            <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                                                                <XCircle className="w-3.5 h-3.5 text-amber-500 mt-0.5 flex-shrink-0" />
                                                                {c}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}

                                            {/* AI Recommendations */}
                                            {(job.ai_recommendations?.length ?? 0) > 0 && (
                                                <div className="space-y-2">
                                                    <h4 className="text-xs font-semibold text-blue-600 dark:text-blue-400 flex items-center gap-1.5">
                                                        <Lightbulb className="w-3.5 h-3.5" />
                                                        Recommendations
                                                    </h4>
                                                    <ul className="space-y-1">
                                                        {job.ai_recommendations?.map((r, i) => (
                                                            <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                                                                <span className="text-blue-500 mt-0.5 flex-shrink-0">→</span>
                                                                {r}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}

                                            {/* Skill Gaps with Transferability */}
                                            {(job.skill_gaps_detailed?.length ?? 0) > 0 && (
                                                <div className="space-y-2">
                                                    <h4 className="text-xs font-semibold text-red-600 dark:text-red-400 flex items-center gap-1.5">
                                                        <XCircle className="w-3.5 h-3.5" />
                                                        Skill Gaps
                                                    </h4>
                                                    <div className="space-y-1">
                                                        {job.skill_gaps_detailed?.map((gap, i) => (
                                                            <div key={i} className="flex items-center gap-2 text-sm">
                                                                <span className={`px-2 py-0.5 text-[11px] font-medium rounded-md border ${gap.importance === 'must_have'
                                                                    ? 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20'
                                                                    : 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
                                                                    }`}>
                                                                    {gap.skill}
                                                                </span>
                                                                {gap.transferable_from && (
                                                                    <span className="text-xs text-muted-foreground">
                                                                        ← transferable from <span className="text-emerald-500">{gap.transferable_from}</span>
                                                                    </span>
                                                                )}
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Legacy AI Analysis (old re-ranker) */}
                                    {job.match_engine !== 'gemini' && job.gemini_reasoning && (
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

                                    {/* Legacy AI Strengths & Gaps (old re-ranker) */}
                                    {job.match_engine !== 'gemini' && ((job.gemini_strengths?.length ?? 0) > 0 || (job.gemini_gaps?.length ?? 0) > 0) && (
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
                                    <div className="flex items-center justify-between">
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleAnalyze(String(job.id)); }}
                                            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm font-medium transition-colors"
                                        >
                                            <Microscope className="w-4 h-4" />
                                            Analyze Resume
                                        </button>
                                        <span className="font-mono text-[10px] text-muted-foreground/40">
                                            #{job.id}
                                        </span>
                                    </div>
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
    // Read URL params for initial filter values
    const [searchParams] = useSearchParams();
    const initialMinScore = Number(searchParams.get('minScore')) || 0;

    const [minScore, setMinScore] = useState(initialMinScore);
    const [maxScore, setMaxScore] = useState(100);
    const [search, setSearch] = useState('');
    const [companyFilter, setCompanyFilter] = useState<string>('');
    const [locationRegion, setLocationRegion] = useState<string>('');
    const [recency, setRecency] = useState<string>('all'); // Default to 'all' when coming from Analytics
    const [sortOrder, setSortOrder] = useState<string>('score_desc');
    const [showIgnored, setShowIgnored] = useState(false);
    const [heartedOnly, setHeartedOnly] = useState(false);
    const [filtersOpen, setFiltersOpen] = useState(false);

    const updateStatusMutation = useUpdateJobStatus();

    const { data: marketData } = useAnalyticsMarket(10, 60);

    const sortBy = sortOrder.startsWith('date') ? 'date' : 'score';
    const sortDirection = sortOrder.endsWith('asc') ? 'asc' : 'desc';

    const effectiveSearch = companyFilter || search || undefined;

    const { data, isLoading, error } = useJobs({
        min_score: minScore,
        max_score: maxScore < 100 ? maxScore : undefined,
        search: effectiveSearch,
        location_region: locationRegion || undefined,
        recency_days: recency === 'all' ? undefined : Number(recency),
        limit: 100,
        sort_by: sortBy,
        sort_order: sortDirection,
        show_ignored: showIgnored || undefined,
        hearted_only: heartedOnly || undefined,
    });

    const handleStatusChange = (jobId: number, status: string | null) => {
        updateStatusMutation.mutate({ jobId, userStatus: status });
    };

    // Stats
    const totalJobs = data?.jobs.length || 0;
    const highMatches = data?.jobs.filter(j => j.match_score >= 85).length || 0;
    const avgScore = totalJobs > 0
        ? Math.round(data!.jobs.reduce((sum, j) => sum + j.match_score, 0) / totalJobs)
        : 0;
    const aiMatches = data?.jobs.filter(j => j.match_engine === 'gemini').length || 0;
    const nlpMatches = totalJobs - aiMatches;

    const activeFilterCount = [
        search !== '',
        companyFilter !== '',
        locationRegion !== '',
        minScore !== 0,
        maxScore !== 100,
        heartedOnly,
        showIgnored,
        recency !== 'all',
    ].filter(Boolean).length;

    // Aggregated AI Insights
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
                    className="grid grid-cols-2 sm:grid-cols-4 gap-2"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                >
                    <div className="flex items-center gap-2 p-2 sm:p-3 rounded-lg bg-muted/30 border border-border/50">
                        <div className="p-1.5 rounded-md bg-primary/10 flex-shrink-0">
                            <Briefcase className="w-3.5 h-3.5 text-primary" />
                        </div>
                        <div className="min-w-0">
                            <p className="text-lg sm:text-2xl font-bold tabular-nums leading-tight">{totalJobs}</p>
                            <p className="text-[10px] sm:text-xs text-muted-foreground truncate">Total Matches</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2 p-2 sm:p-3 rounded-lg bg-muted/30 border border-border/50">
                        <div className="p-1.5 rounded-md bg-emerald-500/10 flex-shrink-0">
                            <TrendingUp className="w-3.5 h-3.5 text-emerald-500" />
                        </div>
                        <div className="min-w-0">
                            <p className="text-lg sm:text-2xl font-bold tabular-nums leading-tight">{highMatches}</p>
                            <p className="text-[10px] sm:text-xs text-muted-foreground truncate">High Quality (85+)</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2 p-2 sm:p-3 rounded-lg bg-muted/30 border border-border/50">
                        <div className="p-1.5 rounded-md bg-violet-500/10 flex-shrink-0">
                            <Sparkles className="w-3.5 h-3.5 text-violet-500" />
                        </div>
                        <div className="min-w-0">
                            <p className="text-lg sm:text-2xl font-bold tabular-nums leading-tight">{avgScore}%</p>
                            <p className="text-[10px] sm:text-xs text-muted-foreground truncate">Avg Score</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2 p-2 sm:p-3 rounded-lg bg-muted/30 border border-border/50">
                        <div className="p-1.5 rounded-md bg-violet-500/10 flex-shrink-0">
                            <Bot className="w-3.5 h-3.5 text-violet-500" />
                        </div>
                        <div className="min-w-0">
                            <p className="text-lg sm:text-2xl font-bold tabular-nums leading-tight">
                                {aiMatches}<span className="text-xs sm:text-sm font-normal text-muted-foreground">/{nlpMatches}</span>
                            </p>
                            <p className="text-[10px] sm:text-xs text-muted-foreground truncate">AI / NLP</p>
                        </div>
                    </div>
                </motion.div>
            )}

            {/* Filters */}
            <motion.div
                className="space-y-2"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15 }}
            >
                {/* Mobile toggle — hidden on lg+ where filters are always visible */}
                <button
                    className="lg:hidden flex items-center gap-2 w-full px-4 py-2.5 rounded-xl bg-card border border-border/50 hover:bg-muted/50 active:bg-muted transition-colors text-sm font-medium"
                    onClick={() => setFiltersOpen(!filtersOpen)}
                >
                    <SlidersHorizontal className="w-4 h-4 text-muted-foreground" />
                    Filters
                    {activeFilterCount > 0 && (
                        <span className="inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 text-[10px] font-bold rounded-full bg-primary text-primary-foreground">
                            {activeFilterCount}
                        </span>
                    )}
                    <ChevronDown className={`w-4 h-4 ml-auto text-muted-foreground transition-transform duration-200 ${filtersOpen ? 'rotate-180' : ''}`} />
                </button>

                {/* Filter content — hidden on mobile when closed, always shown on lg+ */}
                <div className={`flex-col gap-3 p-4 rounded-xl bg-card border border-border/50 ${filtersOpen ? 'flex' : 'hidden'} lg:flex lg:flex-row`}>
                    {/* Search */}
                    <div className="flex-1">
                        <div className="relative">
                            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                            <Input
                                placeholder="Search jobs or companies..."
                                className="pl-9 bg-background/50"
                                value={search}
                                onChange={(e) => {
                                    setSearch(e.target.value);
                                    if (e.target.value) setCompanyFilter('');
                                }}
                            />
                        </div>
                    </div>

                    {/* Top Companies Filter */}
                    {marketData?.top_companies && marketData.top_companies.length > 0 && (
                        <Select
                            value={companyFilter}
                            onValueChange={(value) => {
                                setCompanyFilter(value === '__all__' ? '' : value);
                                if (value !== '__all__') setSearch('');
                            }}
                        >
                            <SelectTrigger className="w-full lg:w-[200px] bg-background/50">
                                <Building2 className="w-3.5 h-3.5 mr-1.5 text-muted-foreground" />
                                <SelectValue placeholder="Company" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="__all__">All Companies</SelectItem>
                                {marketData.top_companies.map((company) => (
                                    <SelectItem key={company.name} value={company.name}>
                                        {company.name} ({company.count})
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    )}

                    {/* Location Region Filter */}
                    <Select
                        value={locationRegion || '__all__'}
                        onValueChange={(value) => setLocationRegion(value === '__all__' ? '' : value)}
                    >
                        <SelectTrigger className="w-full lg:w-[170px] bg-background/50">
                            <MapPin className="w-3.5 h-3.5 mr-1.5 text-muted-foreground" />
                            <SelectValue placeholder="Location" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="__all__">All Locations</SelectItem>
                            <SelectItem value="us">US</SelectItem>
                            <SelectItem value="canada">Canada</SelectItem>
                            <SelectItem value="remote">Remote</SelectItem>
                        </SelectContent>
                    </Select>

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

                    {/* Sort */}
                    <Select value={sortOrder} onValueChange={setSortOrder}>
                        <SelectTrigger className="w-full lg:w-[150px] bg-background/50">
                            <SelectValue placeholder="Sort" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="score_desc">Score: High → Low</SelectItem>
                            <SelectItem value="score_asc">Score: Low → High</SelectItem>
                            <SelectItem value="date_desc">Date: Newest</SelectItem>
                            <SelectItem value="date_asc">Date: Oldest</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </motion.div>

            {/* Time Period Filter Buttons */}
            <div className="space-y-2">
                {/* Period buttons — horizontal scroll on mobile, wrap on sm+ */}
                <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 [scrollbar-width:none] [-webkit-overflow-scrolling:touch]">
                    <span className="text-xs text-muted-foreground flex-shrink-0">Show:</span>
                    {[
                        { value: '1', label: '24h' },
                        { value: '3', label: '3 days' },
                        { value: '7', label: '7 days' },
                        { value: '14', label: '14 days' },
                        { value: '30', label: '30 days' },
                        { value: 'all', label: 'All time' },
                    ].map((option) => (
                        <Button
                            key={option.value}
                            variant={recency === option.value ? 'default' : 'outline'}
                            size="sm"
                            className={`h-7 px-3 text-xs flex-shrink-0 ${recency === option.value
                                ? 'bg-primary text-primary-foreground'
                                : 'bg-background/50 hover:bg-muted'
                                }`}
                            onClick={() => setRecency(option.value)}
                        >
                            {option.label}
                        </Button>
                    ))}
                </div>

                {/* Status filters on their own row */}
                <div className="flex items-center gap-3">
                    <div className="w-px h-5 bg-border" />
                    <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer select-none">
                        <input
                            type="checkbox"
                            checked={heartedOnly}
                            onChange={(e) => { setHeartedOnly(e.target.checked); if (e.target.checked) setShowIgnored(false); }}
                            className="rounded border-border"
                        />
                        <Heart className="w-3 h-3 text-red-500" />
                        Hearted only
                    </label>
                    <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer select-none">
                        <input
                            type="checkbox"
                            checked={showIgnored}
                            onChange={(e) => { setShowIgnored(e.target.checked); if (e.target.checked) setHeartedOnly(false); }}
                            className="rounded border-border"
                        />
                        <EyeOff className="w-3 h-3" />
                        Show ignored
                    </label>
                </div>
            </div>

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
                        <JobCard key={job.id} job={job} index={index} onStatusChange={handleStatusChange} />
                    ))
                )}
            </div>
        </div>
    );
}
