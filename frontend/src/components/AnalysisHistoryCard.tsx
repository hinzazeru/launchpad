import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useMatchSuggestions, useSaveLikedBullet } from '@/services/api';
import type { AnalysisHistoryItem } from '@/services/api';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Building2,
  Calendar,
  MapPin,
  Sparkles,
  FileText,
  TrendingUp,
  AlertTriangle,
  ExternalLink,
  ChevronDown,
  Loader2,
  ArrowRight,
  Briefcase,
  Bot,
  Heart,
  Check,
} from 'lucide-react';

// Radial Progress Component for score display
function RadialScore({ score, size = 64, strokeWidth = 5 }: { score: number; size?: number; strokeWidth?: number }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (score / 100) * circumference;

  const getGradientColors = () => {
    if (score >= 75) return { start: '#10b981', end: '#34d399' };
    if (score >= 60) return { start: '#f59e0b', end: '#fbbf24' };
    return { start: '#ef4444', end: '#f87171' };
  };

  const colors = getGradientColors();
  const gradientId = `history-score-${score}-${Math.random().toString(36).substr(2, 9)}`;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={colors.start} />
            <stop offset="100%" stopColor={colors.end} />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-muted/30"
        />
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
          transition={{ duration: 0.8, ease: 'easeOut', delay: 0.2 }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <motion.span
          className="text-base font-bold tabular-nums tracking-tight"
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

interface AnalysisHistoryCardProps {
  item: AnalysisHistoryItem;
  index: number;
  onSelect: (jobId: number, resumeId: number) => void;
}

export function AnalysisHistoryCard({ item, index, onSelect }: AnalysisHistoryCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [savedSuggestions, setSavedSuggestions] = useState<Set<string>>(new Set());

  // Only fetch suggestions when expanded
  const { data: suggestionsData, isLoading: suggestionsLoading } = useMatchSuggestions(
    isExpanded ? item.match_id : null
  );

  // Mutation for saving bullets
  const saveBulletMutation = useSaveLikedBullet();

  // Generate a unique key for a suggestion
  const getSuggestionKey = (roleKey: string, bulletIndex: number, suggestionIndex: number) =>
    `${roleKey}-${bulletIndex}-${suggestionIndex}`;

  // Handle saving a suggestion
  const handleSaveSuggestion = (
    roleTitle: string,
    company: string,
    originalText: string,
    rewrittenText: string,
    suggestionKey: string
  ) => {
    if (savedSuggestions.has(suggestionKey)) return;

    saveBulletMutation.mutate(
      {
        original_text: originalText,
        rewritten_text: rewrittenText,
        role_title: roleTitle,
        company: company,
        job_id: item.job_id,
      },
      {
        onSuccess: () => {
          setSavedSuggestions((prev) => new Set([...prev, suggestionKey]));
        },
      }
    );
  };

  const scoreColor =
    item.match_score >= 75
      ? 'from-emerald-500 to-emerald-400'
      : item.match_score >= 60
      ? 'from-amber-500 to-amber-400'
      : 'from-red-500 to-red-400';

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  // Calculate totals from roles summary
  const totalBullets = item.roles_summary.reduce((sum, role) => sum + role.bullet_count, 0);
  const rolesWithSuggestions = item.roles_summary.filter((r) => r.has_suggestions).length;

  const handleAiClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsExpanded(!isExpanded);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.05 }}
    >
      <Card className="group relative overflow-hidden transition-all duration-300 hover:shadow-lg hover:shadow-primary/5 border-border/50">
        {/* Score indicator strip */}
        <div className={`absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b ${scoreColor}`} />

        <CardContent className="p-0">
          {/* Main content - clickable to load analysis */}
          <div
            className="flex gap-4 p-4 pl-5 cursor-pointer"
            onClick={() => onSelect(item.job_id, item.resume_id)}
          >
            {/* Score */}
            <div className="shrink-0">
              <RadialScore score={item.match_score} size={64} strokeWidth={5} />
            </div>

            {/* Main content */}
            <div className="flex-1 min-w-0 space-y-2">
              {/* Job title and company */}
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="font-semibold text-sm truncate group-hover:text-primary transition-colors">
                    {item.job_title}
                  </h3>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Building2 className="w-3 h-3" />
                      {item.job_company}
                    </span>
                    {item.job_location && (
                      <span className="flex items-center gap-1">
                        <MapPin className="w-3 h-3" />
                        {item.job_location}
                      </span>
                    )}
                  </div>
                </div>

                {/* Engine badge */}
                <div className="flex items-center gap-1.5 shrink-0">
                  <Badge
                    variant="outline"
                    className={`text-[10px] px-1.5 py-0 h-5 ${
                      item.match_engine === 'gemini'
                        ? 'bg-violet-500/10 text-violet-600 border-violet-500/20'
                        : 'bg-blue-500/10 text-blue-600 border-blue-500/20'
                    }`}
                  >
                    {item.match_engine === 'gemini' ? 'AI' : 'NLP'}
                  </Badge>
                </div>
              </div>

              {/* Roles and bullets summary */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  <FileText className="w-3 h-3" />
                  {item.roles_summary.length} role{item.roles_summary.length !== 1 ? 's' : ''}
                </span>
                <span className="text-xs text-muted-foreground">|</span>
                <span className="text-xs text-muted-foreground">{totalBullets} bullets</span>

                {item.has_bullet_suggestions && (
                  <>
                    <span className="text-xs text-muted-foreground">|</span>
                    <button
                      onClick={handleAiClick}
                      className="flex items-center gap-1 text-xs text-emerald-600 hover:text-emerald-500 transition-colors font-medium"
                    >
                      <Sparkles className="w-3 h-3" />
                      {rolesWithSuggestions} with AI
                      <ChevronDown
                        className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                      />
                    </button>
                  </>
                )}
              </div>

              {/* AI insights counts */}
              {(item.ai_strengths_count > 0 || item.ai_concerns_count > 0) && (
                <div className="flex gap-3">
                  {item.ai_strengths_count > 0 && (
                    <span className="flex items-center gap-1 text-[11px] text-emerald-600">
                      <TrendingUp className="w-3 h-3" />
                      {item.ai_strengths_count} strengths
                    </span>
                  )}
                  {item.ai_concerns_count > 0 && (
                    <span className="flex items-center gap-1 text-[11px] text-amber-600">
                      <AlertTriangle className="w-3 h-3" />
                      {item.ai_concerns_count} concerns
                    </span>
                  )}
                </div>
              )}

              {/* Date and action */}
              <div className="flex items-center justify-between pt-1">
                <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
                  <Calendar className="w-3 h-3" />
                  {formatDate(item.generated_date)}
                </span>

                {item.job_url && (
                  <a
                    href={item.job_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-primary transition-colors"
                  >
                    <ExternalLink className="w-3 h-3" />
                    View posting
                  </a>
                )}
              </div>
            </div>
          </div>

          {/* Expandable AI Suggestions Section */}
          <AnimatePresence>
            {isExpanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="border-t border-border/50 bg-muted/20 p-4 pl-5 space-y-6">
                  {/* Section header */}
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-violet-500/10">
                      <Bot className="w-4 h-4 text-violet-600 dark:text-violet-400" />
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold">AI Bullet Suggestions</h4>
                      <p className="text-xs text-muted-foreground">
                        {suggestionsData?.total_with_suggestions || 0} bullets with suggestions
                      </p>
                    </div>
                  </div>

                  {suggestionsLoading ? (
                    <div className="flex items-center justify-center py-8 gap-2 text-muted-foreground">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span className="text-sm">Loading suggestions...</span>
                    </div>
                  ) : suggestionsData?.roles.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No AI suggestions available
                    </p>
                  ) : (
                    <div className="space-y-6">
                      {suggestionsData?.roles.map((role, roleIndex) => (
                        <motion.div
                          key={role.role_key}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.3, delay: roleIndex * 0.1 }}
                          className="space-y-4"
                        >
                          {/* Role header - icon box pattern */}
                          <div className="flex items-center gap-3">
                            <div className="p-1.5 rounded-md bg-primary/10">
                              <Briefcase className="w-3.5 h-3.5 text-primary" />
                            </div>
                            <div>
                              <h5 className="text-base font-semibold tracking-tight">{role.title}</h5>
                              <p className="text-xs text-muted-foreground">at {role.company}</p>
                            </div>
                          </div>

                          {/* Bullets with suggestions */}
                          <div className="space-y-3 pl-2 border-l-2 border-border/50 ml-3">
                            {role.bullets.map((bullet, bulletIndex) => (
                              <motion.div
                                key={bullet.index}
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ duration: 0.2, delay: roleIndex * 0.1 + bulletIndex * 0.05 }}
                                className="rounded-lg border border-border/50 bg-background overflow-hidden shadow-sm"
                              >
                                {/* Original bullet */}
                                <div className="p-4 border-b border-border/30">
                                  <div className="flex items-start gap-3">
                                    <Badge
                                      variant="outline"
                                      className="shrink-0 text-[10px] px-2 py-0.5 h-5 bg-muted/50 font-medium"
                                    >
                                      Original
                                    </Badge>
                                    <p className="text-sm text-muted-foreground leading-relaxed">
                                      {bullet.original}
                                    </p>
                                  </div>
                                  {bullet.score !== undefined && (
                                    <div className="mt-3 flex items-center gap-3">
                                      <span className="text-xs text-muted-foreground">Alignment</span>
                                      <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                                        <motion.div
                                          initial={{ width: 0 }}
                                          animate={{ width: `${bullet.score * 100}%` }}
                                          transition={{ duration: 0.5, delay: 0.2 }}
                                          className={`h-full rounded-full ${
                                            bullet.score >= 0.7
                                              ? 'bg-gradient-to-r from-emerald-500 to-emerald-400'
                                              : bullet.score >= 0.5
                                              ? 'bg-gradient-to-r from-amber-500 to-amber-400'
                                              : 'bg-gradient-to-r from-red-500 to-red-400'
                                          }`}
                                        />
                                      </div>
                                      <span className="text-xs font-medium tabular-nums w-10 text-right">
                                        {Math.round(bullet.score * 100)}%
                                      </span>
                                    </div>
                                  )}
                                </div>

                                {/* AI Suggestions */}
                                {bullet.suggestions.length > 0 && (
                                  <div className="p-4 bg-emerald-500/5 space-y-3">
                                    <div className="flex items-center justify-between">
                                      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
                                        <Sparkles className="w-3 h-3" />
                                        AI Suggestions
                                      </div>
                                      <span className="text-[10px] text-muted-foreground">
                                        Click <Heart className="w-3 h-3 inline" /> to save
                                      </span>
                                    </div>
                                    <div className="space-y-2.5">
                                      {bullet.suggestions.map((suggestion, i) => {
                                        const suggestionKey = getSuggestionKey(role.role_key, bullet.index, i);
                                        const isSaved = savedSuggestions.has(suggestionKey);

                                        return (
                                          <motion.div
                                            key={i}
                                            initial={{ opacity: 0 }}
                                            animate={{ opacity: 1 }}
                                            transition={{ duration: 0.2, delay: 0.1 * i }}
                                            className="group/suggestion flex items-start gap-2.5 p-2 -m-2 rounded-lg hover:bg-emerald-500/5 transition-colors"
                                          >
                                            <ArrowRight className="w-3.5 h-3.5 shrink-0 mt-0.5 text-emerald-500" />
                                            <p className="flex-1 text-sm text-foreground leading-relaxed">{suggestion}</p>
                                            <button
                                              onClick={(e) => {
                                                e.stopPropagation();
                                                handleSaveSuggestion(
                                                  role.title,
                                                  role.company,
                                                  bullet.original,
                                                  suggestion,
                                                  suggestionKey
                                                );
                                              }}
                                              disabled={isSaved || saveBulletMutation.isPending}
                                              className={`shrink-0 p-1.5 rounded-md transition-all ${
                                                isSaved
                                                  ? 'text-rose-500 bg-rose-500/10'
                                                  : 'text-muted-foreground/50 hover:text-rose-500 hover:bg-rose-500/10 opacity-0 group-hover/suggestion:opacity-100'
                                              }`}
                                              title={isSaved ? 'Saved to library' : 'Save to library'}
                                            >
                                              {isSaved ? (
                                                <Check className="w-3.5 h-3.5" />
                                              ) : (
                                                <Heart className="w-3.5 h-3.5" />
                                              )}
                                            </button>
                                          </motion.div>
                                        );
                                      })}
                                    </div>
                                  </div>
                                )}
                              </motion.div>
                            ))}
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  )}

                  {/* Load full analysis button */}
                  <div className="pt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelect(item.job_id, item.resume_id);
                      }}
                    >
                      Load Full Analysis
                      <ExternalLink className="w-3 h-3 ml-1" />
                    </Button>
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
