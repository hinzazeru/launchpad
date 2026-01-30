import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
// api is mostly used inside hooks now, but maybe needed for types
import { useJobs, useResumes, useGeminiStatus, useAnalyzeResume, useGenerateSuggestions, useSaveLikedBullet } from '@/services/api';
import type { AnalyzeResponse, RoleAnalysis } from '@/services/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { BulletEditor } from '@/components/BulletEditor';
import { ExportButton } from '@/components/ExportButton';
import type { BulletSelection } from '@/components/ExportButton';
import { AnalysisResultSkeleton } from '@/components/ui/skeleton';
import { PageTransition, FadeIn, ExpandableSection } from '@/components/AnimatedComponents';
import { useToastActions } from '@/components/ui/toast';

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


export function Dashboard() {
  const toast = useToastActions();

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
            Select a job and resume to analyze alignment
          </motion.p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Selection */}
          <div className="lg:col-span-1 space-y-4">
            {/* Job Selection */}
            <Card className="border-border/50">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-md bg-primary/10">
                    <Briefcase className="w-4 h-4 text-primary" />
                  </div>
                  <div>
                    <CardTitle className="text-base">Select Job</CardTitle>
                    <CardDescription className="text-xs">{jobs.length} jobs available</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search jobs..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-9 bg-background/50"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs text-muted-foreground flex items-center gap-1">
                      <ArrowUpDown className="h-3 w-3" /> Sort
                    </label>
                    <Select value={sortBy} onValueChange={(v: any) => setSortBy(v)}>
                      <SelectTrigger className="h-8 text-xs bg-background/50">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="score">Match Score</SelectItem>
                        <SelectItem value="date">Date Posted</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-muted-foreground flex items-center gap-1">
                      <Calendar className="h-3 w-3" /> Date
                    </label>
                    <Select value={recency} onValueChange={setRecency}>
                      <SelectTrigger className="h-8 text-xs bg-background/50">
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
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm text-gray-500">Min Score: {minScore}%</label>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={minScore}
                    onChange={(e) => setMinScore(Number(e.target.value))}
                    className="w-full"
                  />
                </div>

                <Select
                  value={selectedJobId}
                  onValueChange={(value) => {
                    setSelectedJobId(value);
                    setAnalysisResult(null);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Choose a job..." />
                  </SelectTrigger>
                  <SelectContent>
                    {jobs.map((job) => (
                      <SelectItem key={job.id} value={job.id.toString()}>
                        <div className="flex items-center gap-2">
                          <span className="truncate flex-1">
                            {job.title.replace(/Senior Product Manager/g, "SPM")} <span className="text-muted-foreground font-normal ml-1">at {job.company}</span>
                          </span>
                          <Badge variant="secondary" className="text-xs">
                            {job.match_score.toFixed(0)}%
                          </Badge>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {selectedJob && (
                  <div className="p-3 bg-muted rounded-lg text-sm">
                    <a
                      href={selectedJob.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-foreground hover:text-primary hover:underline block transition-colors"
                    >
                      {selectedJob.title}
                    </a>
                    <p className="text-muted-foreground">{selectedJob.company}</p>
                    <div className="flex flex-col gap-0.5 mt-1">
                      {selectedJob.location && (
                        <p className="text-muted-foreground text-xs">{selectedJob.location}</p>
                      )}
                      {selectedJob.salary && (
                        <p className="text-emerald-500 text-xs font-medium">{selectedJob.salary}</p>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Resume Selection */}
            <Card className="border-border/50">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-md bg-violet-500/10">
                    <FileText className="w-4 h-4 text-violet-500" />
                  </div>
                  <div>
                    <CardTitle className="text-base">Select Resume</CardTitle>
                    <CardDescription className="text-xs">{resumes.length} resumes in library</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <Select
                  value={selectedResumeFilename}
                  onValueChange={(value) => {
                    setSelectedResumeFilename(value);
                    setAnalysisResult(null);
                  }}
                >
                  <SelectTrigger className="bg-background/50">
                    <SelectValue placeholder="Choose a resume..." />
                  </SelectTrigger>
                  <SelectContent>
                    {resumes.map((resume) => (
                      <SelectItem key={resume.filename} value={resume.filename}>
                        {resume.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {selectedResume && (
                  <div className="p-3 bg-muted/50 rounded-lg text-sm border border-border/50">
                    <p className="font-medium text-foreground">{selectedResume.name}</p>
                    <p className="text-muted-foreground text-xs">{selectedResume.format} format</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Analyze Button */}
            <Button
              onClick={runAnalysis}
              disabled={!selectedJob || !selectedResume || analyzeMutation.isPending}
              className="w-full"
              size="lg"
            >
              {analyzeMutation.isPending ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Analyzing...
                </>
              ) : (
                'Analyze Resume'
              )}
            </Button>

            {!geminiAvailable && (
              <p className="text-xs text-yellow-600 text-center">
                Gemini AI not configured. Add API key to config.yaml for AI suggestions.
              </p>
            )}
          </div>

          {/* Right Column - Results */}
          <div className="lg:col-span-2">
            {analyzeMutation.isPending ? (
              <FadeIn>
                <AnalysisResultSkeleton />
              </FadeIn>
            ) : analysisResult ? (
              <FadeIn>
                <div className="space-y-6">
                  {/* Stats Bar - matching JobMatches design */}
                  <motion.div
                    className="grid grid-cols-2 lg:grid-cols-4 gap-4"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                  >
                    <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 border border-border/50">
                      <div className="p-2 rounded-md bg-primary/10">
                        <TrendingUp className="w-4 h-4 text-primary" />
                      </div>
                      <div>
                        <p className="text-2xl font-bold tabular-nums">{(analysisResult.overall_alignment * 100).toFixed(0)}%</p>
                        <p className="text-xs text-muted-foreground">Overall Score</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 border border-border/50">
                      <div className="p-2 rounded-md bg-blue-500/10">
                        <FileText className="w-4 h-4 text-blue-500" />
                      </div>
                      <div>
                        <p className="text-2xl font-bold tabular-nums">{analysisResult.total_bullets}</p>
                        <p className="text-xs text-muted-foreground">Total Bullets</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 border border-border/50">
                      <div className="p-2 rounded-md bg-amber-500/10">
                        <AlertCircle className="w-4 h-4 text-amber-500" />
                      </div>
                      <div>
                        <p className="text-2xl font-bold tabular-nums">{analysisResult.low_scoring_bullets}</p>
                        <p className="text-xs text-muted-foreground">Low Scoring</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 border border-border/50">
                      <div className="p-2 rounded-md bg-emerald-500/10">
                        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                      </div>
                      <div>
                        <p className="text-2xl font-bold tabular-nums">{totalModifications}</p>
                        <p className="text-xs text-muted-foreground">Modified</p>
                      </div>
                    </div>
                  </motion.div>

                  {/* Summary Card */}
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
                        {/* Progress Bar */}
                        <div className="space-y-2">
                          <div className="flex justify-between text-sm">
                            <span className="text-muted-foreground">Alignment Score</span>
                            <span className="font-medium">{(analysisResult.overall_alignment * 100).toFixed(0)}%</span>
                          </div>
                          <Progress
                            value={analysisResult.overall_alignment * 100}
                            indicatorClassName={
                              analysisResult.overall_alignment >= 0.7 ? 'bg-gradient-to-r from-emerald-500 to-emerald-400' :
                                analysisResult.overall_alignment >= 0.5 ? 'bg-gradient-to-r from-amber-500 to-amber-400' : 'bg-gradient-to-r from-red-500 to-red-400'
                            }
                            className="h-2"
                          />
                        </div>

                        {/* Export Section */}
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

                  {/* Role Cards */}
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
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" />
                              Generating All...
                            </>
                          ) : (
                            <>
                              <Sparkles className="h-4 w-4" />
                              Generate All Suggestions
                            </>
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
              <Card className="h-full flex items-center justify-center min-h-[400px] border-border/50">
                <div className="text-center text-muted-foreground">
                  <Search className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium">Select a job and resume</p>
                  <p className="text-sm mt-1">Then click "Analyze Resume" to see results</p>
                </div>
              </Card>
            )}
          </div>
        </div>
      </div>
    </PageTransition >
  );
}
