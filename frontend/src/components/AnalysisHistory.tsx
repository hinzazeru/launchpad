import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAnalysisHistory, useResumes } from '@/services/api';
import type { AnalysisHistoryFilters } from '@/services/api';
import { AnalysisHistoryCard } from '@/components/AnalysisHistoryCard';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Search,
  Sparkles,
  History,
  ArrowUpDown,
  FileText,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Check,
  Clock,
  Filter,
  BarChart3,
} from 'lucide-react';
import { useDebounce } from '@/hooks/use-debounce';

interface AnalysisHistoryProps {
  onSelectAnalysis: (jobId: number, resumeId: number) => void;
}

// Skeleton loader for history cards
function AnalysisHistoryCardSkeleton({ index = 0 }: { index?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
      className="rounded-xl border border-border/50 p-4 pl-5 bg-card"
    >
      <div className="flex gap-4">
        {/* Score skeleton */}
        <div className="w-16 h-16 rounded-full bg-muted/40 animate-pulse shrink-0" />

        {/* Content skeleton */}
        <div className="flex-1 space-y-3">
          <div className="flex justify-between">
            <div className="space-y-2">
              <div className="h-4 w-48 bg-muted/40 rounded-md animate-pulse" />
              <div className="h-3 w-32 bg-muted/40 rounded-md animate-pulse" />
            </div>
            <div className="h-5 w-12 bg-muted/40 rounded-full animate-pulse" />
          </div>
          <div className="flex gap-2">
            <div className="h-3 w-20 bg-muted/40 rounded-md animate-pulse" />
            <div className="h-3 w-16 bg-muted/40 rounded-md animate-pulse" />
            <div className="h-3 w-24 bg-muted/40 rounded-md animate-pulse" />
          </div>
          <div className="flex justify-between">
            <div className="h-3 w-24 bg-muted/40 rounded-md animate-pulse" />
            <div className="h-3 w-20 bg-muted/40 rounded-md animate-pulse" />
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export function AnalysisHistory({ onSelectAnalysis }: AnalysisHistoryProps) {
  // Filter state
  const [search, setSearch] = useState('');
  const [resumeId, setResumeId] = useState<number | undefined>(undefined);
  const [minScore, setMinScore] = useState<number | undefined>(undefined);
  const [maxScore, setMaxScore] = useState<number | undefined>(undefined);
  const [hasAiSuggestions, setHasAiSuggestions] = useState<boolean | undefined>(undefined);
  const [sortBy, setSortBy] = useState<'date' | 'score'>('date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(0);
  const limit = 20;

  // Debounce search
  const debouncedSearch = useDebounce(search, 300);

  // Build filters
  const filters: AnalysisHistoryFilters = useMemo(
    () => ({
      search: debouncedSearch || undefined,
      resume_id: resumeId,
      min_score: minScore,
      max_score: maxScore,
      has_ai_suggestions: hasAiSuggestions,
      sort_by: sortBy,
      sort_order: sortOrder,
      skip: page * limit,
      limit,
    }),
    [debouncedSearch, resumeId, minScore, maxScore, hasAiSuggestions, sortBy, sortOrder, page]
  );

  // Fetch data
  const { data, isLoading, isFetching } = useAnalysisHistory(filters);
  const { data: resumesData } = useResumes();

  // Calculate pagination
  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  // Stats
  const withAiCount = useMemo(() => {
    return data?.items.filter((item) => item.has_bullet_suggestions).length || 0;
  }, [data?.items]);

  // Reset page when filters change
  const handleFilterChange = () => {
    setPage(0);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-4"
      >
        <div className="p-3 rounded-xl bg-primary/10">
          <Clock className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Analysis History</h2>
          <p className="text-sm text-muted-foreground">
            Browse and revisit your previous job-resume analyses
          </p>
        </div>
      </motion.div>

      {/* Filter Bar */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="p-5 rounded-xl bg-card border border-border/50 shadow-sm"
      >
        {/* Filter header */}
        <div className="flex items-center gap-2 mb-4">
          <Filter className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm font-medium">Filters</span>
        </div>

        <div className="flex flex-col lg:flex-row gap-4">
          {/* Search */}
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search job title or company..."
                className="pl-9 bg-background/50 h-10"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  handleFilterChange();
                }}
              />
            </div>
          </div>

          {/* Resume filter */}
          <div className="w-full lg:w-52">
            <Select
              value={resumeId?.toString() || 'all'}
              onValueChange={(v) => {
                setResumeId(v === 'all' ? undefined : Number(v));
                handleFilterChange();
              }}
            >
              <SelectTrigger className="bg-background/50 h-10">
                <FileText className="w-4 h-4 mr-2 text-muted-foreground" />
                <SelectValue placeholder="All resumes" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All resumes</SelectItem>
                {resumesData?.resumes.map((resume) => (
                  <SelectItem key={resume.filename} value="1">
                    {resume.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Score range */}
          <div className="flex items-center gap-2 p-2 rounded-lg bg-muted/30 border border-border/50">
            <BarChart3 className="w-4 h-4 text-muted-foreground shrink-0" />
            <span className="text-xs text-muted-foreground whitespace-nowrap font-medium">Score</span>
            <Input
              type="number"
              placeholder="Min"
              min={0}
              max={100}
              className="w-16 h-8 bg-background/80 text-sm"
              value={minScore ?? ''}
              onChange={(e) => {
                setMinScore(e.target.value ? Number(e.target.value) : undefined);
                handleFilterChange();
              }}
            />
            <span className="text-muted-foreground text-xs">to</span>
            <Input
              type="number"
              placeholder="Max"
              min={0}
              max={100}
              className="w-16 h-8 bg-background/80 text-sm"
              value={maxScore ?? ''}
              onChange={(e) => {
                setMaxScore(e.target.value ? Number(e.target.value) : undefined);
                handleFilterChange();
              }}
            />
          </div>

          {/* Sort */}
          <div className="flex items-center gap-2">
            <Select value={sortBy} onValueChange={(v: 'date' | 'score') => setSortBy(v)}>
              <SelectTrigger className="w-32 bg-background/50 h-10">
                <ArrowUpDown className="w-4 h-4 mr-2 text-muted-foreground" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="date">Date</SelectItem>
                <SelectItem value="score">Score</SelectItem>
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="icon"
              className="h-10 w-10 transition-all"
              onClick={() => setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))}
            >
              <motion.span
                key={sortOrder}
                initial={{ opacity: 0, y: sortOrder === 'desc' ? -10 : 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-sm font-medium"
              >
                {sortOrder === 'desc' ? '↓' : '↑'}
              </motion.span>
            </Button>
          </div>
        </div>

        {/* Second row - filter toggles */}
        <div className="flex items-center gap-3 mt-4 pt-4 border-t border-border/50">
          <span className="text-xs text-muted-foreground font-medium">Quick filters:</span>
          <Button
            variant={hasAiSuggestions === true ? 'default' : 'outline'}
            size="sm"
            className={`h-8 px-3 text-xs gap-1.5 transition-all ${
              hasAiSuggestions === true
                ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                : ''
            }`}
            onClick={() => {
              setHasAiSuggestions(hasAiSuggestions === true ? undefined : true);
              handleFilterChange();
            }}
          >
            {hasAiSuggestions === true && <Check className="w-3 h-3" />}
            <Sparkles className={`w-3.5 h-3.5 ${hasAiSuggestions === true ? '' : 'text-emerald-500'}`} />
            Has AI suggestions
          </Button>
        </div>
      </motion.div>

      {/* Stats bar */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="flex items-center justify-between px-1"
      >
        <div className="flex items-center gap-6 text-sm">
          <span className="flex items-center gap-2 text-muted-foreground">
            <div className="p-1.5 rounded-md bg-muted/50">
              <History className="w-3.5 h-3.5" />
            </div>
            <span className="font-medium">{data?.total || 0}</span> analyses
          </span>
          {withAiCount > 0 && (
            <span className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
              <div className="p-1.5 rounded-md bg-emerald-500/10">
                <Sparkles className="w-3.5 h-3.5" />
              </div>
              <span className="font-medium">{withAiCount}</span> with AI suggestions
            </span>
          )}
          {isFetching && !isLoading && (
            <span className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" />
              Updating...
            </span>
          )}
        </div>

        {/* Pagination info */}
        {totalPages > 1 && (
          <span className="text-sm text-muted-foreground">
            Page <span className="font-medium">{page + 1}</span> of <span className="font-medium">{totalPages}</span>
          </span>
        )}
      </motion.div>

      {/* Results list */}
      <div className="space-y-3">
        <AnimatePresence mode="wait">
          {isLoading ? (
            // Loading skeletons
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="space-y-3"
            >
              {[...Array(5)].map((_, i) => (
                <AnalysisHistoryCardSkeleton key={i} index={i} />
              ))}
            </motion.div>
          ) : data?.items.length === 0 ? (
            // Empty state
            <motion.div
              key="empty"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
            >
              <Card className="p-12 text-center border-dashed">
                <CardContent className="space-y-4 p-0">
                  <div className="mx-auto w-16 h-16 rounded-full bg-muted/50 flex items-center justify-center">
                    <History className="w-8 h-8 text-muted-foreground/50" />
                  </div>
                  <div className="space-y-2">
                    <h3 className="font-semibold text-lg">No analyses found</h3>
                    <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                      {search || hasAiSuggestions !== undefined
                        ? 'No results match your current filters. Try adjusting your search criteria.'
                        : 'Run your first resume analysis to see history here. Go to "New Analysis" tab to get started.'}
                    </p>
                  </div>
                  {(search || hasAiSuggestions !== undefined) && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-2"
                      onClick={() => {
                        setSearch('');
                        setHasAiSuggestions(undefined);
                        setMinScore(undefined);
                        setMaxScore(undefined);
                        setResumeId(undefined);
                      }}
                    >
                      Clear all filters
                    </Button>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          ) : (
            // Results
            <motion.div
              key="results"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="space-y-3"
            >
              {data?.items.map((item, index) => (
                <AnalysisHistoryCard
                  key={item.match_id}
                  item={item}
                  index={index}
                  onSelect={onSelectAnalysis}
                />
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="flex items-center justify-center gap-2 pt-4"
        >
          <Button
            variant="outline"
            size="sm"
            className="h-9 px-3"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
          >
            <ChevronLeft className="w-4 h-4 mr-1" />
            Previous
          </Button>
          <div className="flex items-center gap-1">
            {[...Array(Math.min(5, totalPages))].map((_, i) => {
              const pageNum = Math.max(
                0,
                Math.min(totalPages - 5, page - 2)
              ) + i;
              if (pageNum >= totalPages) return null;
              return (
                <Button
                  key={pageNum}
                  variant={pageNum === page ? 'default' : 'ghost'}
                  size="sm"
                  className={`w-9 h-9 ${pageNum === page ? '' : 'text-muted-foreground'}`}
                  onClick={() => setPage(pageNum)}
                >
                  {pageNum + 1}
                </Button>
              );
            })}
          </div>
          <Button
            variant="outline"
            size="sm"
            className="h-9 px-3"
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
          >
            Next
            <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        </motion.div>
      )}
    </div>
  );
}
