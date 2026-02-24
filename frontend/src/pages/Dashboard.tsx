import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
// api is mostly used inside hooks now, but maybe needed for types
import { useJobs, useResumes, useGeminiStatus, useAnalyzeResume, useGenerateSuggestions, useSaveLikedBullet } from '@/services/api';
import type { AnalyzeResponse, RoleAnalysis, Job } from '@/services/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { BulletEditor } from '@/components/BulletEditor';
import { ExportButton } from '@/components/ExportButton';
import type { BulletSelection } from '@/components/ExportButton';
import { AnalysisResultSkeleton } from '@/components/ui/skeleton';
import { PageTransition, FadeIn, ExpandableSection } from '@/components/AnimatedComponents';
import { useToastActions } from '@/components/ui/toast';
import { AnalysisHistory } from '@/components/AnalysisHistory';

import {
  Search,
  Loader2,
  Sparkles,
  ChevronDown,
  ArrowUpDown,
  Calendar,
  FileText,
  Briefcase,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  Bot,
  Lightbulb,
  XCircle,
  History,
  MapPin,
} from 'lucide-react';

import { useDebounce } from '@/hooks/use-debounce';

// Radial Progress Component - Matching JobMatches design
function RadialScore({ score, size = 64, strokeWidth = 5 }: { score: number; size?: number; strokeWidth?: number }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (score / 100) * circumference;

  // Dynamic gradient based on score
  const getGradientColors = () => {
    if (score >= 70) return { start: '#10b981', end: '#34d399' }; // Emerald
    if (score >= 50) return { start: '#f59e0b', end: '#fbbf24' }; // Amber
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
          className="text-base font-bold tabular-nums tracking-tight"
          initial={{ opacity: 0, scale: 0.5 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3, delay: 0.5 }}
        >
          {Math.round(score)}%
        </motion.span>
      </div>
    </div>
  );
}



interface RoleCardProps {
  role: RoleAnalysis;
  roleKey: string;
  index: number;
  onGenerateSuggestions: (index: number) => void;
  isGenerating: boolean;
  suggestions?: Array<{ original: string; analysis: string; suggestions: string[] }>;
  bulletSelections: BulletSelection[];
  onBulletSelect: (bulletIndex: number, optionId: string, text: string, type: 'original' | 'ai' | 'custom') => void;
  onLike: (original: string, rewritten: string) => void;
}

