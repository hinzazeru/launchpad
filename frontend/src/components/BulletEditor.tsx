import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ChevronDown, ChevronUp, Edit3, Check, Heart } from 'lucide-react';

export interface BulletOption {
  id: string;
  label: string;
  text: string;
  type: 'original' | 'ai' | 'custom';
}

export interface BulletEditorProps {
  original: string;
  score: number;
  matchedKeywords?: string[];
  missingKeywords?: string[];
  aiSuggestions?: string[];
  analysis?: string;
  selectedOption: string;
  onSelect: (optionId: string, text: string, type: 'original' | 'ai' | 'custom') => void;
}

export function BulletEditor({
  original,
  aiSuggestions = [],
  analysis,
  selectedOption,
  onSelect,
  onLike,
}: BulletEditorProps & { onLike?: (text: string) => void }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [likedOptions, setLikedOptions] = useState<Set<string>>(new Set());
  const [customText, setCustomText] = useState('');
  const [isEditingCustom, setIsEditingCustom] = useState(false);

  // Build options list
  const options: BulletOption[] = [
    { id: 'original', label: 'Keep Original', text: original, type: 'original' },
    ...aiSuggestions.map((suggestion, index) => ({
      id: `ai-${index}`,
      label: `AI Option ${index + 1}`,
      text: suggestion,
      type: 'ai' as const,
    })),
  ];

  const handleCustomSave = () => {
    if (customText.trim()) {
      onSelect('custom', customText.trim(), 'custom');
      setIsEditingCustom(false);
    }
  };

  const handleLike = (e: React.MouseEvent, optionId: string, text: string) => {
    e.preventDefault();
    e.stopPropagation();

    if (likedOptions.has(optionId)) return;

    setLikedOptions(prev => {
      const next = new Set(prev);
      next.add(optionId);
      return next;
    });

    onLike?.(text);
  };

  const selectedText = selectedOption === 'custom'
    ? customText
    : options.find(o => o.id === selectedOption)?.text || original;

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      {/* Header - Always visible */}
      <button
        className="w-full p-4 flex items-start justify-between gap-4 hover:bg-muted/50 text-left transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <p className="flex-1 min-w-0 text-sm text-foreground line-clamp-2">{selectedText}</p>

        <div className="flex items-center gap-2 shrink-0">
          {selectedOption !== 'original' && (
            <Badge variant="default" className="text-xs">Modified</Badge>
          )}
          {isExpanded ? (
            <ChevronUp className="h-5 w-5 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-5 w-5 text-muted-foreground" />
          )}
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t border-border p-4 space-y-4 bg-muted/30">
          {/* AI Analysis */}
          {analysis && (
            <div className="p-3 bg-primary/10 rounded-lg border border-primary/20">
              <p className="text-xs font-medium text-primary mb-1">AI Analysis</p>
              <p className="text-sm text-primary/90">{analysis}</p>
            </div>
          )}

          {/* Options */}
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Select Version
            </p>

            {options.map((option) => (
              <label
                key={option.id}
                className={cn(
                  'flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all group',
                  option.type === 'ai'
                    ? selectedOption === option.id
                      ? 'border-violet-500/60 bg-violet-500/10 shadow-[inset_0_0_0_1px_rgba(139,92,246,0.15)]'
                      : 'border-violet-500/20 bg-violet-500/[0.04] hover:border-violet-500/40 hover:bg-violet-500/[0.08]'
                    : selectedOption === option.id
                      ? 'border-primary bg-primary/10'
                      : 'border-border bg-card hover:border-muted-foreground/50'
                )}
              >
                <input
                  type="radio"
                  name={`bullet-option-${original.substring(0, 10)}`}
                  checked={selectedOption === option.id}
                  onChange={() => onSelect(option.id, option.text, option.type)}
                  className="mt-1 h-4 w-4 text-primary focus:ring-primary"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-foreground">{option.label}</span>
                      {option.type === 'ai' && (
                        <Badge variant="default" className="text-xs bg-violet-500/20 text-violet-400 border-violet-500/30 hover:bg-violet-500/20">AI</Badge>
                      )}
                    </div>

                    {/* Like Button for AI Options */}
                    {option.type === 'ai' && onLike && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className={cn(
                          "h-6 w-6 opacity-40 hover:opacity-100 hover:scale-110 transition-all",
                          likedOptions.has(option.id) && "opacity-100 text-red-500 hover:text-red-600"
                        )}
                        onClick={(e) => handleLike(e, option.id, option.text)}
                        title="Save this suggestion to your collection"
                      >
                        <Heart className={cn("h-4 w-4", likedOptions.has(option.id) && "fill-current")} />
                      </Button>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">{option.text}</p>
                </div>
                {selectedOption === option.id && (
                  <Check className="h-5 w-5 text-primary shrink-0" />
                )}
              </label>
            ))}

            {/* Custom Option */}
            <div
              className={cn(
                'p-3 rounded-lg border transition-colors',
                selectedOption === 'custom'
                  ? 'border-primary bg-primary/10'
                  : 'border-border bg-card'
              )}
            >
              <div className="flex items-center gap-3">
                <input
                  type="radio"
                  name="bullet-option"
                  checked={selectedOption === 'custom'}
                  onChange={() => {
                    if (customText.trim()) {
                      onSelect('custom', customText.trim(), 'custom');
                    } else {
                      setIsEditingCustom(true);
                    }
                  }}
                  className="h-4 w-4 text-primary focus:ring-primary"
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-foreground">Custom Edit</span>
                    <Edit3 className="h-4 w-4 text-muted-foreground" />
                  </div>
                </div>
                {!isEditingCustom && customText && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.preventDefault();
                      setIsEditingCustom(true);
                    }}
                  >
                    Edit
                  </Button>
                )}
              </div>

              {(isEditingCustom || (selectedOption === 'custom' && !customText)) && (
                <div className="mt-3 space-y-2">
                  <textarea
                    value={customText}
                    onChange={(e) => setCustomText(e.target.value)}
                    placeholder="Enter your custom bullet point..."
                    className="w-full p-2 text-sm border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent bg-background text-foreground"
                    rows={3}
                  />
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setIsEditingCustom(false);
                        if (!customText.trim() && selectedOption === 'custom') {
                          onSelect('original', original, 'original');
                        }
                      }}
                    >
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      onClick={handleCustomSave}
                      disabled={!customText.trim()}
                    >
                      Save
                    </Button>
                  </div>
                </div>
              )}

              {selectedOption === 'custom' && customText && !isEditingCustom && (
                <p className="mt-2 text-sm text-muted-foreground">{customText}</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
