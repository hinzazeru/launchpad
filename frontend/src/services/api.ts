/**
 * API client service for communicating with the FastAPI backend.
 */

const API_BASE = '/api';

// Types matching backend Pydantic models

export interface SkillMatchDetail {
  job_skill: string;
  resume_skill: string;
  confidence: number;
  context?: string;
}

export interface SkillGapDetail {
  skill: string;
  importance: 'must_have' | 'nice_to_have';
  transferable_from?: string;
}

export interface Job {
  id: number;
  title: string;
  company: string;
  description: string;
  summary?: string;
  url?: string;
  location?: string;
  salary?: string;
  posting_date?: string;
  domains: string[];
  match_score: number;
  matching_skills: string[];
  gemini_score?: number;
  gemini_reasoning?: string;
  gemini_strengths?: string[];
  gemini_gaps?: string[];
  missing_domains?: string[];
  experience_alignment?: string;
  required_skills?: string[];
  // Score breakdown fields
  skills_matched_count: number;
  skills_required_count: number;
  skill_gaps: string[];
  experience_required?: number;

  // New AI matching fields
  ai_match_score?: number;
  skills_score?: number;
  experience_score?: number;
  seniority_fit?: number;
  domain_score?: number;

  // Rich AI insights
  ai_strengths?: string[];
  ai_concerns?: string[];
  ai_recommendations?: string[];

  // Detailed skill analysis
  skill_matches?: SkillMatchDetail[];
  skill_gaps_detailed?: SkillGapDetail[];

  // Matching metadata
  match_engine?: 'nlp' | 'gemini';
  match_confidence?: number;
}

export interface JobListResponse {
  jobs: Job[];
  total: number;
  filtered: number;
}

export interface ResumeMetadata {
  filename: string;
  name: string;
  format: 'text' | 'json';
  saved_at?: string;
  char_count?: number;
}

export interface ResumeListResponse {
  resumes: ResumeMetadata[];
  total: number;
}

export interface ResumeRole {
  company: string;
  title: string;
  duration: string;
  bullets: string[];
  location?: string;
  technologies: string[];
}

export interface ResumePreview {
  summary: string;
  roles: ResumeRole[];
  education: string;
  skills: Record<string, string[]>;
  source_format: string;
}

export interface DomainSuggestion {
  domain: string;
  confidence: number;
  category: string;
  evidence: string;
  description: string;
}

export interface SuggestedDomainsResponse {
  filename: string;
  suggestions: DomainSuggestion[];
  total: number;
}

export interface BulletScore {
  text: string;
  score: number;
  matched_keywords: string[];
  missing_keywords: string[];
  suggestions: string[];
}

export interface RoleAnalysis {
  company: string;
  title: string;
  duration: string;
  alignment_score: number;
  bullet_scores: BulletScore[];
  low_scoring_count: number;
}

export interface AnalyzeResponse {
  success: boolean;
  overall_alignment: number;
  total_bullets: number;
  low_scoring_bullets: number;
  roles: RoleAnalysis[];
  job_title?: string;
  job_company?: string;
}

export interface BulletSuggestion {
  index: number;
  original: string;
  score: number;
  analysis: string;
  suggestions: string[];
}

export interface SuggestionsResponse {
  success: boolean;
  role_index: number;
  bullet_suggestions: BulletSuggestion[];
}

export interface ExportResponse {
  success: boolean;
  filename: string;
  download_url: string;
  changes_made: number;
}

export interface GeminiStatus {
  available: boolean;
  message: string;
}

// Analysis history types

export interface AnalysisRoleSummary {
  company: string;
  title: string;
  bullet_count: number;
  has_suggestions: boolean;
}

export interface AnalysisHistoryItem {
  match_id: number;
  job_id: number;
  job_title: string;
  job_company: string;
  job_location?: string;
  job_url?: string;
  resume_id: number;
  match_score: number;
  ai_match_score?: number;
  match_engine: 'nlp' | 'gemini';
  generated_date: string;
  has_bullet_suggestions: boolean;
  roles_summary: AnalysisRoleSummary[];
  ai_strengths_count: number;
  ai_concerns_count: number;
}

export interface AnalysisHistoryFilters {
  search?: string;
  resume_id?: number;
  date_from?: string;
  date_to?: string;
  min_score?: number;
  max_score?: number;
  has_ai_suggestions?: boolean;
  sort_by?: 'date' | 'score';
  sort_order?: 'asc' | 'desc';
  skip?: number;
  limit?: number;
}

export interface AnalysisHistoryResponse {
  items: AnalysisHistoryItem[];
  total: number;
  skip: number;
  limit: number;
}

// Match suggestions detail types

export interface BulletSuggestionDetail {
  index: number;
  original: string;
  score?: number;
  analysis?: string;
  suggestions: string[];
}

export interface RoleBulletSuggestions {
  role_key: string;
  company: string;
  title: string;
  bullets: BulletSuggestionDetail[];
}

