import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api, useResumes, useUploadResume, useDeleteResume } from '@/services/api';
import type { ResumeMetadata, ResumePreview } from '@/services/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ResumeCardSkeleton } from '@/components/ui/skeleton';
import { PageTransition, ExpandableSection } from '@/components/AnimatedComponents';
import { useToastActions } from '@/components/ui/toast';
import {
  Upload,
  Trash2,
  Eye,
  Loader2,
  FileText,
  FileJson,
  X,
  ChevronDown,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SavedBullets } from './SavedBullets';

function ResumeCard({
  resume,
  onPreview,
  onDelete,
  isDeleting,
  index = 0,
}: {
  resume: ResumeMetadata;
  onPreview: () => void;
  onDelete: () => void;
  isDeleting: boolean;
  index?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -10 }}
      transition={{ duration: 0.2, delay: index * 0.05 }}
      whileHover={{ scale: 1.01 }}
    >
      <Card className="hover:shadow-md transition-shadow">
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <motion.div
                className="p-2 bg-muted rounded-lg shrink-0"
                whileHover={{ rotate: 5 }}
              >
                {resume.format === 'json' ? (
                  <FileJson className="h-5 w-5 text-blue-500" />
                ) : (
                  <FileText className="h-5 w-5 text-muted-foreground" />
                )}
              </motion.div>
              <div className="min-w-0 flex-1">
                <h3 className="font-medium text-foreground truncate">{resume.name}</h3>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="secondary" className="text-xs">
                    {resume.format}
                  </Badge>
                  {resume.saved_at && (
                    <span className="text-xs text-muted-foreground">
                      {new Date(resume.saved_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Button variant="ghost" size="icon" onClick={onPreview}>
                <Eye className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={onDelete}
                disabled={isDeleting}
                className="text-red-500 hover:text-red-700 hover:bg-red-50"
              >
                {isDeleting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

function ResumePreviewModal({
  preview,
  filename,
  onClose,
}: {
  preview: ResumePreview;
  filename: string;
  onClose: () => void;
}) {
  const [expandedRoles, setExpandedRoles] = useState<Set<number>>(new Set([0]));

  const toggleRole = (index: number) => {
    setExpandedRoles(prev => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  return (
    <>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        transition={{ duration: 0.2 }}
        className="fixed inset-0 flex items-center justify-center p-4 z-50 pointer-events-none"
      >
        <Card className="w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col pointer-events-auto">
          <CardHeader className="flex-row items-center justify-between border-b shrink-0">
            <div>
              <CardTitle>Resume Preview</CardTitle>
              <CardDescription>{filename}</CardDescription>
            </div>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-5 w-5" />
            </Button>
          </CardHeader>
          <CardContent className="p-6 overflow-y-auto flex-1">
            {/* Summary */}
            {preview.summary && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-6"
              >
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  Summary
                </h3>
                <p className="text-gray-700">{preview.summary}</p>
              </motion.div>
            )}

            {/* Skills */}
            {Object.keys(preview.skills).length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.05 }}
                className="mb-6"
              >
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
                  Skills
                </h3>
                <div className="space-y-2">
                  {Object.entries(preview.skills).map(([category, skills]) => (
                    <div key={category}>
                      <span className="text-sm font-medium text-gray-600">{category}: </span>
                      <span className="text-sm text-gray-700">{skills.join(', ')}</span>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Experience */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="mb-6"
            >
              <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
                Experience
              </h3>
              <div className="space-y-3">
                {preview.roles.map((role, index) => (
                  <div key={index} className="border border-gray-200 rounded-lg overflow-hidden">
                    <button
                      className="w-full p-4 flex items-center justify-between text-left hover:bg-muted/50 transition-colors"
                      onClick={() => toggleRole(index)}
                    >
                      <div>
                        <p className="font-medium text-gray-900">{role.title}</p>
                        <p className="text-sm text-gray-500">
                          {role.company} • {role.duration}
                        </p>
                      </div>
                      <motion.div
                        animate={{ rotate: expandedRoles.has(index) ? 180 : 0 }}
                        transition={{ duration: 0.2 }}
                      >
                        <ChevronDown className="h-5 w-5 text-gray-400" />
                      </motion.div>
                    </button>
                    <ExpandableSection isExpanded={expandedRoles.has(index)}>
                      <div className="p-4 pt-0 border-t border-gray-100">
                        <ul className="space-y-2">
                          {role.bullets.map((bullet, bi) => (
                            <li key={bi} className="text-sm text-gray-700 flex gap-2">
                              <span className="text-gray-400 shrink-0">•</span>
                              <span>{bullet}</span>
                            </li>
                          ))}
                        </ul>
                        {role.technologies.length > 0 && (
                          <div className="mt-3 flex flex-wrap gap-1">
                            {role.technologies.map((tech, ti) => (
                              <Badge key={ti} variant="secondary" className="text-xs">
                                {tech}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>
                    </ExpandableSection>
                  </div>
                ))}
              </div>
            </motion.div>

            {/* Education */}
            {preview.education && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15 }}
              >
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  Education
                </h3>
                <p className="text-gray-700">{preview.education}</p>
              </motion.div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </>
  );
}


export function Library() {
  const toast = useToastActions();

  // React Query Hooks
  const { data, isLoading } = useResumes();
  const resumes = data?.resumes || [];

  const uploadMutation = useUploadResume();
  const deleteMutation = useDeleteResume();

  const [previewResume, setPreviewResume] = useState<{
    filename: string;
    preview: ResumePreview;
  } | null>(null);
  const [uploadName, setUploadName] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [deletingResume, setDeletingResume] = useState<string | null>(null);

  // No useEffect loadResumes anymore

  async function handleUpload() {
    if (!selectedFile || !uploadName.trim()) return;

    try {
      await uploadMutation.mutateAsync({ file: selectedFile, name: uploadName.trim() });
      setSelectedFile(null);
      setUploadName('');
      toast.success('Resume uploaded', `"${uploadName.trim()}" has been added to your library.`);
    } catch (error) {
      console.error('Upload failed:', error);
      toast.error('Upload failed', 'Please check your file and try again.');
    }
  }

  async function handleDelete(filename: string) {
    if (!confirm('Are you sure you want to delete this resume?')) return;

    setDeletingResume(filename);
    try {
      await deleteMutation.mutateAsync(filename);
      toast.success('Resume deleted', 'The resume has been removed from your library.');
    } catch (error) {
      console.error('Delete failed:', error);
      toast.error('Delete failed', 'Please try again.');
    } finally {
      setDeletingResume(null);
    }
  }

  async function handlePreview(filename: string) {
    try {
      const preview = await api.getResumePreview(filename);
      setPreviewResume({ filename, preview });
    } catch (error) {
      console.error('Preview failed:', error);
      toast.error('Failed to load preview', 'Please try again.');
    }
  }

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      const ext = file.name.split('.').pop()?.toLowerCase();
      if (['txt', 'md', 'json'].includes(ext || '')) {
        setSelectedFile(file);
        if (!uploadName) {
          setUploadName(file.name.replace(/\.[^/.]+$/, ''));
        }
      }
    }
  }, [uploadName]);

  if (isLoading) {
    return (
      <PageTransition>
        <div className="space-y-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Resume Library</h1>
            <p className="text-gray-500 mt-1">Manage your saved resumes</p>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1">
              <Card>
                <CardHeader>
                  <CardTitle>Upload Resume</CardTitle>
                  <CardDescription>Add a new resume to your library</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-32 border-2 border-dashed border-muted rounded-lg animate-pulse bg-muted/50" />
                </CardContent>
              </Card>
            </div>
            <div className="lg:col-span-2 space-y-3">
              {[1, 2, 3].map((i) => (
                <ResumeCardSkeleton key={i} />
              ))}
            </div>
          </div>
        </div>
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      <div className="space-y-6">
        {/* Page Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Library</h1>
          <p className="text-gray-500 mt-1">Manage resumes and saved AI content</p>
        </div>

        <Tabs defaultValue="resumes" className="w-full">
          <TabsList className="mb-6">
            <TabsTrigger value="resumes" className="flex items-center gap-2">
              <FileText className="w-4 h-4" /> Resumes
            </TabsTrigger>
            <TabsTrigger value="saved-bullets" className="flex items-center gap-2">
              <Sparkles className="w-4 h-4" /> Saved Bullets
            </TabsTrigger>
          </TabsList>

          <TabsContent value="resumes" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Upload Section */}
              <div className="lg:col-span-1">
                <Card>
                  <CardHeader>
                    <CardTitle>Upload Resume</CardTitle>
                    <CardDescription>Add a new resume to your library</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* Drag and Drop Zone */}
                    <div
                      className={cn(
                        'border-2 border-dashed rounded-lg p-6 text-center transition-colors',
                        dragActive
                          ? 'border-primary bg-primary/10'
                          : 'border-border hover:border-muted-foreground/50'
                      )}
                      onDragEnter={handleDrag}
                      onDragLeave={handleDrag}
                      onDragOver={handleDrag}
                      onDrop={handleDrop}
                    >
                      <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                      <p className="text-sm text-muted-foreground mb-2">
                        Drag & drop a file or{' '}
                        <label className="text-blue-600 hover:underline cursor-pointer">
                          browse
                          <input
                            type="file"
                            accept=".txt,.md,.json"
                            className="hidden"
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              if (file) {
                                setSelectedFile(file);
                                if (!uploadName) {
                                  setUploadName(file.name.replace(/\.[^/.]+$/, ''));
                                }
                              }
                            }}
                          />
                        </label>
                      </p>
                      <p className="text-xs text-muted-foreground">Supports .txt, .md, .json</p>
                    </div>

                    {selectedFile && (
                      <div className="p-3 bg-muted rounded-lg flex items-center gap-3">
                        <FileText className="h-5 w-5 text-muted-foreground" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-foreground truncate">
                            {selectedFile.name}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {(selectedFile.size / 1024).toFixed(1)} KB
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setSelectedFile(null)}
                          className="shrink-0"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    )}

                    <Input
                      placeholder="Resume name..."
                      value={uploadName}
                      onChange={(e) => setUploadName(e.target.value)}
                    />

                    <Button
                      onClick={handleUpload}
                      disabled={!selectedFile || !uploadName.trim() || uploadMutation.isPending}
                      className="w-full"
                    >
                      {uploadMutation.isPending ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Uploading...
                        </>
                      ) : (
                        <>
                          <Upload className="h-4 w-4" />
                          Upload Resume
                        </>
                      )}
                    </Button>
                  </CardContent>
                </Card>
              </div>

              {/* Resume List */}
              <div className="lg:col-span-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Your Resumes</CardTitle>
                    <CardDescription>{resumes.length} resumes saved</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {resumes.length === 0 ? (
                      <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="text-center py-12 text-gray-500"
                      >
                        <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                        <p className="font-medium">No resumes yet</p>
                        <p className="text-sm mt-1">Upload your first resume to get started</p>
                      </motion.div>
                    ) : (
                      <div className="space-y-3">
                        <AnimatePresence mode="popLayout">
                          {resumes.map((resume, index) => (
                            <ResumeCard
                              key={resume.filename}
                              resume={resume}
                              index={index}
                              onPreview={() => handlePreview(resume.filename)}
                              onDelete={() => handleDelete(resume.filename)}
                              isDeleting={deletingResume === resume.filename}
                            />
                          ))}
                        </AnimatePresence>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="saved-bullets">
            <SavedBullets />
          </TabsContent>
        </Tabs>

        {/* Preview Modal */}
        <AnimatePresence>
          {previewResume && (
            <ResumePreviewModal
              filename={previewResume.filename}
              preview={previewResume.preview}
              onClose={() => setPreviewResume(null)}
            />
          )}
        </AnimatePresence>
      </div>
    </PageTransition>
  );
}