function RoleCard({
  role,
  index,
  onGenerateSuggestions,
  isGenerating,
  suggestions,
  bulletSelections,
  onBulletSelect,
  onLike,
}: RoleCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Count modifications
  const modifiedCount = bulletSelections.filter(s => s.type !== 'original').length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.05 }}
    >
      <Card className="group relative overflow-hidden transition-all duration-300 hover:shadow-lg hover:shadow-primary/5 border-border/50">
        {/* Score indicator strip */}
        <div
          className={`absolute left-0 top-0 bottom-0 w-1 ${role.alignment_score >= 0.7 ? 'bg-gradient-to-b from-emerald-500 to-emerald-400' :
            role.alignment_score >= 0.5 ? 'bg-gradient-to-b from-amber-500 to-amber-400' :
              'bg-gradient-to-b from-red-500 to-red-400'
            }`}
        />
        <CardHeader
          className="cursor-pointer transition-colors hover:bg-muted/50 pl-5"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <div className="flex items-center gap-4">
            {/* Radial Score */}
            <div className="flex-shrink-0">
              <RadialScore score={role.alignment_score * 100} />
            </div>

            <div className="flex-1 min-w-0">
              <CardTitle className="text-[15px] leading-tight">{role.title}</CardTitle>
              <CardDescription className="text-sm">{role.company} • {role.duration}</CardDescription>
            </div>

            <div className="flex items-center gap-3">
              <AnimatePresence>
                {modifiedCount > 0 && (
                  <motion.div
                    initial={{ scale: 0, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={{ scale: 0, opacity: 0 }}
                  >
                    <Badge variant="default" className="text-xs bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20">
                      {modifiedCount} modified
                    </Badge>
                  </motion.div>
                )}
              </AnimatePresence>
              <motion.div
                animate={{ rotate: isExpanded ? 180 : 0 }}
                transition={{ duration: 0.2 }}
              >
                <ChevronDown className="h-4 w-4 text-muted-foreground/50" />
              </motion.div>
            </div>
          </div>
        </CardHeader>

        <ExpandableSection isExpanded={isExpanded}>
          <CardContent className="pt-0 pl-5">
            <div className="space-y-4 border-t border-border/50 pt-4 bg-muted/20 -mx-6 px-6 pb-2 -mb-6">
              {/* Generate suggestions button */}
              {!suggestions && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.1 }}
                >
                  <Button
                    onClick={(e) => {
                      e.stopPropagation();
                      onGenerateSuggestions(index);
                    }}
                    disabled={isGenerating}
                    className="w-full"
                    variant="outline"
                  >
                    {isGenerating ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Generating AI Suggestions...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4" />
                        Generate AI Suggestions for This Role
                      </>
                    )}
                  </Button>
                </motion.div>
              )}

              {suggestions && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-2 p-2 bg-emerald-500/10 rounded-lg border border-emerald-500/20"
                >
                  <Sparkles className="h-4 w-4 text-emerald-500" />
                  <span className="text-sm text-emerald-600 dark:text-emerald-400">AI suggestions available - expand bullets to view options</span>
                </motion.div>
              )}

              {/* Bullet editors */}
              <div className="space-y-3">
                {role.bullet_scores.map((bullet, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                  >
                    <BulletEditor
                      original={bullet.text}
                      score={bullet.score * 100}
                      matchedKeywords={bullet.matched_keywords}
                      missingKeywords={bullet.missing_keywords}
                      aiSuggestions={suggestions?.[i]?.suggestions}
                      analysis={suggestions?.[i]?.analysis}
                      selectedOption={
                        bulletSelections[i]?.type === 'custom' ? 'custom' :
                          bulletSelections[i]?.type === 'ai' ?
                            `ai-${suggestions?.[i]?.suggestions.findIndex(s => s === bulletSelections[i]?.selected) ?? 0}` :
                            'original'
                      }
                      onSelect={(optionId, text, type) => onBulletSelect(i, optionId, text, type)}
                      onLike={async (rewritten) => onLike(bullet.text, rewritten)}
                    />
                  </motion.div>
                ))}
              </div>
            </div>
          </CardContent>
        </ExpandableSection>
      </Card>
    </motion.div>
  );
}


