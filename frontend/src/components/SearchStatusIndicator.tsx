import { useSearchStore } from '@/stores/searchStore';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Loader2 } from 'lucide-react';

export function SearchStatusIndicator() {
  const { isSearching, progress } = useSearchStore();
  const navigate = useNavigate();
  const location = useLocation();

  // Don't show on GetJobs page (redundant) or when not searching
  if (location.pathname === '/get-jobs' || !isSearching) {
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
          onClick={() => navigate('/get-jobs')}
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
