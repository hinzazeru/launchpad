import { useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api, useResumes, useSearchDefaults, useGeminiConfigStatus, useSuggestedKeywords } from '@/services/api';
import type { JobSearchParams, SearchProgress, SearchResult, TopMatch, SearchStage, SearchJobProgress } from '@/services/api';
import { useSearchStore } from '@/stores/searchStore';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { PageTransition } from '@/components/AnimatedComponents';
import { useToastActions } from '@/components/ui/toast';
import {
  Search,
  Loader2,
  CheckCircle2,
  XCircle,
  ExternalLink,
  MapPin,
  Building2,
  FileText,
  BarChart3,
  Clock,
  ArrowRight,
  RefreshCw,
  Calendar,
  AlertTriangle,
  Info,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ScheduleList, ScheduleForm } from '@/components/schedules';
import type { ScheduledSearch } from '@/services/api';

// Constants for select options
const JOB_TYPES = [
  { value: '', label: 'Any' },
  { value: 'Full-time', label: 'Full-time' },
  { value: 'Part-time', label: 'Part-time' },
  { value: 'Contract', label: 'Contract' },
  { value: 'Temporary', label: 'Temporary' },
  { value: 'Internship', label: 'Internship' },
];

const EXPERIENCE_LEVELS = [
  { value: '', label: 'Any' },
  { value: 'Entry level', label: 'Entry level' },
  { value: 'Mid-Senior level', label: 'Mid-Senior level' },
  { value: 'Director', label: 'Director' },
  { value: 'Executive', label: 'Executive' },
];

const WORK_ARRANGEMENTS = [
  { value: '', label: 'Any' },
  { value: 'Remote', label: 'Remote' },
  { value: 'Hybrid', label: 'Hybrid' },
  { value: 'On-site', label: 'On-site' },
];

// Stage configuration for progress stepper
const STAGES: { key: SearchStage; label: string; icon: typeof Search }[] = [
  { key: 'initializing', label: 'Initializing', icon: FileText },
  { key: 'fetching', label: 'Fetching Jobs', icon: Search },
  { key: 'importing', label: 'Importing', icon: Building2 },
  { key: 'matching', label: 'Matching', icon: BarChart3 },
  { key: 'exporting', label: 'Exporting', icon: ExternalLink },
  { key: 'completed', label: 'Complete', icon: CheckCircle2 },
];

function ProgressStepper({
  currentStage,
  progress,
}: {
  currentStage: SearchStage;
  progress: SearchProgress | null;
}) {
  const stageOrder = STAGES.map((s) => s.key);
  const currentIndex = stageOrder.indexOf(currentStage);

  return (
    <div className="space-y-3">
      {STAGES.filter((s) => s.key !== 'error').map((stage, index) => {
        const Icon = stage.icon;
        const isComplete = currentIndex > index || currentStage === 'completed';
        const isCurrent = currentStage === stage.key;
        const isPending = currentIndex < index && currentStage !== 'completed';

        return (
          <motion.div
            key={stage.key}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1 }}
            className={cn(
              'flex items-center gap-3 p-3 rounded-lg transition-colors',
              isComplete && 'bg-green-50 dark:bg-green-950',
              isCurrent && 'bg-blue-50 dark:bg-blue-950',
              isPending && 'bg-muted/50'
            )}
          >
            <div
              className={cn(
                'w-8 h-8 rounded-full flex items-center justify-center shrink-0',
                isComplete && 'bg-green-500 text-white',
                isCurrent && 'bg-blue-500 text-white',
                isPending && 'bg-muted text-muted-foreground'
              )}
            >
              {isComplete ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : isCurrent ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Icon className="h-4 w-4" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-medium text-sm">{stage.label}</div>
              {isCurrent && progress?.message && (
                <div className="text-xs text-muted-foreground truncate">
                  {progress.message}
                </div>
              )}
            </div>
            {isCurrent && progress && (
              <div className="text-sm font-medium text-blue-600">
                {progress.progress}%
              </div>
            )}
          </motion.div>
        );
      })}
    </div>
  );
}