export interface MatchSuggestionsResponse {
  match_id: number;
  job_title: string;
  job_company: string;
  roles: RoleBulletSuggestions[];
  total_bullets: number;
  total_with_suggestions: number;
}

export interface JobStats {
  total_jobs: number;
  average_match_score: number;
  high_match_count: number;
  recent_count: number;
}

export interface LikedBullet {
  id: number;
  original_text: string;
  rewritten_text: string;
  role_title?: string;
  company?: string;
  job_id?: number;
  created_at: string;
}

export interface SaveLikedBulletParams {
  original_text: string;
  rewritten_text: string;
  role_title?: string;
  company?: string;
  job_id?: number;
}

export interface PaginatedLikedBulletsResponse {
  items: LikedBullet[];
  total: number;
  skip: number;
  limit: number;
}

// Search types

export type SearchStage =
  | 'initializing'
  | 'fetching'
  | 'importing'
  | 'matching'
  | 'exporting'
  | 'completed'
  | 'error';

export interface JobSearchParams {
  keyword: string;
  location: string;
  job_type?: string;
  experience_level?: string;
  work_arrangement?: string;
  max_results: number;
  resume_filename: string;
  export_to_sheets: boolean;
}

export interface SearchProgress {
  stage: SearchStage;
  progress: number;
  message: string;
  jobs_found?: number;
  jobs_imported?: number;
  matches_found?: number;
  high_matches?: number;
  exported_count?: number;
  error?: string;
}

export interface TopMatch {
  title: string;
  company: string;
  location?: string;
  url?: string;
  score: number;
  gemini_score?: number;
}

export interface GeminiStats {
  attempted: number;
  succeeded: number;
  failed: number;
  failure_reasons: string[];
}

export interface SearchResult {
  success: boolean;
  jobs_fetched: number;
  jobs_imported: number;
  jobs_matched: number;
  high_matches: number;
  exported_to_sheets: number;
  duration_seconds: number;
  top_matches: TopMatch[];
  fetched_jobs: TopMatch[];
  sheets_url?: string;
  gemini_stats?: GeminiStats;
}

// Background Job Queue Types (resilient to disconnections)

export interface SearchJobStartResponse {
  search_id: string;
  status: string;
  message: string;
}

export interface SearchJobProgress {
  search_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  stage: SearchStage;
  progress: number;
  message?: string;
  jobs_found?: number;
  jobs_imported?: number;
  matches_found?: number;
  high_matches?: number;
  exported_count?: number;
  result?: SearchResult;
  error?: string;
  created_at: string;
  updated_at: string;
}

export interface SearchJobListResponse {
  jobs: SearchJobProgress[];
  total: number;
}

export interface GeminiConfigStatus {
  enabled: boolean;
  matcher_enabled: boolean;
  has_api_key: boolean;
  mode: string;
  model?: string;
}

export interface GeminiHealthResponse {
  available: boolean;
  model?: string;
  latency_ms?: number;
  error?: string;
}

export interface SearchDefaults {
  location: string;
  max_results: number;
  job_type?: string;
  experience_level?: string;
  work_arrangement?: string;
  posted_when: string;
}

export interface SuggestedKeyword {
  keyword: string;
  count: number;
  source: 'scheduled' | 'job_titles';
}

export interface SuggestedKeywordsResponse {
  suggestions: SuggestedKeyword[];
}

// Analytics types

export interface SummaryMetrics {
  total_jobs: number;
  high_matches: number;
  ai_analysed: number;
  avg_score: number;
}

export interface SkillCount {
  name: string;
  count: number;
}

export interface SkillsAnalytics {
  skill_gaps: SkillCount[];
  matching_skills: SkillCount[];
  in_demand_skills: SkillCount[];
}

export interface CompanyCount {
  name: string;
  count: number;
}

export interface LocationCount {
  name: string;
  count: number;
}

export interface MarketAnalytics {
  top_companies: CompanyCount[];
  locations: LocationCount[];
}

export interface TimelinePoint {
  date: string;
  jobs_fetched: number;
  matches_generated: number;
}

export interface TimelineAnalytics {
  points: TimelinePoint[];
}

export interface ScoreDistribution {
  range: string;
  count: number;
}

export interface LatencyMetric {
  name: string;
  avg_ms: number;
  p50_ms: number;
  p90_ms: number;
  p99_ms: number;
  count: number;
}

export interface PerformanceSummary {
  avg_search_duration_ms: number;
  avg_gemini_latency_ms: number;
  search_success_rate: number;
  total_searches_30d: number;
  total_api_calls_30d: number;
  latencies: LatencyMetric[];
}

// New performance analytics types

export interface MatchingDistributionPoint {
  date: string;
  nlp_count: number;
  gemini_count: number;
}

export interface MatchingDistribution {
  points: MatchingDistributionPoint[];
}

export interface GeminiUsageDay {
  date: string;
  matching: number;
  rerank: number;
  suggestions: number;
  total: number;
}

