import { useState, useEffect, createContext, useContext, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, CheckCircle, AlertCircle, AlertTriangle, Info, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ReactNode } from 'react';

type ToastType = 'success' | 'error' | 'warning' | 'info';

interface Toast {
  id: string;
  type: ToastType;
  title: string;
  description?: string;
  duration?: number;
  onClick?: () => void;
  actionLabel?: string;
}

interface ToastActionOptions {
  onClick?: () => void;
  actionLabel?: string;
  duration?: number;
}

interface ToastContextType {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}

// Convenience methods
export function useToastActions() {
  const { addToast } = useToast();

  return {
    success: (title: string, description?: string, options?: ToastActionOptions) =>
      addToast({ type: 'success', title, description, ...options }),
    error: (title: string, description?: string, options?: ToastActionOptions) =>
      addToast({ type: 'error', title, description, duration: 6000, ...options }),
    warning: (title: string, description?: string, options?: ToastActionOptions) =>
      addToast({ type: 'warning', title, description, ...options }),
    info: (title: string, description?: string, options?: ToastActionOptions) =>
      addToast({ type: 'info', title, description, ...options }),
  };
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { ...toast, id }]);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </ToastContext.Provider>
  );
}

function ToastContainer({
  toasts,
  removeToast,
}: {
  toasts: Toast[];
  removeToast: (id: string) => void;
}) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onClose={() => removeToast(toast.id)} />
        ))}
      </AnimatePresence>
    </div>
  );
}

function ToastItem({ toast, onClose }: { toast: Toast; onClose: () => void }) {
  const { type, title, description, duration = 4000, onClick, actionLabel } = toast;
  const isClickable = !!onClick;

  useEffect(() => {
    const timer = setTimeout(onClose, duration);
    return () => clearTimeout(timer);
  }, [duration, onClose]);

  const handleClick = () => {
    if (onClick) {
      onClick();
      onClose();
    }
  };

  const handleCloseClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onClose();
  };

  const icons = {
    success: CheckCircle,
    error: AlertCircle,
    warning: AlertTriangle,
    info: Info,
  };

  const colors = {
    success: 'bg-green-50 border-green-200 text-green-800',
    error: 'bg-red-50 border-red-200 text-red-800',
    warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
    info: 'bg-blue-50 border-blue-200 text-blue-800',
  };

  const iconColors = {
    success: 'text-green-500',
    error: 'text-red-500',
    warning: 'text-yellow-500',
    info: 'text-blue-500',
  };

  const Icon = icons[type];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, x: 100, scale: 0.95 }}
      transition={{ duration: 0.2 }}
      onClick={isClickable ? handleClick : undefined}
      role={isClickable ? 'button' : undefined}
      tabIndex={isClickable ? 0 : undefined}
      className={cn(
        'pointer-events-auto rounded-lg border p-4 shadow-lg flex items-start gap-3',
        colors[type],
        isClickable && 'cursor-pointer hover:brightness-95 transition-all'
      )}
    >
      <Icon className={cn('h-5 w-5 shrink-0 mt-0.5', iconColors[type])} />
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm">{title}</p>
        {description && (
          <p className="mt-1 text-sm opacity-80">{description}</p>
        )}
        {isClickable && actionLabel && (
          <p className="mt-1.5 text-xs font-medium flex items-center gap-1 opacity-70">
            {actionLabel}
            <ChevronRight className="h-3 w-3" />
          </p>
        )}
      </div>
      <button
        onClick={handleCloseClick}
        className="shrink-0 rounded p-1 hover:bg-black/5 transition-colors"
      >
        <X className="h-4 w-4" />
      </button>
    </motion.div>
  );
}