function StatsCard({
  label,
  value,
  icon: Icon,
  highlight,
}: {
  label: string;
  value: number | string;
  icon: typeof Search;
  highlight?: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn(
        'p-4 rounded-lg border flex flex-col items-center justify-center text-center',
        highlight ? 'bg-green-50 border-green-200 dark:bg-green-950 dark:border-green-800' : 'bg-muted/50'
      )}
    >
      <div className="flex items-center gap-2 text-muted-foreground mb-1">
        <Icon className="h-4 w-4" />
        <span className="text-xs">{label}</span>
      </div>
      <div className={cn('text-2xl font-bold', highlight && 'text-green-600 dark:text-green-400')}>
        {value}
      </div>
    </motion.div>
  );
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

function ResultsPanel({ result }: { result: SearchResult }) {
  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard label="Jobs Fetched" value={result.jobs_fetched} icon={Search} />
        <StatsCard label="Jobs Matched" value={result.jobs_matched} icon={BarChart3} />
        <StatsCard
          label="High Matches (70%+)"
          value={result.high_matches}
          icon={CheckCircle2}
          highlight={result.high_matches > 0}
        />
        <StatsCard label="Duration" value={formatDuration(result.duration_seconds)} icon={Clock} />
      </div>

      <Tabs defaultValue="matches" className="w-full">
        <TabsList className="grid w-full grid-cols-2 mb-4">
          <TabsTrigger value="matches">Top Matches ({result.top_matches.length})</TabsTrigger>
          <TabsTrigger value="fetched">All Fetched Jobs ({result.fetched_jobs?.length || 0})</TabsTrigger>
        </TabsList>

        <TabsContent value="matches" className="mt-0">
          {result.top_matches.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Top Matches</CardTitle>
                <CardDescription>
                  Best {result.top_matches.length} matches based on blended AI + NLP scores
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {result.top_matches.map((match, index) => (
                  <JobMatchRow key={index} match={match} index={index} />
                ))}
              </CardContent>
            </Card>
          ) : (
            <Card className="border-dashed">
              <CardContent className="flex flex-col items-center justify-center p-8 text-muted-foreground">
                <Search className="h-10 w-10 opacity-20 mb-3" />
                <p>No high-quality matches found.</p>
                <p className="text-sm">Try adjusting your filters or check the All Fetched Jobs tab.</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="fetched" className="mt-0">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Search className="h-5 w-5 text-muted-foreground" />
                Fetched Jobs
              </CardTitle>
              <CardDescription>
                All {result.fetched_jobs?.length || 0} jobs retrieved in this search session
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {result.fetched_jobs && result.fetched_jobs.length > 0 ? (
                result.fetched_jobs.map((match, index) => (
                  <JobMatchRow key={index} match={match} index={index} isRaw={true} />
                ))
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No fetched jobs to display.
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Sheets Link */}
      {result.sheets_url && result.exported_to_sheets > 0 && (
        <Card className="bg-blue-50 border-blue-200 dark:bg-blue-950 dark:border-blue-800">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-lg">
                  <ExternalLink className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <div className="font-medium text-blue-900 dark:text-blue-100">Exported to Google Sheets</div>
                  <div className="text-sm text-blue-700 dark:text-blue-300">
                    {result.exported_to_sheets} matches saved to spreadsheet
                  </div>
                </div>
              </div>
              <Button variant="outline" className="border-blue-300 hover:bg-blue-100 text-blue-700" asChild>
                <a href={result.sheets_url} target="_blank" rel="noopener noreferrer">
                  Open Sheets
                  <ArrowRight className="h-4 w-4 ml-2" />
                </a>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function JobMatchRow({ match, index, isRaw = false }: { match: TopMatch; index: number; isRaw?: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors bg-card"
    >
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate">{match.title}</div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Building2 className="h-3 w-3" />
          <span className="truncate">{match.company}</span>
          {match.location && (
            <>
              <MapPin className="h-3 w-3 ml-2" />
              <span className="truncate">{match.location}</span>
            </>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <div className="text-right">
          {!isRaw ? (
            <>
              <div className="font-bold text-green-600">{match.score}%</div>
              {match.gemini_score && (
                <div className="text-xs text-muted-foreground">
                  AI: {match.gemini_score}%
                </div>
              )}
            </>
          ) : (
            <div className="text-xs font-medium text-orange-500 bg-orange-100 px-2 py-1 rounded">
              Raw
            </div>
          )}
        </div>
        {match.url && (
          <Button variant="ghost" size="icon" asChild>
            <a href={match.url} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="h-4 w-4" />
            </a>
          </Button>
        )}
      </div>
    </motion.div>
  );
}

export function GetJobs() {
  const toast = useToastActions();
  const { data: resumesData, isLoading: resumesLoading } = useResumes();
  const { data: defaults } = useSearchDefaults();
  const { data: geminiConfig } = useGeminiConfigStatus();
  const { data: suggestedKeywords } = useSuggestedKeywords();

  // Form state
  const [keyword, setKeyword] = useState('');
  const [location, setLocation] = useState('');
  const [jobType, setJobType] = useState('');
  const [experienceLevel, setExperienceLevel] = useState('');
  const [workArrangement, setWorkArrangement] = useState('');
  const [maxResults, setMaxResults] = useState(20);
  const [selectedResume, setSelectedResume] = useState('');
  const [exportToSheets, setExportToSheets] = useState(true);

  // Search state from global store (persists across navigation)
  const {
    isSearching,
    progress,
    result,
    error,
    activeSearchId,
    startSearch,
    updateFromJobProgress,
    setResult,
    setError,
    reset: resetSearch,
    cancelSearch,
    abortController,
    setAbortController,
  } = useSearchStore();

  // Schedule state
  const [activeTab, setActiveTab] = useState<'manual' | 'scheduled'>('manual');
  const [showScheduleForm, setShowScheduleForm] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<ScheduledSearch | null>(null);

  // Update location from defaults when loaded
  useEffect(() => {
    if (defaults?.location && !location) {
      setLocation(defaults.location);
    }
  }, [defaults?.location]);

  // Show warning toast when Gemini fallbacks occur
  useEffect(() => {
    if (result?.gemini_stats && result.gemini_stats.failed > 0) {
      const stats = result.gemini_stats;
      const reasonsText = stats.failure_reasons.length > 0
        ? ` (${stats.failure_reasons.map(r => r.replace(/_/g, ' ')).join(', ')})`
        : '';
      toast.warning(
        'AI Matching Fallback',
        `${stats.failed} of ${stats.attempted} jobs used NLP fallback${reasonsText}`
      );
    }
  }, [result?.gemini_stats]);

  // Resume polling if there's an active search from before (recovery after disconnection)
  useEffect(() => {
    if (activeSearchId && !result) {
      // There's an active search - resume polling
      const controller = new AbortController();
      setAbortController(controller);

      api.pollSearchJobUntilComplete(
        activeSearchId,
        (jobProgress: SearchJobProgress) => {
          updateFromJobProgress(jobProgress);
        },
        2000,
        controller.signal
      ).then((searchResult) => {
        setResult(searchResult);
        toast.success('Search Complete', `Found ${searchResult.high_matches} high-quality matches`);
      }).catch((err) => {
        if (err.message !== 'Search cancelled') {
          setError(err.message);
          toast.error('Error', err.message);
        }
      }).finally(() => {
        setAbortController(null);
      });

      return () => controller.abort();
    }
  }, [activeSearchId]); // Only run when activeSearchId changes (on mount if persisted)

  const handleSearch = useCallback(async () => {
    if (!keyword.trim()) {
      toast.error('Error', 'Please enter a keyword');
      return;
    }
    if (!selectedResume) {
      toast.error('Error', 'Please select a resume');
      return;
    }

    // Abort any previous search
    if (abortController) {
      abortController.abort();
    }

    // Create new abort controller for this search
    const controller = new AbortController();
    setAbortController(controller);

    const params: JobSearchParams = {
      keyword: keyword.trim(),
      location: location || defaults?.location || 'United States',
      job_type: jobType && jobType !== '__any__' ? jobType : undefined,
      experience_level: experienceLevel && experienceLevel !== '__any__' ? experienceLevel : undefined,
      work_arrangement: workArrangement && workArrangement !== '__any__' ? workArrangement : undefined,
      max_results: maxResults,
      resume_filename: selectedResume,
      export_to_sheets: exportToSheets,
    };

    try {
      // Start background search job (returns immediately with search_id)
      const { search_id } = await api.startSearchJob(params);

      // Update store with search ID (persisted for recovery)
      startSearch(search_id);

      // Poll for completion (resilient to disconnections)
      const searchResult = await api.pollSearchJobUntilComplete(
        search_id,
        (jobProgress: SearchJobProgress) => {
          updateFromJobProgress(jobProgress);
          if (jobProgress.stage === 'error') {
            setError(jobProgress.error || 'Search failed');
          }
        },
        2000, // Poll every 2 seconds
        controller.signal
      );

      setResult(searchResult);
      toast.success(
        'Search Complete',
        `Found ${searchResult.high_matches} high-quality matches`
      );
    } catch (err) {
      // Don't show error for aborted/cancelled requests
      if (err instanceof Error && (err.name === 'AbortError' || err.message === 'Search cancelled')) {
        return;
      }
      const message = err instanceof Error ? err.message : 'Search failed';
      setError(message);
      toast.error('Error', message);
    } finally {
      setAbortController(null);
    }
  }, [keyword, location, jobType, experienceLevel, workArrangement, maxResults, selectedResume, exportToSheets, defaults, toast, abortController, setAbortController, startSearch, updateFromJobProgress, setResult, setError]);

  const handleReset = useCallback(() => {
    resetSearch();
  }, [resetSearch]);

  const resumes = resumesData?.resumes || [];

  return (
    <PageTransition>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Get Jobs</h1>
          <p className="text-muted-foreground mt-1">
            Search LinkedIn for jobs and match them against your resume
          </p>
        </div>

        {/* Top-level tabs for Manual vs Scheduled */}
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'manual' | 'scheduled')} className="mb-6">
          <TabsList className="grid w-full max-w-md grid-cols-2">
            <TabsTrigger value="manual" className="flex items-center gap-2">
              <Search className="h-4 w-4" />
              Manual Search
            </TabsTrigger>
            <TabsTrigger value="scheduled" className="flex items-center gap-2">
              <Calendar className="h-4 w-4" />
              Scheduled
            </TabsTrigger>
          </TabsList>

          {/* Manual Search Tab Content */}
          <TabsContent value="manual" className="mt-6">

            {/* Gemini Config Warning Banner */}
            {geminiConfig && !geminiConfig.enabled && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-4 flex items-center gap-3 rounded-lg bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 p-3"
              >
                <Info className="h-5 w-5 text-blue-500 flex-shrink-0" />
                <div className="text-sm text-blue-700 dark:text-blue-300">
                  <span className="font-medium">AI matching is disabled.</span>{' '}
                  Job matches will use NLP-only scoring. Enable Gemini in config for richer insights.
                </div>
              </motion.div>
            )}
            {geminiConfig && geminiConfig.enabled && !geminiConfig.has_api_key && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-4 flex items-center gap-3 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 p-3"
              >
                <AlertTriangle className="h-5 w-5 text-amber-500 flex-shrink-0" />
                <div className="text-sm text-amber-700 dark:text-amber-300">
                  <span className="font-medium">Gemini API key not configured.</span>{' '}
                  Matches will fall back to NLP scoring. Add your API key in config.yaml.
                </div>
              </motion.div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left Column: Search Form */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Search className="h-5 w-5" />
                    Search Parameters
                  </CardTitle>
                  <CardDescription>
                    Configure your job search criteria
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Keyword */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">
                      Keyword <span className="text-red-500">*</span>
                    </label>
                    <div className="relative">
                      <Input
                        placeholder="e.g., Product Manager, Senior Developer"
                        value={keyword}
                        onChange={(e) => setKeyword(e.target.value)}
                        disabled={isSearching}
                        list="keyword-suggestions"
                        autoComplete="off"
                      />
                      <datalist id="keyword-suggestions">
                        {suggestedKeywords?.suggestions.map((s) => (
                          <option key={s.keyword} value={s.keyword}>
                            {s.source === 'scheduled' ? '(Recent)' : ''} {s.keyword}
                          </option>
                        ))}
                      </datalist>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {suggestedKeywords?.suggestions.length ? (
                        <>Type or select from your recent searches</>
                      ) : (
                        <>Tip: Add "Remote" at the end to search for remote jobs</>
                      )}
                    </p>
                  </div>

                  {/* Work Arrangement */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Work Arrangement</label>
                    <Select
                      value={workArrangement}
                      onValueChange={(val) => {
                        setWorkArrangement(val);
                        if (val === 'Remote') {
                          setLocation('');
                        }
                      }}
                      disabled={isSearching}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Any" />
                      </SelectTrigger>
                      <SelectContent>
                        {WORK_ARRANGEMENTS.map((arr) => (
                          <SelectItem key={arr.value || '__any__'} value={arr.value || '__any__'}>
                            {arr.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Location */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Location</label>
                    <Input
                      placeholder={workArrangement === 'Remote' ? 'Remote (Location ignored)' : (defaults?.location || 'United States')}
                      value={location}
                      onChange={(e) => setLocation(e.target.value)}
                      disabled={isSearching || workArrangement === 'Remote'}
                    />
                  </div>

                  {/* Job Type */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Job Type</label>
                    <Select value={jobType} onValueChange={setJobType} disabled={isSearching}>
                      <SelectTrigger>
                        <SelectValue placeholder="Any" />
                      </SelectTrigger>
                      <SelectContent>
                        {JOB_TYPES.map((type) => (
                          <SelectItem key={type.value || '__any__'} value={type.value || '__any__'}>
                            {type.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Experience Level */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Experience Level</label>
                    <Select value={experienceLevel} onValueChange={setExperienceLevel} disabled={isSearching}>
                      <SelectTrigger>
                        <SelectValue placeholder="Any" />
                      </SelectTrigger>
                      <SelectContent>
                        {EXPERIENCE_LEVELS.map((level) => (
                          <SelectItem key={level.value || '__any__'} value={level.value || '__any__'}>
                            {level.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Max Results */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Max Results</label>
                    <Input
                      type="number"
                      min={1}
                      max={100}
                      value={maxResults}
                      onChange={(e) => setMaxResults(Math.min(100, Math.max(1, parseInt(e.target.value) || 25)))}
                      disabled={isSearching}
                    />
                  </div>

                  {/* Resume Selection */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">
                      Resume <span className="text-red-500">*</span>
                    </label>
                    <Select value={selectedResume} onValueChange={setSelectedResume} disabled={isSearching || resumesLoading}>
                      <SelectTrigger>
                        <SelectValue placeholder={resumesLoading ? 'Loading...' : 'Select a resume'} />
                      </SelectTrigger>
                      <SelectContent>
                        {resumes.map((resume) => (
                          <SelectItem key={resume.filename} value={resume.filename}>
                            {resume.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {resumes.length === 0 && !resumesLoading && (
                      <p className="text-xs text-amber-600">
                        No resumes found. Please upload one in the Resume Library first.
                      </p>
                    )}
                  </div>

                  {/* Export to Sheets */}
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="exportToSheets"
                      checked={exportToSheets}
                      onChange={(e) => setExportToSheets(e.target.checked)}
                      disabled={isSearching}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                    <label htmlFor="exportToSheets" className="text-sm">
                      Export results to Google Sheets
                    </label>
                  </div>

                  {/* Search Button */}
                  <Button
                    onClick={handleSearch}
                    disabled={isSearching || !keyword.trim() || !selectedResume}
                    className="w-full"
                    size="lg"
                  >
                    {isSearching ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Searching...
                      </>
                    ) : (
                      <>
                        <Search className="h-4 w-4 mr-2" />
                        Start Search
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>

              {/* Right Column: Progress / Results */}
              <div className="space-y-6">
                <AnimatePresence mode="wait">
                  {/* Initial State */}
                  {!isSearching && !result && !error && (
                    <motion.div
                      key="initial"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                    >
                      <Card className="h-full min-h-[400px] flex items-center justify-center">
                        <div className="text-center p-8">
                          <Search className="h-16 w-16 mx-auto text-muted-foreground/30 mb-4" />
                          <h3 className="text-lg font-medium text-muted-foreground">
                            Ready to Search
                          </h3>
                          <p className="text-sm text-muted-foreground mt-2">
                            Enter your search criteria and click "Start Search" to find matching jobs
                          </p>
                        </div>
                      </Card>
                    </motion.div>
                  )}

                  {/* Progress State */}
                  {isSearching && (
                    <motion.div
                      key="progress"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                    >
                      <Card>
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2">
                            <Loader2 className="h-5 w-5 animate-spin" />
                            Search in Progress
                          </CardTitle>
                          <CardDescription>
                            {progress?.message || 'Starting search...'}
                          </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                          <div className="flex items-center gap-4">
                            <Progress value={progress?.progress || 0} className="h-2 flex-1" />
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={async () => {
                                await cancelSearch();
                                toast.info('Search Cancelled', 'The search has been stopped');
                              }}
                            >
                              <XCircle className="h-4 w-4 mr-1" />
                              Cancel
                            </Button>
                          </div>
                          <ProgressStepper currentStage={progress?.stage || 'initializing'} progress={progress} />

                          {/* Live Stats */}
                          {progress && (progress.jobs_found !== undefined || progress.matches_found !== undefined) && (
                            <div className="grid grid-cols-2 gap-4 pt-4 border-t">
                              {progress.jobs_found !== undefined && (
                                <div className="text-center">
                                  <div className="text-2xl font-bold">{progress.jobs_found}</div>
                                  <div className="text-xs text-muted-foreground">Jobs Found</div>
                                </div>
                              )}
                              {progress.matches_found !== undefined && (
                                <div className="text-center">
                                  <div className="text-2xl font-bold">{progress.matches_found}</div>
                                  <div className="text-xs text-muted-foreground">Matches</div>
                                </div>
                              )}
                              {progress.high_matches !== undefined && (
                                <div className="text-center">
                                  <div className="text-2xl font-bold text-green-600">{progress.high_matches}</div>
                                  <div className="text-xs text-muted-foreground">High Matches</div>
                                </div>
                              )}
                              {progress.exported_count !== undefined && (
                                <div className="text-center">
                                  <div className="text-2xl font-bold">{progress.exported_count}</div>
                                  <div className="text-xs text-muted-foreground">Exported</div>
                                </div>
                              )}
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    </motion.div>
                  )}

                  {/* Error State */}
                  {error && !isSearching && (
                    <motion.div
                      key="error"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                    >
                      <Card className="border-red-200 bg-red-50 dark:bg-red-950 dark:border-red-800">
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2 text-red-600">
                            <XCircle className="h-5 w-5" />
                            Search Failed
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <p className="text-red-600 mb-4">{error}</p>
                          <Button onClick={handleReset} variant="outline">
                            <RefreshCw className="h-4 w-4 mr-2" />
                            Try Again
                          </Button>
                        </CardContent>
                      </Card>
                    </motion.div>
                  )}

                  {/* Results State */}
                  {result && !isSearching && (
                    <motion.div
                      key="results"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                    >
                      <div className="space-y-4">
                        <div className="flex items-center justify-between">
                          <h2 className="text-xl font-semibold">Search Results</h2>
                          <Button onClick={handleReset} variant="outline" size="sm">
                            <RefreshCw className="h-4 w-4 mr-2" />
                            New Search
                          </Button>
                        </div>
                        <ResultsPanel result={result} />
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </TabsContent>

          {/* Scheduled Tab Content */}
          <TabsContent value="scheduled" className="mt-6">
            {showScheduleForm || editingSchedule ? (
              <div className="max-w-2xl">
                <ScheduleForm
                  schedule={editingSchedule}
                  onClose={() => {
                    setShowScheduleForm(false);
                    setEditingSchedule(null);
                  }}
                  onSaved={() => {
                    setShowScheduleForm(false);
                    setEditingSchedule(null);
                  }}
                />
              </div>
            ) : (
              <ScheduleList
                onEdit={(schedule) => setEditingSchedule(schedule)}
                onCreateNew={() => setShowScheduleForm(true)}
              />
            )}
          </TabsContent>
        </Tabs>
      </div>
    </PageTransition>
  );
}

export default GetJobs;