export interface GeminiUsageTotals {
  matching: number;
  rerank: number;
  suggestions: number;
  total: number;
}

export interface GeminiUsageResponse {
  data: GeminiUsageDay[];
  totals: GeminiUsageTotals;
}

export interface PerformanceTimelinePoint {
  date: string;
  avg_ms: number;
  count: number;
}

export interface PerformanceTimeline {
  points: PerformanceTimelinePoint[];
}

export interface StageMetric {
  avg_ms: number;
  pct: number;
}

export interface PerformanceBreakdown {
  stages: Record<string, StageMetric>;
}

export interface ApiLatencyDetail {
  p50: number;
  p90: number;
  p99: number;
  count: number;
}

export interface RecentSearch {
  search_id: string;
  created_at: string;
  total_duration_ms: number | null;
  jobs_fetched: number;
  jobs_matched: number;
  high_matches: number;
  status: string;
  error_message: string | null;
  trigger_source: 'manual' | 'scheduled';
}

export interface RecentSearchesResponse {
  searches: RecentSearch[];
}

// Domain types

export interface DomainInfo {
  key: string;
  name: string;
  description: string;
}

export interface AvailableDomainsResponse {
  categories: {
    industries: DomainInfo[];
    platforms: DomainInfo[];
    technologies: DomainInfo[];
  };
}

export interface UserDomainsResponse {
  domains: string[];
}

// Scheduler types

export interface ScheduledSearch {
  id: number;
  name: string;
  keyword: string;
  location: string;
  job_type?: string;
  experience_level?: string;
  work_arrangement?: string;
  max_results: number;
  resume_filename: string;
  export_to_sheets: boolean;
  enabled: boolean;
  run_times: string[];
  timezone: string;
  created_at: string;
  updated_at: string;
  last_run_at?: string;
  next_run_at?: string;
  last_run_status?: string;
}

export interface ScheduleCreateParams {
  name: string;
  keyword: string;
  location?: string;
  job_type?: string;
  experience_level?: string;
  work_arrangement?: string;
  max_results?: number;
  resume_filename: string;
  export_to_sheets?: boolean;
  enabled?: boolean;
  run_times?: string[];
  timezone?: string;
}

export interface ScheduleUpdateParams {
  name?: string;
  keyword?: string;
  location?: string;
  job_type?: string;
  experience_level?: string;
  work_arrangement?: string;
  max_results?: number;
  resume_filename?: string;
  export_to_sheets?: boolean;
  enabled?: boolean;
  run_times?: string[];
  timezone?: string;
}

export interface ScheduleListResponse {
  schedules: ScheduledSearch[];
  total: number;
}

export interface SchedulerStatus {
  running: boolean;
  active_schedules: number;
  next_run_at?: string;
  next_schedule_name?: string;
}

export interface ScheduleToggleResponse {
  id: number;
  name: string;
  enabled: boolean;
  next_run_at?: string;
  message: string;
}

export interface ScheduleRunNowResponse {
  id: number;
  name: string;
  message: string;
  search_id: string;
}

// API client class

class ApiClient {
  private async fetch<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // Jobs endpoints

