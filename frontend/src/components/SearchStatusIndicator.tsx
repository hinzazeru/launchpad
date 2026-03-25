import { useRef, useEffect } from 'react';
import { useSearchStore } from '@/stores/searchStore';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Loader2 } from 'lucide-react';
import { useToastActions } from '@/components/ui/toast';

export function SearchStatusIndicator() {
  const { isSearching, progress, result } = useSearchStore();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToastActions();
  const wasSearchingRef = useRef(false);

  // Show completion toast on non-GetJobs pages when search finishes
  useEffect(() => {
    if (isSearching) {
      wasSearchingRef.current = true;
    }

    if (wasSearchingRef.current && !isSearching && result && location.pathname !== '/') {
      toast.success(
        'Search Complete',
        `Found ${result.high_matches} high-quality matches`,
        {
          onClick: () => navigate('/'),
          actionLabel: 'View Results',
          duration: 8000,
        }
      );
      wasSearchingRef.current = false;
    }

    if (wasSearchingRef.current && !isSearching && !result) {
      wasSearchingRef.current = false;
    }
  }, [isSearching, result, location.pathname, navigate, toast]);

  // Don't show on GetJobs page (redundant) or when not searching
  if (location.pathname === '/' || !isSearching) {
    return null;
  }

  return (
    <AnimatePresence>
      {isSearching && (
        <motion.button
          initial={{ opacity: 0, y: 20, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.9 }}
          transition={{ type: 'spring', stiffness: 300, damping: 25 }}
          onClick={() => navigate('/')}
          className="fixed bottom-6 right-6 bg-primary text-primary-foreground
                     px-4 py-3 rounded-full shadow-lg flex items-center gap-3
                     hover:bg-primary/90 transition-colors z-50 cursor-pointer"
          title="Click to view search progress"
        >
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="font-medium text-sm">
            Searching: {progress?.progress ?? 0}%
          </span>
        </motion.button>
      )}
    </AnimatePresence>
  );
}