// Collapsible AI Insights panel shown in the selected job preview card
function CollapsibleAIInsights({ job }: { job: Job }) {
  const [open, setOpen] = useState(false);
  const hasInsights =
    (job.ai_strengths?.length ?? 0) > 0 ||
    (job.ai_concerns?.length ?? 0) > 0 ||
    (job.ai_recommendations?.length ?? 0) > 0 ||
    (job.skill_gaps_detailed?.length ?? 0) > 0;

  if (!hasInsights) return null;

  return (
    <div className="mt-3 pt-3 border-t border-border/50">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full text-xs font-semibold text-violet-600 dark:text-violet-400 hover:text-violet-500 transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <Bot className="w-3.5 h-3.5" />
          AI Match Insights
        </span>
        <motion.div animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown className="w-3.5 h-3.5" />
        </motion.div>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="mt-3 space-y-3">
              {(job.ai_strengths?.length ?? 0) > 0 && (
                <div className="space-y-1">
                  <p className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Strengths
                  </p>
                  <ul className="space-y-0.5">
                    {job.ai_strengths?.map((s, i) => (
                      <li key={i} className="text-[11px] text-muted-foreground">• {s}</li>
                    ))}
                  </ul>
                </div>
              )}
              {(job.ai_concerns?.length ?? 0) > 0 && (
                <div className="space-y-1">
                  <p className="text-[10px] text-amber-600 dark:text-amber-400 font-medium flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" /> Concerns
                  </p>
                  <ul className="space-y-0.5">
                    {job.ai_concerns?.map((c, i) => (
                      <li key={i} className="text-[11px] text-muted-foreground">• {c}</li>
                    ))}
                  </ul>
                </div>
              )}
              {(job.ai_recommendations?.length ?? 0) > 0 && (
                <div className="space-y-1">
                  <p className="text-[10px] text-blue-600 dark:text-blue-400 font-medium flex items-center gap-1">
                    <Lightbulb className="w-3 h-3" /> Focus Areas
                  </p>
                  <ul className="space-y-0.5">
                    {job.ai_recommendations?.map((r, i) => (
                      <li key={i} className="text-[11px] text-muted-foreground">→ {r}</li>
                    ))}
                  </ul>
                </div>
              )}
              {(job.skill_gaps_detailed?.length ?? 0) > 0 && (
                <div className="space-y-1">
                  <p className="text-[10px] text-red-600 dark:text-red-400 font-medium flex items-center gap-1">
                    <XCircle className="w-3 h-3" /> Key Gaps
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {job.skill_gaps_detailed?.map((gap, i) => (
                      <span
                        key={i}
                        className={`px-1.5 py-0.5 text-[10px] font-medium rounded border ${
                          gap.importance === 'must_have'
                            ? 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20'
                            : 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
                        }`}
                      >
                        {gap.skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function Dashboard() {
  const toast = useToastActions();
  const location = useLocation();

  // Tab state
  const [activeTab, setActiveTab] = useState<'analysis' | 'history'>('analysis');
  const [preloadedJob, setPreloadedJob] = useState<{ jobId: number; resumeId: number } | null>(null);

  // State
  const [selectedJobId, setSelectedJobId] = useState<string>('');
  const [selectedResumeFilename, setSelectedResumeFilename] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState('');
  const [minScore, setMinScore] = useState(0);
  const [sortBy, setSortBy] = useState<'score' | 'date'>('score');
  const [recency, setRecency] = useState<string>('all');

  const debouncedSearch = useDebounce(searchTerm, 500);
  const debouncedScore = useDebounce(minScore, 500);

  // React Query Hooks
  const {
    data: jobsData,
    isLoading: jobsLoading,
    error: jobsError
  } = useJobs({
    search: debouncedSearch,
    min_score: debouncedScore,
    recency_days: recency === 'all' ? undefined : Number(recency),
    sort_by: sortBy,
    limit: 100
  });

  const {
    data: resumesData,
    isLoading: resumesLoading,
    error: resumesError
  } = useResumes();

  const { data: geminiStatus } = useGeminiStatus();

  const analyzeMutation = useAnalyzeResume();
  const suggestionsMutation = useGenerateSuggestions();
  const saveBulletMutation = useSaveLikedBullet();

  // Derived state
  const jobs = jobsData?.jobs || [];
  const resumes = resumesData?.resumes || [];
  const geminiAvailable = geminiStatus?.available || false;

  const selectedJob = jobs.find(j => j.id.toString() === selectedJobId) || null;
  const selectedResume = resumes.find(r => r.filename === selectedResumeFilename) || null;

  // Analysis State
  const [analysisResult, setAnalysisResult] = useState<AnalyzeResponse | null>(null);
  const [generatingRole, setGeneratingRole] = useState<number | null>(null);
  const [isGeneratingAll, setIsGeneratingAll] = useState(false);
  const [roleSuggestions, setRoleSuggestions] = useState<Record<number, Array<{ original: string; analysis: string; suggestions: string[] }>>>({});
  const [bulletSelections, setBulletSelections] = useState<Record<string, BulletSelection[]>>({});

  // LocalStorage key for bullet selections
  const SELECTIONS_STORAGE_KEY = 'resume-bullet-selections';

  // Load bullet selections from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(SELECTIONS_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        // Only restore if we have data and it's an object
        if (parsed && typeof parsed === 'object') {
          setBulletSelections(parsed);
        }
      }
    } catch (e) {
      // Ignore parse errors
    }
  }, []);

  // Save bullet selections to localStorage when they change
  useEffect(() => {
    if (Object.keys(bulletSelections).length > 0) {
      localStorage.setItem(SELECTIONS_STORAGE_KEY, JSON.stringify(bulletSelections));
    }
  }, [bulletSelections]);

  // Pre-select job when navigating from JobMatches
  useEffect(() => {
    const incomingJobId = (location.state as { jobId?: string })?.jobId;
    if (incomingJobId) {
      setSelectedJobId(String(incomingJobId));
      setActiveTab('analysis');
      // Clear router state so navigating away and back doesn't re-select
      window.history.replaceState({}, '');
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Initialize bullet selections when analysis result changes
  useEffect(() => {
    if (analysisResult) {
      const initialSelections: Record<string, BulletSelection[]> = {};
      analysisResult.roles.forEach((role) => {
        const roleKey = `${role.company}_${role.title}`;
        initialSelections[roleKey] = role.bullet_scores.map((bullet) => ({
          original: bullet.text,
          selected: bullet.text,
          type: 'original' as const,
        }));
      });
      setBulletSelections(initialSelections);
    }
  }, [analysisResult]);

  // Handle selecting analysis from history
  function handleSelectFromHistory(jobId: number, _resumeId: number) {
    // Set the job ID to preload
    setSelectedJobId(jobId.toString());
    // Clear previous analysis
    setAnalysisResult(null);
    setRoleSuggestions({});
    // Switch to analysis tab
    setActiveTab('analysis');
    // Store preload request
    setPreloadedJob({ jobId, resumeId: _resumeId });
  }

  // Auto-trigger analysis when preloaded from history
  useEffect(() => {
    if (preloadedJob && activeTab === 'analysis' && selectedJobId === preloadedJob.jobId.toString()) {
      // Find job and resume from loaded data
      const job = jobs.find(j => j.id === preloadedJob.jobId);
      if (job && resumes.length > 0 && selectedResumeFilename) {
        // Clear preload state after handling
        setPreloadedJob(null);
        // Auto-run analysis is not ideal UX - let user click analyze
        // They can see the job is preselected
      }
    }
  }, [preloadedJob, activeTab, selectedJobId, jobs, resumes, selectedResumeFilename]);

  // Run analysis
  async function runAnalysis() {
    if (!selectedJob || !selectedResume) return;

    setAnalysisResult(null);
    setRoleSuggestions({});
    setBulletSelections({});

    try {
      const result = await analyzeMutation.mutateAsync({
        resume_filename: selectedResume.filename,
        job_id: selectedJob.id,
        threshold: 0.7,
      });
      setAnalysisResult(result);

      // Load saved suggestions if any
      const savedSuggestions: Record<number, any> = {};
      let hasSaved = false;
      result.roles.forEach((role, idx) => {
        role.bullet_scores.forEach(bullet => {
          if (bullet.suggestions && bullet.suggestions.length > 0) {
            // Reconstruct the suggestion object structure expected by UI
            if (!savedSuggestions[idx]) savedSuggestions[idx] = [];
            // We need to find the suggestions for this bullet.
            // The API now returns fully populated BulletScore objects
          }
        });

        // Wait, the API returns suggestions inside BulletScore.
        // We need to map this back to roleSuggestions state structure:
        // Record<number, Array<{ original: string; analysis: string; suggestions: string[] }>>

        const roleBulletsWithSuggestions = role.bullet_scores
          .map((bs, i) => ({
            original: bs.text,
            suggestions: bs.suggestions,
            analysis: "", // API doesn't persist analysis text in BulletScore model yet sadly, unless we add it. But suggestions exist.
            index: i
          }))
          .filter(b => b.suggestions && b.suggestions.length > 0);

        if (roleBulletsWithSuggestions.length > 0) {
          savedSuggestions[idx] = roleBulletsWithSuggestions.map(b => ({
            original: b.original,
            analysis: "Previously generated suggestion", // Placeholder since we didn't save analysis text in column
            suggestions: b.suggestions
          }));
          hasSaved = true;
        }
      });

      if (hasSaved) {
        setRoleSuggestions(savedSuggestions);
        toast.success('Analysis complete', `Loaded saved AI suggestions and alignment: ${(result.overall_alignment * 100).toFixed(0)}%`);
      } else {
        toast.success('Analysis complete', `Overall alignment: ${(result.overall_alignment * 100).toFixed(0)}%`);
      }
    } catch (error) {
      console.error('Analysis failed:', error);
      toast.error('Analysis failed', 'Please try again.');
    }
  }

  // Generate suggestions for a role
  async function generateSuggestions(roleIndex: number) {
    if (!selectedJob || !selectedResume) return;

    setGeneratingRole(roleIndex);

    try {
      const result = await suggestionsMutation.mutateAsync({
        resume_filename: selectedResume.filename,
        role_index: roleIndex,
        job_title: selectedJob.title,
        job_company: selectedJob.company,
        job_description: selectedJob.description,
        job_id: selectedJob.id,
      });

      setRoleSuggestions(prev => ({
        ...prev,
        [roleIndex]: result.bullet_suggestions,
      }));
      toast.success('Suggestions ready', 'AI suggestions have been generated for this role.');
    } catch (error) {
      console.error('Failed to generate suggestions:', error);
      toast.error('Failed to generate suggestions', 'Please check if Gemini API is configured.');
    } finally {
      setGeneratingRole(null);
    }
  }

  // Generate suggestions for all roles at once
  async function generateAllSuggestions() {
    if (!selectedJob || !selectedResume || !analysisResult) return;

    setIsGeneratingAll(true);
    let successCount = 0;

    for (let i = 0; i < analysisResult.roles.length; i++) {
      // Skip if already has suggestions
      if (roleSuggestions[i]) {
        successCount++;
        continue;
      }

      try {
        const result = await suggestionsMutation.mutateAsync({
          resume_filename: selectedResume.filename,
          role_index: i,
          job_title: selectedJob.title,
          job_company: selectedJob.company,
          job_description: selectedJob.description,
          job_id: selectedJob.id,
        });

        setRoleSuggestions(prev => ({
          ...prev,
          [i]: result.bullet_suggestions,
        }));
        successCount++;
      } catch (error) {
        console.error(`Failed to generate suggestions for role ${i}:`, error);
      }
    }

    setIsGeneratingAll(false);
    toast.success('Bulk generation complete', `Generated suggestions for ${successCount}/${analysisResult.roles.length} roles.`);
  }

  // Handle bullet selection matches previous logic
  function handleBulletSelect(
    roleKey: string,
    bulletIndex: number,
    _optionId: string,
    text: string,
    type: 'original' | 'ai' | 'custom'
  ) {
    setBulletSelections(prev => {
      const roleSelections = [...(prev[roleKey] || [])];
      roleSelections[bulletIndex] = {
        original: roleSelections[bulletIndex]?.original || text,
        selected: text,
        type,
      };
      return { ...prev, [roleKey]: roleSelections };
    });
  }

  // Handle saving liked bullet
  function handleLikeBullet(
    roleTitle: string,
    company: string,
    originalText: string,
    rewrittenText: string
  ) {
    if (!selectedJob) return;

    saveBulletMutation.mutate({
      original_text: originalText,
      rewritten_text: rewrittenText,
      role_title: roleTitle,
      company: company,
      job_id: selectedJob.id,
    }, {
      onSuccess: () => {
        toast.success("Saved!", "Rewrite saved to your collection");
      },
      onError: () => {
        toast.error("Error", "Failed to save rewrite");
      }
    });
  }

  // Count total modifications

  // Count total modifications
  const totalModifications = Object.values(bulletSelections)
    .flat()
    .filter(s => s.type !== 'original').length;

  // Only show full loading screen on initial load, not during filter refetches
  const isInitialLoading = (jobsLoading && !jobsData) || (resumesLoading && !resumesData);
  const loadError = jobsError || resumesError;

  if (isInitialLoading) {
    return (
      <PageTransition>
        <div className="space-y-6">
          <div className="space-y-1">
            <motion.h1
              className="text-3xl font-bold tracking-tight"
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
            >
              Resume Analysis
            </motion.h1>
            <motion.p
              className="text-muted-foreground"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.1 }}
            >
              Select a job and resume to analyze alignment
            </motion.p>
          </div>
          <div className="flex flex-col items-center justify-center py-16 gap-4">
            <motion.div
              className="w-12 h-12 rounded-full border-2 border-primary border-t-transparent"
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            />
            <p className="text-muted-foreground">Loading...</p>
          </div>
        </div>
      </PageTransition>
    );
  }

  // Error state
  if (loadError && jobs.length === 0) {
    return (
      <PageTransition>
        <div className="space-y-6">
          <div className="space-y-1">
            <motion.h1
              className="text-3xl font-bold tracking-tight"
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
            >
              Resume Analysis
            </motion.h1>
            <motion.p
              className="text-muted-foreground"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.1 }}
            >
              Select a job and resume to analyze alignment
            </motion.p>
          </div>
          <div className="flex flex-col items-center justify-center py-16 gap-2 text-destructive">
            <AlertCircle className="w-8 h-8" />
            <p>Failed to load data. Please try again.</p>
          </div>
        </div>
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="space-y-1">
          <motion.h1
            className="text-3xl font-bold tracking-tight"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            Resume Analysis
          </motion.h1>
          <motion.p
            className="text-muted-foreground"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1 }}
          >
            Analyze your resume against job postings
          </motion.p>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'analysis' | 'history')}>
          <TabsList className="mb-6">
            <TabsTrigger value="analysis" className="flex items-center gap-2">
              <FileText className="w-4 h-4" />
              New Analysis
            </TabsTrigger>
            <TabsTrigger value="history" className="flex items-center gap-2">
              <History className="w-4 h-4" />
              History
            </TabsTrigger>
          </TabsList>

          <TabsContent value="analysis" className="mt-0">
            <div className="space-y-4 pb-32">

              {/* 1. Filters bar — always visible, compact horizontal */}
              <div className="flex flex-wrap gap-2 p-3 rounded-xl bg-card border border-border/50">
                <div className="relative flex-1 min-w-[160px]">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search jobs..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-9 bg-background/50 h-9 text-sm"
                  />
                </div>
                <Select value={sortBy} onValueChange={(v: any) => setSortBy(v)}>
                  <SelectTrigger className="h-9 w-[130px] bg-background/50 text-xs">
                    <ArrowUpDown className="h-3 w-3 mr-1.5 text-muted-foreground flex-shrink-0" />
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="score">Match Score</SelectItem>
                    <SelectItem value="date">Date Posted</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={recency} onValueChange={setRecency}>
                  <SelectTrigger className="h-9 w-[130px] bg-background/50 text-xs">
                    <Calendar className="h-3 w-3 mr-1.5 text-muted-foreground flex-shrink-0" />
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Any time</SelectItem>
                    <SelectItem value="1">Past 24h</SelectItem>
                    <SelectItem value="3">Past 3 days</SelectItem>
                    <SelectItem value="7">Past 7 days</SelectItem>
                    <SelectItem value="14">Past 14 days</SelectItem>
                    <SelectItem value="30">Past 30 days</SelectItem>
                  </SelectContent>
                </Select>
                <div className="flex items-center gap-2 px-1">
                  <span className="text-xs text-muted-foreground whitespace-nowrap">Min: {minScore}%</span>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={minScore}
                    onChange={(e) => setMinScore(Number(e.target.value))}
                    className="w-20 accent-primary"
                  />
                </div>
              </div>

              {/* 2. Job dropdown — full width */}
              <Select
                value={selectedJobId}
                onValueChange={(value) => {
                  setSelectedJobId(value);
                  setAnalysisResult(null);
                }}
              >
                <SelectTrigger className="w-full h-11 bg-card border-border/50">
                  <Briefcase className="h-4 w-4 mr-2 text-muted-foreground flex-shrink-0" />
                  <SelectValue placeholder={`Choose from ${jobs.length} jobs…`} />
                </SelectTrigger>
                <SelectContent>
                  {jobs.map((job) => (
                    <SelectItem key={job.id} value={job.id.toString()}>
                      <div className="flex items-center gap-2 w-full">
                        <span className="truncate flex-1 min-w-0">
                          {job.title} <span className="text-muted-foreground font-normal">at {job.company}</span>
                        </span>
                        <Badge variant="secondary" className="text-xs flex-shrink-0">
                          {job.match_score.toFixed(0)}%
                        </Badge>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* 3. Selected job preview card */}
              <AnimatePresence>
                {selectedJob && (
                  <motion.div
                    key={selectedJob.id}
                    initial={{ opacity: 0, y: -6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.2 }}
                  >
                    <Card className="border-border/50 overflow-hidden">
                      {/* Score color strip */}
                      <div className={`h-1 w-full ${
                        selectedJob.match_score >= 75 ? 'bg-gradient-to-r from-emerald-500 to-emerald-400' :
                        selectedJob.match_score >= 60 ? 'bg-gradient-to-r from-amber-500 to-amber-400' :
                        'bg-gradient-to-r from-red-500 to-red-400'
                      }`} />
                      <CardContent className="p-4">
                        <div className="flex items-start gap-3">
                          <div className="flex-1 min-w-0">
                            <a
                              href={selectedJob.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="font-semibold text-[15px] leading-tight hover:text-primary transition-colors line-clamp-1"
                            >
                              {selectedJob.title}
                            </a>
                            <p className="text-sm text-muted-foreground mt-0.5">{selectedJob.company}</p>
                            <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground flex-wrap">
                              {selectedJob.location && (
                                <span className="flex items-center gap-1">
                                  <MapPin className="w-3 h-3 flex-shrink-0" />
                                  <span className="truncate max-w-[140px]">{selectedJob.location}</span>
                                </span>
                              )}
                              {selectedJob.salary && (
                                <span className="text-emerald-500 font-medium">{selectedJob.salary}</span>
                              )}
                            </div>
                            {selectedJob.domains.length > 0 && (
                              <div className="flex flex-wrap gap-1 mt-2">
                                {selectedJob.domains.map((domain) => (
                                  <span
                                    key={domain}
                                    className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-muted border border-border/60 text-muted-foreground"
                                  >
                                    {domain}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                          {/* Score badge */}
                          <div className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-sm font-bold border ${
                            selectedJob.match_score >= 75
                              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                              : selectedJob.match_score >= 60
                              ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
                              : 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20'
                          }`}>
                            {selectedJob.match_score.toFixed(0)}%
                          </div>
                        </div>

                        {/* Collapsible AI insights */}
                        {selectedJob.match_engine === 'gemini' && <CollapsibleAIInsights job={selectedJob} />}

                        {/* NLP badge */}
                        {selectedJob.match_engine !== 'gemini' && (
                          <div className="mt-3 pt-3 border-t border-border/50 flex items-center gap-2">
                            <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                              NLP Matched
                            </span>
                            <p className="text-[10px] text-muted-foreground">Enable Gemini for AI insights</p>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* 4. Analysis results */}
              {analyzeMutation.isPending ? (
                <FadeIn>
                  <AnalysisResultSkeleton />
                </FadeIn>
              ) : analysisResult ? (
                <FadeIn>
                  <div className="space-y-6">
                    {/* Stats bar */}
                    <motion.div
                      className="grid grid-cols-2 sm:grid-cols-4 gap-2"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.2 }}
                    >
                      <div className="flex items-center gap-2 p-2 sm:p-3 rounded-lg bg-muted/30 border border-border/50">
                        <div className="p-1.5 rounded-md bg-primary/10 flex-shrink-0">
                          <TrendingUp className="w-3.5 h-3.5 text-primary" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-lg sm:text-2xl font-bold tabular-nums leading-tight">{(analysisResult.overall_alignment * 100).toFixed(0)}%</p>
                          <p className="text-[10px] sm:text-xs text-muted-foreground truncate">Overall Score</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 p-2 sm:p-3 rounded-lg bg-muted/30 border border-border/50">
                        <div className="p-1.5 rounded-md bg-blue-500/10 flex-shrink-0">
                          <FileText className="w-3.5 h-3.5 text-blue-500" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-lg sm:text-2xl font-bold tabular-nums leading-tight">{analysisResult.total_bullets}</p>
                          <p className="text-[10px] sm:text-xs text-muted-foreground truncate">Bullets</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 p-2 sm:p-3 rounded-lg bg-muted/30 border border-border/50">
                        <div className="p-1.5 rounded-md bg-amber-500/10 flex-shrink-0">
                          <AlertCircle className="w-3.5 h-3.5 text-amber-500" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-lg sm:text-2xl font-bold tabular-nums leading-tight">{analysisResult.low_scoring_bullets}</p>
                          <p className="text-[10px] sm:text-xs text-muted-foreground truncate">Low Scoring</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 p-2 sm:p-3 rounded-lg bg-muted/30 border border-border/50">
                        <div className="p-1.5 rounded-md bg-emerald-500/10 flex-shrink-0">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-lg sm:text-2xl font-bold tabular-nums leading-tight">{totalModifications}</p>
                          <p className="text-[10px] sm:text-xs text-muted-foreground truncate">Modified</p>
                        </div>
                      </div>
                    </motion.div>

                    {/* Summary card */}
                    <Card className="border-border/50">
                      <CardHeader className="pb-3">
                        <div className="flex items-center gap-3">
                          <div className="p-2 rounded-md bg-violet-500/10">
                            <Sparkles className="w-4 h-4 text-violet-500" />
                          </div>
                          <div>
                            <CardTitle className="text-base">Analysis Results</CardTitle>
                            {analysisResult.job_title && (
                              <CardDescription className="text-xs">
                                {analysisResult.job_title} at {analysisResult.job_company}
                              </CardDescription>
                            )}
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-4">
                          <div className="space-y-2">
                            <div className="flex justify-between text-sm">
                              <span className="text-muted-foreground">Alignment Score</span>
                              <span className="font-medium">{(analysisResult.overall_alignment * 100).toFixed(0)}%</span>
                            </div>
                            <Progress
                              value={analysisResult.overall_alignment * 100}
                              indicatorClassName={
                                analysisResult.overall_alignment >= 0.7 ? 'bg-gradient-to-r from-emerald-500 to-emerald-400' :
                                  analysisResult.overall_alignment >= 0.5 ? 'bg-gradient-to-r from-amber-500 to-amber-400' :
                                    'bg-gradient-to-r from-red-500 to-red-400'
                              }
                              className="h-2"
                            />
                          </div>
                          {selectedResume && selectedJob && (
                            <div className="pt-4 border-t border-border/50">
                              <ExportButton
                                resumeFilename={selectedResume.filename}
                                company={selectedJob.company}
                                selections={bulletSelections}
                                disabled={analyzeMutation.isPending}
                              />
                            </div>
                          )}
                        </div>
                      </CardContent>
                    </Card>

                    {/* Role cards */}
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="text-lg font-semibold">Role Analysis</h3>
                        {geminiAvailable && (
                          <Button
                            onClick={generateAllSuggestions}
                            disabled={isGeneratingAll || generatingRole !== null}
                            variant="outline"
                            size="sm"
                          >
                            {isGeneratingAll ? (
                              <><Loader2 className="h-4 w-4 animate-spin" />Generating All…</>
                            ) : (
                              <><Sparkles className="h-4 w-4" />Generate All Suggestions</>
                            )}
                          </Button>
                        )}
                      </div>
                      {analysisResult.roles.map((role, index) => {
                        const roleKey = `${role.company}_${role.title}`;
                        return (
                          <RoleCard
                            key={index}
                            role={role}
                            roleKey={roleKey}
                            index={index}
                            onGenerateSuggestions={generateSuggestions}
                            isGenerating={generatingRole === index}
                            suggestions={roleSuggestions[index]}
                            bulletSelections={bulletSelections[roleKey] || []}
                            onBulletSelect={(bulletIndex, optionId, text, type) =>
                              handleBulletSelect(roleKey, bulletIndex, optionId, text, type)
                            }
                            onLike={(original, rewritten) =>
                              handleLikeBullet(role.title, role.company, original, rewritten)
                            }
                          />
                        );
                      })}
                    </div>
                  </div>
                </FadeIn>
              ) : (
                <Card className="flex items-center justify-center min-h-[280px] border-border/50 border-dashed">
                  <div className="text-center text-muted-foreground p-8">
                    <Search className="h-10 w-10 mx-auto mb-3 opacity-30" />
                    <p className="font-medium">Select a job above</p>
                    <p className="text-sm mt-1 opacity-70">Then pick a resume below and click Analyze Resume</p>
                  </div>
                </Card>
              )}
            </div>

            {/* 5. Sticky bottom action bar */}
            <div className="fixed bottom-[52px] sm:bottom-0 left-0 right-0 z-40 border-t border-border/50 bg-background/80 backdrop-blur-md supports-[backdrop-filter]:bg-background/70">
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center gap-3">
                <div className="flex-1">
                  <Select
                    value={selectedResumeFilename}
                    onValueChange={(value) => {
                      setSelectedResumeFilename(value);
                      setAnalysisResult(null);
                    }}
                  >
                    <SelectTrigger className="bg-background/50 h-10">
                      <FileText className="h-4 w-4 mr-2 text-muted-foreground flex-shrink-0" />
                      <SelectValue placeholder="Choose a resume…" />
                    </SelectTrigger>
                    <SelectContent>
                      {resumes.map((resume) => (
                        <SelectItem key={resume.filename} value={resume.filename}>
                          {resume.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col items-end gap-1 flex-shrink-0">
                  <Button
                    onClick={runAnalysis}
                    disabled={!selectedJob || !selectedResume || analyzeMutation.isPending}
                    className="h-10"
                  >
                    {analyzeMutation.isPending ? (
                      <><Loader2 className="h-4 w-4 animate-spin" />Analyzing…</>
                    ) : (
                      'Analyze Resume'
                    )}
                  </Button>
                  {!geminiAvailable && (
                    <p className="text-[10px] text-yellow-600">Gemini not configured</p>
                  )}
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="history" className="mt-0">
            <AnalysisHistory onSelectAnalysis={handleSelectFromHistory} />
          </TabsContent>
        </Tabs>
      </div>
    </PageTransition>
  );
}