  async getJobs(params?: {
    min_score?: number;
    max_score?: number;
    recency_days?: number;
    search?: string;
    sort_by?: 'score' | 'date';
    sort_order?: 'asc' | 'desc';
    limit?: number;
  }): Promise<JobListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.min_score !== undefined) searchParams.set('min_score', String(params.min_score));
    if (params?.max_score !== undefined) searchParams.set('max_score', String(params.max_score));
    if (params?.recency_days !== undefined) searchParams.set('recency_days', String(params.recency_days));
    if (params?.search) searchParams.set('search', params.search);
    if (params?.sort_by) searchParams.set('sort_by', params.sort_by);
    if (params?.sort_order) searchParams.set('sort_order', params.sort_order);
    if (params?.limit !== undefined) searchParams.set('limit', String(params.limit));

    const query = searchParams.toString();
    return this.fetch<JobListResponse>(`/jobs${query ? `?${query}` : ''}`);
  }

  async getJob(id: number): Promise<Job> {
    return this.fetch<Job>(`/jobs/${id}`);
  }

  async getJobStats(): Promise<JobStats> {
    return this.fetch<JobStats>('/jobs/stats/summary');
  }

  // Resumes endpoints

  async getResumes(): Promise<ResumeListResponse> {
    return this.fetch<ResumeListResponse>('/resumes');
  }

  async getResume(filename: string): Promise<{ filename: string; content: string; format: string }> {
    return this.fetch(`/resumes/${encodeURIComponent(filename)}`);
  }

  async getResumePreview(filename: string): Promise<ResumePreview> {
    return this.fetch<ResumePreview>(`/resumes/${encodeURIComponent(filename)}/preview`);
  }

  async getSuggestedDomains(filename: string): Promise<SuggestedDomainsResponse> {
    return this.fetch<SuggestedDomainsResponse>(`/resumes/${encodeURIComponent(filename)}/suggested-domains`);
  }

  async uploadResume(file: File, name: string): Promise<{ success: boolean; filename: string; message: string }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', name);

    const response = await fetch(`${API_BASE}/resumes`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  async deleteResume(filename: string): Promise<{ success: boolean; message: string }> {
    return this.fetch(`/resumes/${encodeURIComponent(filename)}`, { method: 'DELETE' });
  }

  // Analysis endpoints

  async analyzeResume(params: {
    resume_content?: string;
    resume_filename?: string;
    job_id?: number;
    job_description?: string;
    job_title?: string;
    job_company?: string;
    threshold?: number;
  }): Promise<AnalyzeResponse> {
    return this.fetch<AnalyzeResponse>('/analysis/analyze', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async generateSuggestions(params: {
    resume_content?: string;
    resume_filename?: string;
    role_index: number;
    job_title: string;
    job_company: string;
    job_description: string;
    job_id?: number;
  }): Promise<SuggestionsResponse> {
    return this.fetch<SuggestionsResponse>('/analysis/suggestions', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async exportResume(params: {
    resume_content?: string;
    resume_filename?: string;
    selections: Record<string, Array<{ original: string; selected: string; type: string }>>;
    company: string;
  }): Promise<ExportResponse> {
    return this.fetch<ExportResponse>('/analysis/export', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async getGeminiStatus(): Promise<GeminiStatus> {
    return this.fetch<GeminiStatus>('/analysis/gemini-status');
  }

  async getAnalysisHistory(params?: AnalysisHistoryFilters): Promise<AnalysisHistoryResponse> {
    const searchParams = new URLSearchParams();
    if (params?.search) searchParams.set('search', params.search);
    if (params?.resume_id !== undefined) searchParams.set('resume_id', String(params.resume_id));
    if (params?.date_from) searchParams.set('date_from', params.date_from);
    if (params?.date_to) searchParams.set('date_to', params.date_to);
    if (params?.min_score !== undefined) searchParams.set('min_score', String(params.min_score));
    if (params?.max_score !== undefined) searchParams.set('max_score', String(params.max_score));
    if (params?.has_ai_suggestions !== undefined) searchParams.set('has_ai_suggestions', String(params.has_ai_suggestions));
    if (params?.sort_by) searchParams.set('sort_by', params.sort_by);
    if (params?.sort_order) searchParams.set('sort_order', params.sort_order);
    if (params?.skip !== undefined) searchParams.set('skip', String(params.skip));
    if (params?.limit !== undefined) searchParams.set('limit', String(params.limit));

    const query = searchParams.toString();
    return this.fetch<AnalysisHistoryResponse>(`/analysis/history${query ? `?${query}` : ''}`);
  }

  async getMatchSuggestions(matchId: number): Promise<MatchSuggestionsResponse> {
    return this.fetch<MatchSuggestionsResponse>(`/analysis/history/${matchId}/suggestions`);
  }

  getDownloadUrl(filename: string): string {
    return `${API_BASE}/analysis/download/${encodeURIComponent(filename)}`;
  }

  // Bullet endpoints

  async saveLikedBullet(params: SaveLikedBulletParams): Promise<LikedBullet> {
    return this.fetch<LikedBullet>('/bullets', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async getLikedBullets(params?: {
    skip?: number;
    limit?: number;
    role_filter?: string;
  }): Promise<PaginatedLikedBulletsResponse> {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.set('skip', String(params.skip));
    if (params?.limit !== undefined) searchParams.set('limit', String(params.limit));
    if (params?.role_filter) searchParams.set('role_filter', params.role_filter);

    const query = searchParams.toString();
    return this.fetch<PaginatedLikedBulletsResponse>(`/bullets${query ? `?${query}` : ''}`);
  }

  async getUniqueRoles(): Promise<string[]> {
    return this.fetch<string[]>('/bullets/roles');
  }

  async deleteLikedBullet(id: number): Promise<{ status: string }> {
    return this.fetch<{ status: string }>(`/bullets/${id}`, { method: 'DELETE' });
  }

  // Search endpoints

  async getSearchDefaults(): Promise<SearchDefaults> {
    return this.fetch<SearchDefaults>('/search/defaults');
  }

  async getSuggestedKeywords(limit: number = 7): Promise<SuggestedKeywordsResponse> {
    return this.fetch<SuggestedKeywordsResponse>(`/search/suggested-keywords?limit=${limit}`);
  }

  /**
   * Get Gemini configuration status.
   * Used to show warnings if Gemini is not properly configured.
   */
  async getGeminiConfigStatus(): Promise<GeminiConfigStatus> {
    return this.fetch<GeminiConfigStatus>('/search/config/gemini-status');
  }

  /**
   * Check Gemini API health/availability.
   * Used for pre-search validation.
   */
  async checkGeminiHealth(): Promise<GeminiHealthResponse> {
    return this.fetch<GeminiHealthResponse>('/search/health/gemini');
  }

  // Analytics endpoints

  async getAnalyticsSummary(): Promise<SummaryMetrics> {
    return this.fetch<SummaryMetrics>('/analytics/summary');
  }

  async getAnalyticsSkills(topN: number = 10): Promise<SkillsAnalytics> {
    return this.fetch<SkillsAnalytics>(`/analytics/skills?top_n=${topN}`);
  }

  async getAnalyticsMarket(topN: number = 10, minScore: number = 60): Promise<MarketAnalytics> {
    return this.fetch<MarketAnalytics>(`/analytics/market?top_n=${topN}&min_score=${minScore}`);
  }

  async getAnalyticsTimeline(days: number = 30): Promise<TimelineAnalytics> {
    return this.fetch<TimelineAnalytics>(`/analytics/timeline?days=${days}`);
  }

  async getScoreDistribution(): Promise<ScoreDistribution[]> {
    return this.fetch<ScoreDistribution[]>('/analytics/score-distribution');
  }

  async getPerformanceSummary(): Promise<PerformanceSummary> {
    return this.fetch<PerformanceSummary>('/analytics/performance/summary');
  }

  async getPerformanceTimeline(days: number = 30): Promise<PerformanceTimeline> {
    return this.fetch<PerformanceTimeline>(`/analytics/performance/timeline?days=${days}`);
  }

  async getPerformanceBreakdown(days: number = 7): Promise<PerformanceBreakdown> {
    return this.fetch<PerformanceBreakdown>(`/analytics/performance/breakdown?days=${days}`);
  }

  async getMatchingDistribution(days: number = 30): Promise<MatchingDistribution> {
    return this.fetch<MatchingDistribution>(`/analytics/matching-distribution?days=${days}`);
  }

  async getGeminiUsage(days: number = 30): Promise<GeminiUsageResponse> {
    return this.fetch<GeminiUsageResponse>(`/analytics/gemini-usage?days=${days}`);
  }

  async getApiLatency(days: number = 7): Promise<Record<string, ApiLatencyDetail>> {
    return this.fetch<Record<string, ApiLatencyDetail>>(`/analytics/performance/api-latency?days=${days}`);
  }

  async getRecentSearches(limit: number = 20): Promise<RecentSearchesResponse> {
    return this.fetch<RecentSearchesResponse>(`/analytics/performance/recent-searches?limit=${limit}`);
  }

  // Domain endpoints

  async getAvailableDomains(): Promise<AvailableDomainsResponse> {
    return this.fetch<AvailableDomainsResponse>('/domains/available');
  }

  async getUserDomains(): Promise<UserDomainsResponse> {
    return this.fetch<UserDomainsResponse>('/domains/user');
  }

  async updateUserDomains(domains: string[]): Promise<UserDomainsResponse> {
    return this.fetch<UserDomainsResponse>('/domains/user', {
      method: 'PUT',
      body: JSON.stringify({ domains }),
    });
  }

  // Scheduler endpoints

  async getSchedules(): Promise<ScheduleListResponse> {
    return this.fetch<ScheduleListResponse>('/scheduler/schedules');
  }

  async getSchedule(id: number): Promise<ScheduledSearch> {
    return this.fetch<ScheduledSearch>(`/scheduler/schedules/${id}`);
  }

  async createSchedule(params: ScheduleCreateParams): Promise<ScheduledSearch> {
    return this.fetch<ScheduledSearch>('/scheduler/schedules', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async updateSchedule(id: number, params: ScheduleUpdateParams): Promise<ScheduledSearch> {
    return this.fetch<ScheduledSearch>(`/scheduler/schedules/${id}`, {
      method: 'PUT',
      body: JSON.stringify(params),
    });
  }

  async deleteSchedule(id: number): Promise<void> {
    await this.fetch<void>(`/scheduler/schedules/${id}`, { method: 'DELETE' });
  }

  async toggleSchedule(id: number): Promise<ScheduleToggleResponse> {
    return this.fetch<ScheduleToggleResponse>(`/scheduler/schedules/${id}/toggle`, {
      method: 'POST',
    });
  }

  async runScheduleNow(id: number): Promise<ScheduleRunNowResponse> {
    return this.fetch<ScheduleRunNowResponse>(`/scheduler/schedules/${id}/run-now`, {
      method: 'POST',
    });
  }

  async getSchedulerStatus(): Promise<SchedulerStatus> {
    return this.fetch<SchedulerStatus>('/scheduler/status');
  }

  /**
   * Execute job search with SSE progress streaming.
   * @param params Search parameters
   * @param onProgress Callback for progress updates
   * @param signal Optional AbortSignal for cancellation
   * @returns Final search result
   */
  async searchJobs(
    params: JobSearchParams,
    onProgress: (progress: SearchProgress) => void,
    signal?: AbortSignal
  ): Promise<SearchResult> {
    const response = await fetch(`${API_BASE}/search/jobs`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(params),
      signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Search failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let result: SearchResult | null = null;

    if (!reader) {
      throw new Error('Failed to get response stream');
    }

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n').filter((line) => line.startsWith('data: '));

        for (const line of lines) {
          try {
            const data = JSON.parse(line.slice(6)); // Remove "data: " prefix

            // Check if this is the final result
            if (data.type === 'result' && data.data) {
              result = data.data as SearchResult;
            } else if (data.stage) {
              // This is a progress update
              onProgress(data as SearchProgress);
            }
          } catch {
            // Ignore parse errors for incomplete chunks
          }
        }
      }
    } finally {
      reader.releaseLock();
    }

    if (!result) {
      throw new Error('Search completed without result');
    }

    return result;
  }

  // =========================================================================
  // Background Job Queue Methods (resilient to disconnections)
  // =========================================================================

  /**
   * Start a job search in the background.
   * Returns immediately with a search_id for polling.
   */
  async startSearchJob(params: JobSearchParams): Promise<SearchJobStartResponse> {
    return this.fetch<SearchJobStartResponse>('/search/jobs/start', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  /**
   * Get the current progress of a search job.
   * Poll this every 2-3 seconds until status is 'completed' or 'failed'.
   */
  async getSearchJobProgress(searchId: string): Promise<SearchJobProgress> {
    return this.fetch<SearchJobProgress>(`/search/jobs/${searchId}/status`);
  }

  /**
   * List recent search jobs (for recovery after disconnection).
   */
  async getRecentSearchJobs(limit: number = 10): Promise<SearchJobListResponse> {
    return this.fetch<SearchJobListResponse>(`/search/jobs/recent?limit=${limit}`);
  }

  /**
   * Request cancellation of a running search job.
   */
  async cancelSearchJob(searchId: string): Promise<void> {
    await this.fetch(`/search/jobs/${searchId}/cancel`, { method: 'POST' });
  }

  /**
   * Poll for search job completion with automatic retry.
   * This is the main method to use for resilient search execution.
   *
   * @param searchId The search ID returned from startSearchJob
   * @param onProgress Callback for progress updates
   * @param pollInterval Polling interval in ms (default: 2000)
   * @param signal Optional AbortSignal for cancellation
   * @returns Final search result
   */
  async pollSearchJobUntilComplete(
    searchId: string,
    onProgress: (progress: SearchJobProgress) => void,
    pollInterval: number = 2000,
    signal?: AbortSignal
  ): Promise<SearchResult> {
    while (true) {
      // Check if aborted
      if (signal?.aborted) {
        throw new Error('Search cancelled');
      }

      const progress = await this.getSearchJobProgress(searchId);
      onProgress(progress);

      if (progress.status === 'completed' && progress.result) {
        return progress.result;
      }

      if (progress.status === 'failed') {
        if (progress.stage === 'cancelled') {
          throw new Error('Search cancelled');
        }
        throw new Error(progress.error || 'Search failed');
      }

      // Wait before next poll
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(resolve, pollInterval);
        if (signal) {
          const abortHandler = () => {
            clearTimeout(timeout);
            reject(new Error('Search cancelled'));
          };
          signal.addEventListener('abort', abortHandler, { once: true });
        }
      });
    }
  }
}


export const api = new ApiClient();

// React Query Hooks
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export function useJobs(params?: {
  min_score?: number;
  max_score?: number;
  recency_days?: number;
  search?: string;
  sort_by?: 'score' | 'date';
  sort_order?: 'asc' | 'desc';
  limit?: number;
}) {
  return useQuery({
    queryKey: ['jobs', params],
    queryFn: () => api.getJobs(params),
    placeholderData: (previousData) => previousData, // Keep previous data during refetch
  });
}

export function useResumes() {
  return useQuery({
    queryKey: ['resumes'],
    queryFn: () => api.getResumes(),
  });
}

export function useGeminiStatus() {
  return useQuery({
    queryKey: ['gemini-status'],
    queryFn: () => api.getGeminiStatus(),
  });
}

export function useDeleteResume() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (filename: string) => api.deleteResume(filename),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
    },
  });
}

export function useUploadResume() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, name }: { file: File; name: string }) => api.uploadResume(file, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] });
    },
  });
}

