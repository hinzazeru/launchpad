import { create } from 'zustand';
import type { SearchProgress, SearchResult, JobSearchParams } from '@/services/api';

interface SearchState {
  // Form params (persisted across navigation)
  formParams: Partial<JobSearchParams>;
  setFormParams: (params: Partial<JobSearchParams>) => void;

  // Search state
  isSearching: boolean;
  progress: SearchProgress | null;
  result: SearchResult | null;
  error: string | null;

  // Actions
  startSearch: () => void;
  updateProgress: (progress: SearchProgress) => void;
  setResult: (result: SearchResult) => void;
  setError: (error: string) => void;
  reset: () => void;

  // AbortController (stored outside React lifecycle)
  abortController: AbortController | null;
  setAbortController: (controller: AbortController | null) => void;
}

export const useSearchStore = create<SearchState>((set) => ({
  formParams: {},
  setFormParams: (params) => set((state) => ({
    formParams: { ...state.formParams, ...params }
  })),

  isSearching: false,
  progress: null,
  result: null,
  error: null,

  startSearch: () => set({ isSearching: true, progress: null, result: null, error: null }),
  updateProgress: (progress) => set({ progress }),
  setResult: (result) => set({ result, isSearching: false }),
  setError: (error) => set({ error, isSearching: false }),
  reset: () => set({ progress: null, result: null, error: null }),

  abortController: null,
  setAbortController: (controller) => set({ abortController: controller }),
}));
