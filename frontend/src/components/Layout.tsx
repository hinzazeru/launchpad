import { Link, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Target, FolderOpen, Search, Briefcase, BarChart2, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ModeToggle } from '@/components/mode-toggle';

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation();

  const navItems = [
    { path: '/',          label: 'Get Jobs',       shortLabel: 'Jobs',      icon: Search    },
    { path: '/matches',   label: 'Matches',        shortLabel: 'Matches',   icon: Briefcase },
    { path: '/analyze',   label: 'Analyze',        shortLabel: 'Analyze',   icon: Target    },
    { path: '/analytics', label: 'Analytics',      shortLabel: 'Analytics', icon: BarChart2 },
    { path: '/library',   label: 'Resume Library', shortLabel: 'Library',   icon: FolderOpen },
    { path: '/settings',  label: 'Settings',       shortLabel: 'Settings',  icon: Settings  },
  ];

  return (
    <div className="min-h-screen bg-background flex flex-col transition-colors duration-300">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14 sm:h-16">
            {/* Logo */}
            <Link to="/" className="flex items-center gap-2">
              <span className="font-bold text-lg sm:text-xl text-foreground">LaunchPad 💸</span>
            </Link>

            {/* Desktop Navigation */}
            <div className="hidden sm:flex items-center gap-4">
              <nav className="flex items-center gap-1">
                {navItems.map(({ path, label, icon: Icon }) => (
                  <Link
                    key={path}
                    to={path}
                    className={cn(
                      'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                      location.pathname === path
                        ? 'bg-primary/10 text-primary'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {label}
                  </Link>
                ))}
              </nav>
              <ModeToggle />
            </div>

            {/* Mobile: theme toggle only — nav lives at the bottom */}
            <div className="sm:hidden">
              <ModeToggle />
            </div>
          </div>
        </div>
      </header>

      {/* Main Content — extra bottom padding on mobile clears the fixed bottom nav */}
      <main className="max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 pt-4 sm:pt-8 pb-24 sm:pb-8 flex-1">
        {children}
      </main>

      {/* Footer — desktop only */}
      <footer className="hidden sm:block border-t border-border mt-auto bg-card/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-center text-xs sm:text-sm text-muted-foreground">
            LaunchPad 💸 — Optimize your resume for any job
          </p>
        </div>
      </footer>

      {/* Bottom Navigation — mobile only */}
      <nav
        className="sm:hidden fixed bottom-0 left-0 right-0 z-50 border-t border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      >
        <div className="flex">
          {navItems.map(({ path, shortLabel, icon: Icon }) => {
            const isActive = location.pathname === path;
            return (
              <Link
                key={path}
                to={path}
                className={cn(
                  'flex-1 flex flex-col items-center justify-center gap-0.5 py-2 min-h-[52px] relative transition-colors',
                  isActive ? 'text-primary' : 'text-muted-foreground'
                )}
              >
                {isActive && (
                  <motion.div
                    layoutId="bottom-nav-indicator"
                    className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-0.5 rounded-full bg-primary"
                    transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                  />
                )}
                <Icon className="h-5 w-5" />
                <span className="text-[9px] font-medium leading-tight">{shortLabel}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