export function useSuggestedDomains(filename: string | null) {
  return useQuery({
    queryKey: ['suggested-domains', filename],
    queryFn: () => (filename ? api.getSuggestedDomains(filename) : Promise.resolve(null)),
    enabled: !!filename,
  });
}

export function useAnalyzeResume() {
  return useMutation({
    mutationFn: (params: Parameters<ApiClient['analyzeResume']>[0]) => api.analyzeResume(params),
  });
}

export function useGenerateSuggestions() {
  return useMutation({
    mutationFn: (params: Parameters<ApiClient['generateSuggestions']>[0]) => api.generateSuggestions(params),
  });
}

export function useExportResume() {
  return useMutation({
    mutationFn: (params: Parameters<ApiClient['exportResume']>[0]) => api.exportResume(params),
  });
}

export function useAnalysisHistory(params?: AnalysisHistoryFilters) {
  return useQuery({
    queryKey: ['analysis-history', params],
    queryFn: () => api.getAnalysisHistory(params),
    placeholderData: (previousData) => previousData,
    staleTime: 30 * 1000, // 30 seconds
  });
}

export function useMatchSuggestions(matchId: number | null) {
  return useQuery({
    queryKey: ['match-suggestions', matchId],
    queryFn: () => (matchId ? api.getMatchSuggestions(matchId) : Promise.resolve(null)),
    enabled: matchId !== null,
    staleTime: 5 * 60 * 1000, // 5 minutes - suggestions rarely change
  });
}

