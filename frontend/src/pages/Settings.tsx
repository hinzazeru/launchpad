import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Settings as SettingsIcon, Tags, Save, Loader2, AlertCircle, CheckCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { DomainSelector } from '@/components/DomainSelector';
import { useAvailableDomains, useUserDomains, useUpdateUserDomains } from '@/services/api';
import { useToastActions } from '@/components/ui/toast';

export function Settings() {
  const toast = useToastActions();

  // Fetch data
  const { data: availableDomains, isLoading: loadingAvailable, error: availableError } = useAvailableDomains();
  const { data: userDomains, isLoading: loadingUser, error: userError } = useUserDomains();
  const updateDomains = useUpdateUserDomains();

  // Local state for editing
  const [selectedDomains, setSelectedDomains] = useState<string[]>([]);
  const [hasChanges, setHasChanges] = useState(false);

  // Sync local state when user domains load
  useEffect(() => {
    if (userDomains?.domains) {
      setSelectedDomains(userDomains.domains);
      setHasChanges(false);
    }
  }, [userDomains]);

  // Track changes
  const handleDomainChange = (domains: string[]) => {
    setSelectedDomains(domains);
    const originalDomains = userDomains?.domains || [];
    const changed =
      domains.length !== originalDomains.length ||
      domains.some((d) => !originalDomains.includes(d));
    setHasChanges(changed);
  };

  // Save changes
  const handleSave = async () => {
    try {
      await updateDomains.mutateAsync(selectedDomains);
      setHasChanges(false);
      toast.success('Saved', 'Your domain expertise has been updated');
    } catch (error) {
      toast.error('Error', error instanceof Error ? error.message : 'Failed to save domains');
    }
  };

  const isLoading = loadingAvailable || loadingUser;
  const error = availableError || userError;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-1">
        <motion.h1
          className="text-3xl font-bold tracking-tight"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          Settings
        </motion.h1>
        <motion.p
          className="text-muted-foreground"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
        >
          Configure your preferences to improve job matching
        </motion.p>
      </div>

      {/* Error State */}
      {error && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex flex-col items-center justify-center py-12 gap-2 text-destructive"
        >
          <AlertCircle className="w-8 h-8" />
          <p>Failed to load settings. Please try again.</p>
        </motion.div>
      )}

      {/* Loading State */}
      {isLoading && !error && (
        <div className="flex flex-col items-center justify-center py-16 gap-4">
          <motion.div
            className="w-12 h-12 rounded-full border-2 border-primary border-t-transparent"
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
          />
          <p className="text-muted-foreground">Loading settings...</p>
        </div>
      )}

      {/* Settings Content */}
      {!isLoading && !error && availableDomains && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          {/* Domain Expertise Section */}
          <div className="space-y-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
              <Tags className="w-4 h-4" />
              Domain Expertise
            </h2>

            <Card className="border-border/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <SettingsIcon className="w-5 h-5 text-primary" />
                  Your Industry & Platform Experience
                </CardTitle>
                <CardDescription>
                  Select the industries, platforms, and technologies you have experience with.
                  This improves job matching by aligning your background with job requirements.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <DomainSelector
                  categories={availableDomains.categories}
                  selectedDomains={selectedDomains}
                  onChange={handleDomainChange}
                  disabled={updateDomains.isPending}
                />

                {/* Save button */}
                <div className="flex items-center justify-between pt-4 border-t border-border/50">
                  <div className="text-sm text-muted-foreground">
                    {hasChanges ? (
                      <span className="text-amber-500 flex items-center gap-1">
                        <AlertCircle className="w-4 h-4" />
                        You have unsaved changes
                      </span>
                    ) : selectedDomains.length > 0 ? (
                      <span className="text-green-500 flex items-center gap-1">
                        <CheckCircle className="w-4 h-4" />
                        {selectedDomains.length} domain{selectedDomains.length !== 1 ? 's' : ''} selected
                      </span>
                    ) : (
                      <span>No domains selected</span>
                    )}
                  </div>
                  <Button
                    onClick={handleSave}
                    disabled={!hasChanges || updateDomains.isPending}
                    className="min-w-[100px]"
                  >
                    {updateDomains.isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Save className="w-4 h-4 mr-2" />
                        Save
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Info card about domain matching */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="mt-6"
          >
            <Card className="border-border/50 bg-muted/20">
              <CardContent className="py-4">
                <p className="text-sm text-muted-foreground">
                  <strong className="text-foreground">How domains affect matching:</strong>{' '}
                  Domain expertise contributes 20% to your overall match score. Jobs that require
                  specific industry experience (e.g., "fintech background required") will show
                  as skill gaps if you haven't selected those domains.
                </p>
              </CardContent>
            </Card>
          </motion.div>
        </motion.div>
      )}
    </div>
  );
}
