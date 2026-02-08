import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { SearchProgress, SearchResult, JobSearchParams, SearchJobProgress } from '@/services/api';

interface SearchState {
  // Form params (persisted across navigation)
  formParams: Partial<JobSearchParams>;
  setFormParams: (params: Partial<JobSearchParams>) => void;

  // Active search tracking (persisted for recovery after disconnection)
  activeSearchId: string | null;

  // Search state
  isSearching: boolean;
  progress: SearchProgress | null;
  result: SearchResult | null;
  error: string | null;

  // Actions
  startSearch: (searchId: string) => void;
  updateProgress: (progress: SearchProgress) => void;
  updateFromJobProgress: (jobProgress: SearchJobProgress) => void;
  setResult: (result: SearchResult) => void;
  setError: (error: string) => void;
  reset: () => void;
  clearActiveSearch: () => void;

  // AbortController (stored outside React lifecycle)
  abortController: AbortController | null;
  setAbortController: (controller: AbortController | null) => void;
}

export const useSearchStore = create<SearchState>()(
  persist(
    (set) => ({
      formParams: {},
      setFormParams: (params) => set((state) => ({
        formParams: { ...state.formParams, ...params }
      })),

      activeSearchId: null,

      isSearching: false,
      progress: null,
      result: null,
      error: null,

      startSearch: (searchId: string) => set({
        activeSearchId: searchId,
        isSearching: true,
        progress: null,
        result: null,
        error: null
      }),

      updateProgress: (progress) => set({ progress }),

      // Update state from background job progress polling
      updateFromJobProgress: (jobProgress: SearchJobProgress) => set({
        progress: {
          stage: jobProgress.stage,
          progress: jobProgress.progress,
          message: jobProgress.message || '',
          jobs_found: jobProgress.jobs_found,
          jobs_imported: jobProgress.jobs_imported,
          matches_found: jobProgress.matches_found,
          high_matches: jobProgress.high_matches,
          exported_count: jobProgress.exported_count,
        },
        isSearching: jobProgress.status === 'pending' || jobProgress.status === 'running',
        result: jobProgress.result || null,
        error: jobProgress.error || null,
        // Clear activeSearchId when completed or failed
        activeSearchId: (jobProgress.status === 'completed' || jobProgress.status === 'failed')
          ? null
          : jobProgress.search_id,
      }),

      setResult: (result) => set({
        result,
        isSearching: false,
        activeSearchId: null  // Clear after completion
      }),

      setError: (error) => set({
        error,
        isSearching: false,
        activeSearchId: null  // Clear after error
      }),

      reset: () => set({
        progress: null,
        result: null,
        error: null,
        // Don't clear activeSearchId - allow recovery
      }),

      clearActiveSearch: () => set({
        activeSearchId: null,
        isSearching: false,
        progress: null,
      }),

      abortController: null,
      setAbortController: (controller) => set({ abortController: controller }),
    }),
    {
      name: 'search-store',
      partialize: (state) => ({
        formParams: state.formParams,
        activeSearchId: state.activeSearchId,  // Persist for recovery
      }),
    }
  )
);