export function useSaveLikedBullet() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: SaveLikedBulletParams) => api.saveLikedBullet(params),
    // Optimistic update for instant feedback
    onMutate: async (newBullet) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['liked-bullets'] });

      // Snapshot previous value
      const previousData = queryClient.getQueryData<PaginatedLikedBulletsResponse>(['liked-bullets']);

      // Optimistically update cache
      if (previousData) {
        const optimisticBullet: LikedBullet = {
          id: Date.now(), // Temporary ID
          original_text: newBullet.original_text,
          rewritten_text: newBullet.rewritten_text,
          role_title: newBullet.role_title,
          company: newBullet.company,
          job_id: newBullet.job_id,
          created_at: new Date().toISOString(),
        };

        queryClient.setQueryData<PaginatedLikedBulletsResponse>(['liked-bullets'], {
          ...previousData,
          items: [optimisticBullet, ...previousData.items],
          total: previousData.total + 1,
        });
      }

      return { previousData };
    },
    onError: (_err, _newBullet, context) => {
      // Rollback on error
      if (context?.previousData) {
        queryClient.setQueryData(['liked-bullets'], context.previousData);
      }
    },
    onSettled: () => {
      // Refetch to sync with server
      queryClient.invalidateQueries({ queryKey: ['liked-bullets'] });
    },
  });
}

