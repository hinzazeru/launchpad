import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { api } from '@/services/api';
import { Download, Loader2, X, Check, FileText, Eye } from 'lucide-react';

export interface BulletSelection {
  original: string;
  selected: string;
  type: 'original' | 'ai' | 'custom';
}

export interface ExportButtonProps {
  resumeFilename: string;
  company: string;
  selections: Record<string, BulletSelection[]>; // roleKey -> selections
  disabled?: boolean;
  onExportComplete?: (filename: string) => void;
}

interface ChangePreview {
  roleKey: string;
  changes: Array<{
    original: string;
    selected: string;
    type: 'original' | 'ai' | 'custom';
  }>;
}

export function ExportButton({
  resumeFilename,
  company,
  selections,
  disabled = false,
  onExportComplete,
}: ExportButtonProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [exportResult, setExportResult] = useState<{ filename: string; changesMade: number } | null>(null);

  // Calculate changes
  const changes: ChangePreview[] = Object.entries(selections)
    .map(([roleKey, bulletSelections]) => ({
      roleKey,
      changes: bulletSelections.filter(s => s.type !== 'original'),
    }))
    .filter(c => c.changes.length > 0);

  const totalChanges = changes.reduce((sum, c) => sum + c.changes.length, 0);

  const handleExport = async () => {
    setIsExporting(true);
    setExportResult(null);

    try {
      // Format selections for API
      const formattedSelections: Record<string, Array<{ original: string; selected: string; type: string }>> = {};

      Object.entries(selections).forEach(([roleKey, bulletSelections]) => {
        formattedSelections[roleKey] = bulletSelections.map(s => ({
          original: s.original,
          selected: s.selected,
          type: s.type,
        }));
      });

      const result = await api.exportResume({
        resume_filename: resumeFilename,
        selections: formattedSelections,
        company,
      });

      if (result.success) {
        setExportResult({
          filename: result.filename,
          changesMade: result.changes_made,
        });

        // Trigger download
        const downloadUrl = api.getDownloadUrl(result.filename);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = result.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        onExportComplete?.(result.filename);
      }
    } catch (error) {
      console.error('Export failed:', error);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <>
      {/* Export Button with Change Count */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-3">
        <Button
          onClick={() => setShowPreview(true)}
          disabled={disabled || isExporting}
          variant="outline"
          className="gap-2 w-full sm:w-auto"
        >
          <Eye className="h-4 w-4" />
          Preview Changes
          {totalChanges > 0 && (
            <Badge variant="default" className="ml-1">{totalChanges}</Badge>
          )}
        </Button>

        <Button
          onClick={handleExport}
          disabled={disabled || isExporting}
          className="gap-2 w-full sm:w-auto"
        >
          {isExporting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Exporting...
            </>
          ) : (
            <>
              <Download className="h-4 w-4" />
              Export Resume
            </>
          )}
        </Button>
      </div>

      {/* Success Message */}
      {exportResult && (
        <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg flex items-center gap-3">
          <Check className="h-5 w-5 text-green-600" />
          <div className="flex-1">
            <p className="text-sm font-medium text-green-800">Export Successful</p>
            <p className="text-xs text-green-600">
              {exportResult.filename} • {exportResult.changesMade} changes applied
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              const downloadUrl = api.getDownloadUrl(exportResult.filename);
              window.open(downloadUrl, '_blank');
            }}
          >
            <Download className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Preview Modal */}
      <AnimatePresence>
        {showPreview && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/50 z-40"
              onClick={() => setShowPreview(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 flex items-center justify-center p-2 sm:p-4 z-50 pointer-events-none"
            >
              <Card className="w-full max-w-2xl max-h-[90vh] sm:max-h-[80vh] overflow-hidden flex flex-col pointer-events-auto">
            <CardHeader className="flex-row items-center justify-between border-b shrink-0">
              <div>
                <CardTitle>Export Preview</CardTitle>
                <CardDescription>
                  {totalChanges} bullet{totalChanges !== 1 ? 's' : ''} will be modified
                </CardDescription>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setShowPreview(false)}>
                <X className="h-5 w-5" />
              </Button>
            </CardHeader>

            <CardContent className="p-6 overflow-y-auto flex-1">
              {totalChanges === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p className="font-medium">No Changes</p>
                  <p className="text-sm mt-1">All bullets are using their original text</p>
                </div>
              ) : (
                <div className="space-y-6">
                  {changes.map(({ roleKey, changes: roleChanges }) => (
                    <div key={roleKey}>
                      <h4 className="font-medium text-gray-900 mb-3">
                        {roleKey.replace('_', ' @ ')}
                      </h4>
                      <div className="space-y-3">
                        {roleChanges.map((change, i) => (
                          <div key={i} className="border border-gray-200 rounded-lg overflow-hidden">
                            {/* Original */}
                            <div className="p-3 bg-red-50 border-b border-gray-200">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs font-medium text-red-600 uppercase">Original</span>
                              </div>
                              <p className="text-sm text-red-800 line-through">{change.original}</p>
                            </div>
                            {/* New */}
                            <div className="p-3 bg-green-50">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs font-medium text-green-600 uppercase">
                                  {change.type === 'ai' ? 'AI Suggestion' : 'Custom'}
                                </span>
                                <Badge variant={change.type === 'ai' ? 'default' : 'secondary'} className="text-xs">
                                  {change.type.toUpperCase()}
                                </Badge>
                              </div>
                              <p className="text-sm text-green-800">{change.selected}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>

            <div className="border-t p-3 sm:p-4 flex flex-col sm:flex-row justify-end gap-2 sm:gap-3 shrink-0">
              <Button variant="outline" onClick={() => setShowPreview(false)} className="w-full sm:w-auto">
                Cancel
              </Button>
              <Button onClick={() => { setShowPreview(false); handleExport(); }} disabled={isExporting} className="w-full sm:w-auto">
                {isExporting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Exporting...
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4 mr-2" />
                    Export Resume
                  </>
                )}
              </Button>
            </div>
          </Card>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
