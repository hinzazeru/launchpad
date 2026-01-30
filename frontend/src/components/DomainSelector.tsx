import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, X, Building2, Cpu, Layers } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { DomainInfo } from '@/services/api';

interface DomainCategory {
  key: string;
  name: string;
  icon: React.ReactNode;
  domains: DomainInfo[];
}

interface DomainSelectorProps {
  categories: {
    industries: DomainInfo[];
    platforms: DomainInfo[];
    technologies: DomainInfo[];
  };
  selectedDomains: string[];
  onChange: (domains: string[]) => void;
  disabled?: boolean;
}

export function DomainSelector({
  categories,
  selectedDomains,
  onChange,
  disabled = false,
}: DomainSelectorProps) {
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set(['industries']) // Industries expanded by default
  );

  const categoryConfig: DomainCategory[] = [
    {
      key: 'industries',
      name: 'Industries',
      icon: <Building2 className="w-4 h-4" />,
      domains: categories.industries || [],
    },
    {
      key: 'platforms',
      name: 'Platforms',
      icon: <Layers className="w-4 h-4" />,
      domains: categories.platforms || [],
    },
    {
      key: 'technologies',
      name: 'Technologies',
      icon: <Cpu className="w-4 h-4" />,
      domains: categories.technologies || [],
    },
  ];

  const toggleCategory = (key: string) => {
    const newExpanded = new Set(expandedCategories);
    if (newExpanded.has(key)) {
      newExpanded.delete(key);
    } else {
      newExpanded.add(key);
    }
    setExpandedCategories(newExpanded);
  };

  const toggleDomain = (domainKey: string) => {
    if (disabled) return;

    if (selectedDomains.includes(domainKey)) {
      onChange(selectedDomains.filter((d) => d !== domainKey));
    } else {
      onChange([...selectedDomains, domainKey]);
    }
  };

  const removeDomain = (domainKey: string) => {
    if (disabled) return;
    onChange(selectedDomains.filter((d) => d !== domainKey));
  };

  // Find domain info by key
  const getDomainName = (key: string): string => {
    for (const category of categoryConfig) {
      const domain = category.domains.find((d) => d.key === key);
      if (domain) return domain.name;
    }
    return key;
  };

  return (
    <div className="space-y-4">
      {/* Selected domains as tags */}
      {selectedDomains.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Your Domains ({selectedDomains.length})
          </p>
          <div className="flex flex-wrap gap-2">
            <AnimatePresence mode="popLayout">
              {selectedDomains.map((domainKey) => (
                <motion.button
                  key={domainKey}
                  layout
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  transition={{ duration: 0.15 }}
                  onClick={() => removeDomain(domainKey)}
                  disabled={disabled}
                  className={cn(
                    'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                    'bg-primary/10 text-primary border border-primary/20',
                    !disabled && 'hover:bg-primary/20 hover:border-primary/30',
                    disabled && 'opacity-50 cursor-not-allowed'
                  )}
                >
                  {getDomainName(domainKey)}
                  <X className="w-3.5 h-3.5" />
                </motion.button>
              ))}
            </AnimatePresence>
          </div>
        </div>
      )}

      {/* Category sections */}
      <div className="space-y-2">
        {categoryConfig.map((category) => {
          const isExpanded = expandedCategories.has(category.key);
          const selectedInCategory = category.domains.filter((d) =>
            selectedDomains.includes(d.key)
          ).length;

          return (
            <div
              key={category.key}
              className="border border-border/50 rounded-lg overflow-hidden"
            >
              {/* Category header */}
              <button
                onClick={() => toggleCategory(category.key)}
                className="w-full flex items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">{category.icon}</span>
                  <span className="font-medium">{category.name}</span>
                  <span className="text-xs text-muted-foreground">
                    ({category.domains.length})
                  </span>
                  {selectedInCategory > 0 && (
                    <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full">
                      {selectedInCategory} selected
                    </span>
                  )}
                </div>
                <motion.div
                  animate={{ rotate: isExpanded ? 180 : 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                </motion.div>
              </button>

              {/* Domain checkboxes */}
              <AnimatePresence initial={false}>
                {isExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                      {category.domains.map((domain) => {
                        const isSelected = selectedDomains.includes(domain.key);

                        return (
                          <label
                            key={domain.key}
                            className={cn(
                              'flex items-start gap-3 p-2 rounded-lg cursor-pointer transition-colors',
                              isSelected
                                ? 'bg-primary/5 border border-primary/20'
                                : 'hover:bg-muted/50 border border-transparent',
                              disabled && 'opacity-50 cursor-not-allowed'
                            )}
                          >
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => toggleDomain(domain.key)}
                              disabled={disabled}
                              className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary disabled:cursor-not-allowed"
                            />
                            <div className="flex-1 min-w-0">
                              <p
                                className={cn(
                                  'text-sm font-medium',
                                  isSelected && 'text-primary'
                                )}
                              >
                                {domain.name}
                              </p>
                              {domain.description && (
                                <p className="text-xs text-muted-foreground truncate">
                                  {domain.description}
                                </p>
                              )}
                            </div>
                          </label>
                        );
                      })}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </div>
  );
}