export function useLikedBullets(params?: {
  skip?: number;
  limit?: number;
  role_filter?: string;
}) {
  return useQuery({
    queryKey: ['liked-bullets', params],
    queryFn: () => api.getLikedBullets(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes (formerly cacheTime)
  });
}

export function useUniqueRoles() {
  return useQuery({
    queryKey: ['unique-roles'],
    queryFn: () => api.getUniqueRoles(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useDeleteLikedBullet() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteLikedBullet(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['liked-bullets'] });
    },
  });
}

export function useSearchDefaults() {
  return useQuery({
    queryKey: ['search-defaults'],
    queryFn: () => api.getSearchDefaults(),
  });
}

export function useSuggestedKeywords() {
  return useQuery({
    queryKey: ['suggested-keywords'],
    queryFn: () => api.getSuggestedKeywords(7),
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });
}

/**
 * Hook for polling search job progress.
 * Automatically polls every 2 seconds until completed or failed.
 */
export function useSearchJobProgress(searchId: string | null, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['search-job', searchId],
    queryFn: () => searchId ? api.getSearchJobProgress(searchId) : null,
    enabled: (options?.enabled ?? true) && !!searchId,
    refetchInterval: (query) => {
      // Stop polling when completed or failed
      const data = query.state.data;
      if (data?.status === 'completed' || data?.status === 'failed') {
        return false;
      }
      return 2000; // Poll every 2 seconds
    },
  });
}

/**
 * Hook for getting recent search jobs (for recovery).
 */
export function useRecentSearchJobs(limit: number = 5) {
  return useQuery({
    queryKey: ['recent-search-jobs', limit],
    queryFn: () => api.getRecentSearchJobs(limit),
    staleTime: 30 * 1000, // 30 seconds
  });
}

/**
 * Hook for Gemini configuration status.
 * Returns config state to show warnings if Gemini is misconfigured.
 */
export function useGeminiConfigStatus() {
  return useQuery({
    queryKey: ['gemini-config-status'],
    queryFn: () => api.getGeminiConfigStatus(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook for Gemini health check.
 * Used to validate API availability before searches.
 */
export function useGeminiHealth(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['gemini-health'],
    queryFn: () => api.checkGeminiHealth(),
    enabled: options?.enabled ?? true,
    staleTime: 30 * 1000, // 30 seconds
  });
}

// Analytics hooks

export function useAnalyticsSummary() {
  return useQuery({
    queryKey: ['analytics-summary'],
    queryFn: () => api.getAnalyticsSummary(),
    staleTime: 5 * 60 * 1000, // 5 minutes (backend caches for 1 hour)
  });
}

export function useAnalyticsSkills(topN: number = 10) {
  return useQuery({
    queryKey: ['analytics-skills', topN],
    queryFn: () => api.getAnalyticsSkills(topN),
    staleTime: 5 * 60 * 1000,
  });
}

export function useAnalyticsMarket(topN: number = 10, minScore: number = 60) {
  return useQuery({
    queryKey: ['analytics-market', topN, minScore],
    queryFn: () => api.getAnalyticsMarket(topN, minScore),
    staleTime: 5 * 60 * 1000,
  });
}

export function useAnalyticsTimeline(days: number = 30) {
  return useQuery({
    queryKey: ['analytics-timeline', days],
    queryFn: () => api.getAnalyticsTimeline(days),
    staleTime: 5 * 60 * 1000,
  });
}

export function useScoreDistribution() {
  return useQuery({
    queryKey: ['score-distribution'],
    queryFn: () => api.getScoreDistribution(),
    staleTime: 5 * 60 * 1000,
  });
}

export function usePerformanceSummary() {
  return useQuery({
    queryKey: ['performance-summary'],
    queryFn: () => api.getPerformanceSummary(),
    staleTime: 5 * 60 * 1000,
  });
}

export function usePerformanceTimeline(days: number = 30) {
  return useQuery({
    queryKey: ['performance-timeline', days],
    queryFn: () => api.getPerformanceTimeline(days),
    staleTime: 5 * 60 * 1000,
  });
}

export function usePerformanceBreakdown(days: number = 7) {
  return useQuery({
    queryKey: ['performance-breakdown', days],
    queryFn: () => api.getPerformanceBreakdown(days),
    staleTime: 5 * 60 * 1000,
  });
}

export function useMatchingDistribution(days: number = 30) {
  return useQuery({
    queryKey: ['matching-distribution', days],
    queryFn: () => api.getMatchingDistribution(days),
    staleTime: 5 * 60 * 1000,
  });
}

export function useGeminiUsage(days: number = 30) {
  return useQuery({
    queryKey: ['gemini-usage', days],
    queryFn: () => api.getGeminiUsage(days),
    staleTime: 5 * 60 * 1000,
  });
}

export function useApiLatency(days: number = 7) {
  return useQuery({
    queryKey: ['api-latency', days],
    queryFn: () => api.getApiLatency(days),
    staleTime: 5 * 60 * 1000,
  });
}

export function useRecentSearches(limit: number = 20) {
  return useQuery({
    queryKey: ['recent-searches', limit],
    queryFn: () => api.getRecentSearches(limit),
    staleTime: 5 * 60 * 1000,
  });
}

// Domain hooks

export function useAvailableDomains() {
  return useQuery({
    queryKey: ['available-domains'],
    queryFn: () => api.getAvailableDomains(),
    staleTime: 60 * 60 * 1000, // 1 hour - domains rarely change
  });
}

export function useUserDomains() {
  return useQuery({
    queryKey: ['user-domains'],
    queryFn: () => api.getUserDomains(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useUpdateUserDomains() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (domains: string[]) => api.updateUserDomains(domains),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-domains'] });
    },
  });
}

// Scheduler hooks

export function useSchedules() {
  return useQuery({
    queryKey: ['schedules'],
    queryFn: () => api.getSchedules(),
    staleTime: 30 * 1000, // 30 seconds - schedules can change frequently
  });
}

export function useSchedule(id: number) {
  return useQuery({
    queryKey: ['schedule', id],
    queryFn: () => api.getSchedule(id),
    enabled: id > 0,
  });
}

export function useCreateSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: ScheduleCreateParams) => api.createSchedule(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedules'] });
      queryClient.invalidateQueries({ queryKey: ['scheduler-status'] });
    },
  });
}

export function useUpdateSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, params }: { id: number; params: ScheduleUpdateParams }) =>
      api.updateSchedule(id, params),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['schedules'] });
      queryClient.invalidateQueries({ queryKey: ['schedule', id] });
      queryClient.invalidateQueries({ queryKey: ['scheduler-status'] });
    },
  });
}

export function useDeleteSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteSchedule(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedules'] });
      queryClient.invalidateQueries({ queryKey: ['scheduler-status'] });
    },
  });
}

export function useToggleSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.toggleSchedule(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['schedules'] });
      queryClient.invalidateQueries({ queryKey: ['schedule', id] });
      queryClient.invalidateQueries({ queryKey: ['scheduler-status'] });
    },
  });
}

export function useRunScheduleNow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.runScheduleNow(id),
    onSuccess: (_, id) => {
      // Refetch schedule to update last_run_at
      queryClient.invalidateQueries({ queryKey: ['schedules'] });
      queryClient.invalidateQueries({ queryKey: ['schedule', id] });
    },
  });
}

export function useSchedulerStatus() {
  return useQuery({
    queryKey: ['scheduler-status'],
    queryFn: () => api.getSchedulerStatus(),
    refetchInterval: 60 * 1000, // Refetch every minute to keep next_run_at updated
    staleTime: 30 * 1000,
  });
}
