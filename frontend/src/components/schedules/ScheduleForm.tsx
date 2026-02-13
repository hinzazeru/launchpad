/**
 * ScheduleForm - Form for creating/editing scheduled job searches.
 * Reuses the same search parameters as GetJobs.
 */

import { useState } from 'react';
import {
    useResumes,
    useCreateSchedule,
    useUpdateSchedule,
} from '@/services/api';
import type { ScheduledSearch, ScheduleCreateParams, ScheduleUpdateParams } from '@/services/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { useToastActions } from '@/components/ui/toast';
import {
    Calendar,
    Clock,
    Loader2,
    Save,
    X,
    Plus,
} from 'lucide-react';

// Reuse constants from GetJobs
const JOB_TYPES = [
    { value: '', label: 'Any' },
    { value: 'Full-time', label: 'Full-time' },
    { value: 'Part-time', label: 'Part-time' },
    { value: 'Contract', label: 'Contract' },
    { value: 'Temporary', label: 'Temporary' },
    { value: 'Internship', label: 'Internship' },
];

const EXPERIENCE_LEVELS = [
    { value: '', label: 'Any' },
    { value: 'Entry level', label: 'Entry level' },
    { value: 'Mid-Senior level', label: 'Mid-Senior level' },
    { value: 'Director', label: 'Director' },
    { value: 'Executive', label: 'Executive' },
];

const WORK_ARRANGEMENTS = [
    { value: '', label: 'Any' },
    { value: 'Remote', label: 'Remote' },
    { value: 'Hybrid', label: 'Hybrid' },
    { value: 'On-site', label: 'On-site' },
];

const TIMEZONES = [
    { value: 'America/Toronto', label: 'Eastern (Toronto)' },
    { value: 'America/Chicago', label: 'Central (Chicago)' },
    { value: 'America/Denver', label: 'Mountain (Denver)' },
    { value: 'America/Los_Angeles', label: 'Pacific (Los Angeles)' },
    { value: 'America/Vancouver', label: 'Pacific (Vancouver)' },
    { value: 'UTC', label: 'UTC' },
];

interface ScheduleFormProps {
    schedule?: ScheduledSearch | null;
    onClose: () => void;
    onSaved?: () => void;
}

export function ScheduleForm({ schedule, onClose, onSaved }: ScheduleFormProps) {
    const toast = useToastActions();
    const { data: resumesData, isLoading: resumesLoading } = useResumes();
    const createMutation = useCreateSchedule();
    const updateMutation = useUpdateSchedule();

    const isEditing = !!schedule;
    const isSaving = createMutation.isPending || updateMutation.isPending;

    // Form state
    const [name, setName] = useState(schedule?.name || '');
    const [keyword, setKeyword] = useState(schedule?.keyword || '');
    const [location, setLocation] = useState(schedule?.location || 'Canada');
    const [jobType, setJobType] = useState(schedule?.job_type || '');
    const [experienceLevel, setExperienceLevel] = useState(schedule?.experience_level || '');
    const [workArrangement, setWorkArrangement] = useState(schedule?.work_arrangement || '');
    const [maxResults, setMaxResults] = useState(schedule?.max_results || 25);
    const [selectedResume, setSelectedResume] = useState(schedule?.resume_filename || '');
    const [exportToSheets, setExportToSheets] = useState(schedule?.export_to_sheets ?? true);
    const [maxRetries, setMaxRetries] = useState(schedule?.max_retries ?? 2);
    const [retryDelayMinutes, setRetryDelayMinutes] = useState(schedule?.retry_delay_minutes ?? 10);
    const [enabled, setEnabled] = useState(schedule?.enabled ?? true);
    const [timezone, setTimezone] = useState(schedule?.timezone || 'America/Toronto');
    const [weekdaysOnly, setWeekdaysOnly] = useState(schedule?.weekdays_only ?? false);
    const [runTimes, setRunTimes] = useState<string[]>(
        schedule?.run_times || ['08:00', '12:00', '16:00', '20:00']
    );
    const [newTime, setNewTime] = useState('');

    const resumes = resumesData?.resumes || [];

    // Validate time format
    const isValidTime = (time: string) => /^([01]\d|2[0-3]):([0-5]\d)$/.test(time);

    const addRunTime = () => {
        if (!newTime) return;
        if (!isValidTime(newTime)) {
            toast.error('Invalid Time', 'Please use HH:MM format (e.g., 09:00, 14:30)');
            return;
        }
        if (runTimes.includes(newTime)) {
            toast.error('Duplicate Time', 'This time is already in the schedule');
            return;
        }
        setRunTimes([...runTimes, newTime].sort());
        setNewTime('');
    };

    const removeRunTime = (time: string) => {
        setRunTimes(runTimes.filter(t => t !== time));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        // Validation
        if (!name.trim()) {
            toast.error('Validation Error', 'Please enter a schedule name');
            return;
        }
        if (!keyword.trim()) {
            toast.error('Validation Error', 'Please enter a keyword');
            return;
        }
        if (!selectedResume) {
            toast.error('Validation Error', 'Please select a resume');
            return;
        }
        if (runTimes.length === 0) {
            toast.error('Validation Error', 'Please add at least one run time');
            return;
        }

        try {
            if (isEditing && schedule) {
                const params: ScheduleUpdateParams = {
                    name: name.trim(),
                    keyword: keyword.trim(),
                    location: location || undefined,
                    job_type: jobType || undefined,
                    experience_level: experienceLevel || undefined,
                    work_arrangement: workArrangement || undefined,
                    max_results: maxResults,
                    resume_filename: selectedResume,
                    export_to_sheets: exportToSheets,
                    max_retries: maxRetries,
                    retry_delay_minutes: retryDelayMinutes,
                    enabled,
                    timezone,
                    run_times: runTimes,
                    weekdays_only: weekdaysOnly,
                };
                await updateMutation.mutateAsync({ id: schedule.id, params });
                toast.success('Schedule Updated', `"${name}" has been updated`);
            } else {
                const params: ScheduleCreateParams = {
                    name: name.trim(),
                    keyword: keyword.trim(),
                    location: location || undefined,
                    job_type: jobType || undefined,
                    experience_level: experienceLevel || undefined,
                    work_arrangement: workArrangement || undefined,
                    max_results: maxResults,
                    resume_filename: selectedResume,
                    export_to_sheets: exportToSheets,
                    max_retries: maxRetries,
                    retry_delay_minutes: retryDelayMinutes,
                    enabled,
                    timezone,
                    run_times: runTimes,
                    weekdays_only: weekdaysOnly,
                };
                await createMutation.mutateAsync(params);
                toast.success('Schedule Created', `"${name}" has been created`);
            }
            onSaved?.();
            onClose();
        } catch {
            toast.error('Error', `Failed to ${isEditing ? 'update' : 'create'} schedule`);
        }
    };

    return (
        <Card>
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="flex items-center gap-2">
                            <Calendar className="h-5 w-5" />
                            {isEditing ? 'Edit Schedule' : 'New Schedule'}
                        </CardTitle>
                        <CardDescription>
                            {isEditing
                                ? 'Modify the scheduled search configuration'
                                : 'Create a new automated job search schedule'
                            }
                        </CardDescription>
                    </div>
                    <Button variant="ghost" size="icon" onClick={onClose}>
                        <X className="h-5 w-5" />
                    </Button>
                </div>
            </CardHeader>
            <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                    {/* Schedule Name */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium">
                            Schedule Name <span className="text-red-500">*</span>
                        </label>
                        <Input
                            placeholder="e.g., Daily Product Manager Search"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            disabled={isSaving}
                        />
                    </div>

                    {/* Keyword */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium">
                            Keyword <span className="text-red-500">*</span>
                        </label>
                        <Input
                            placeholder="e.g., Product Manager, Senior Developer"
                            value={keyword}
                            onChange={(e) => setKeyword(e.target.value)}
                            disabled={isSaving}
                        />
                        <p className="text-xs text-muted-foreground">
                            Tip: Add "Remote" at the end to search for remote jobs
                        </p>
                    </div>

                    {/* Work Arrangement */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Work Arrangement</label>
                        <Select
                            value={workArrangement}
                            onValueChange={(val) => {
                                setWorkArrangement(val);
                                if (val === 'Remote') {
                                    setLocation('');
                                }
                            }}
                            disabled={isSaving}
                        >
                            <SelectTrigger>
                                <SelectValue placeholder="Any" />
                            </SelectTrigger>
                            <SelectContent>
                                {WORK_ARRANGEMENTS.map((arr) => (
                                    <SelectItem key={arr.value || '__any__'} value={arr.value || '__any__'}>
                                        {arr.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Location */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Location</label>
                        <Input
                            placeholder={workArrangement === 'Remote' ? 'Remote (Location ignored)' : 'Canada'}
                            value={location}
                            onChange={(e) => setLocation(e.target.value)}
                            disabled={isSaving || workArrangement === 'Remote'}
                        />
                    </div>

                    {/* Job Type */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Job Type</label>
                        <Select value={jobType} onValueChange={setJobType} disabled={isSaving}>
                            <SelectTrigger>
                                <SelectValue placeholder="Any" />
                            </SelectTrigger>
                            <SelectContent>
                                {JOB_TYPES.map((type) => (
                                    <SelectItem key={type.value || '__any__'} value={type.value || '__any__'}>
                                        {type.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Experience Level */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Experience Level</label>
                        <Select value={experienceLevel} onValueChange={setExperienceLevel} disabled={isSaving}>
                            <SelectTrigger>
                                <SelectValue placeholder="Any" />
                            </SelectTrigger>
                            <SelectContent>
                                {EXPERIENCE_LEVELS.map((level) => (
                                    <SelectItem key={level.value || '__any__'} value={level.value || '__any__'}>
                                        {level.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Max Results */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Max Results</label>
                        <Input
                            type="number"
                            min={1}
                            max={100}
                            value={maxResults}
                            onChange={(e) => setMaxResults(Math.min(100, Math.max(1, parseInt(e.target.value) || 25)))}
                            disabled={isSaving}
                        />
                    </div>

                    {/* Resume Selection */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium">
                            Resume <span className="text-red-500">*</span>
                        </label>
                        <Select value={selectedResume} onValueChange={setSelectedResume} disabled={isSaving || resumesLoading}>
                            <SelectTrigger>
                                <SelectValue placeholder={resumesLoading ? 'Loading...' : 'Select a resume'} />
                            </SelectTrigger>
                            <SelectContent>
                                {resumes.map((resume) => (
                                    <SelectItem key={resume.filename} value={resume.filename}>
                                        {resume.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        {resumes.length === 0 && !resumesLoading && (
                            <p className="text-xs text-amber-600">
                                No resumes found. Please upload one in the Resume Library first.
                            </p>
                        )}
                    </div>

                    {/* Timezone */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Timezone</label>
                        <Select value={timezone} onValueChange={setTimezone} disabled={isSaving}>
                            <SelectTrigger>
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {TIMEZONES.map((tz) => (
                                    <SelectItem key={tz.value} value={tz.value}>
                                        {tz.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Run Times */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium flex items-center gap-2">
                            <Clock className="h-4 w-4" />
                            Daily Run Times <span className="text-red-500">*</span>
                        </label>
                        <div className="flex flex-wrap gap-2 mb-2">
                            {runTimes.map((time) => (
                                <Badge
                                    key={time}
                                    variant="secondary"
                                    className="flex items-center gap-1 px-2 py-1"
                                >
                                    {time}
                                    <button
                                        type="button"
                                        onClick={() => removeRunTime(time)}
                                        className="ml-1 hover:text-red-500"
                                        disabled={isSaving}
                                    >
                                        <X className="h-3 w-3" />
                                    </button>
                                </Badge>
                            ))}
                            {runTimes.length === 0 && (
                                <span className="text-sm text-muted-foreground">No run times set</span>
                            )}
                        </div>
                        <div className="flex gap-2">
                            <Input
                                type="time"
                                value={newTime}
                                onChange={(e) => setNewTime(e.target.value)}
                                disabled={isSaving}
                                className="w-32"
                            />
                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={addRunTime}
                                disabled={isSaving || !newTime}
                            >
                                <Plus className="h-4 w-4 mr-1" />
                                Add
                            </Button>
                        </div>
                    </div>

                    {/* Weekdays Only */}
                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            id="weekdaysOnly"
                            checked={weekdaysOnly}
                            onChange={(e) => setWeekdaysOnly(e.target.checked)}
                            disabled={isSaving}
                            className="h-4 w-4 rounded border-gray-300"
                        />
                        <label htmlFor="weekdaysOnly" className="text-sm">
                            Weekdays only (Mon–Fri)
                        </label>
                    </div>

                    {/* Export to Sheets */}
                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            id="exportToSheets"
                            checked={exportToSheets}
                            onChange={(e) => setExportToSheets(e.target.checked)}
                            disabled={isSaving}
                            className="h-4 w-4 rounded border-gray-300"
                        />
                        <label htmlFor="exportToSheets" className="text-sm">
                            Export results to Google Sheets
                        </label>
                    </div>

                    {/* Retry Settings */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Retry on Failure</label>
                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1">
                                <label className="text-xs text-muted-foreground">Max retries (0-5)</label>
                                <Input
                                    type="number"
                                    min={0}
                                    max={5}
                                    value={maxRetries}
                                    onChange={(e) => setMaxRetries(Math.min(5, Math.max(0, parseInt(e.target.value) || 0)))}
                                    disabled={isSaving}
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs text-muted-foreground">Delay (5-60 min)</label>
                                <Input
                                    type="number"
                                    min={5}
                                    max={60}
                                    value={retryDelayMinutes}
                                    onChange={(e) => setRetryDelayMinutes(Math.min(60, Math.max(5, parseInt(e.target.value) || 10)))}
                                    disabled={isSaving || maxRetries === 0}
                                />
                            </div>
                        </div>
                        <p className="text-xs text-muted-foreground">
                            {maxRetries === 0 ? 'Retries disabled' : `Up to ${maxRetries} retries, ${retryDelayMinutes} min apart`}
                        </p>
                    </div>

                    {/* Enabled */}
                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            id="enabled"
                            checked={enabled}
                            onChange={(e) => setEnabled(e.target.checked)}
                            disabled={isSaving}
                            className="h-4 w-4 rounded border-gray-300"
                        />
                        <label htmlFor="enabled" className="text-sm">
                            Enable schedule immediately
                        </label>
                    </div>

                    {/* Buttons */}
                    <div className="flex gap-3 pt-4">
                        <Button
                            type="submit"
                            disabled={isSaving || !name.trim() || !keyword.trim() || !selectedResume || runTimes.length === 0}
                            className="flex-1"
                        >
                            {isSaving ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    Saving...
                                </>
                            ) : (
                                <>
                                    <Save className="h-4 w-4 mr-2" />
                                    {isEditing ? 'Update Schedule' : 'Create Schedule'}
                                </>
                            )}
                        </Button>
                        <Button type="button" variant="outline" onClick={onClose} disabled={isSaving}>
                            Cancel
                        </Button>
                    </div>
                </form>
            </CardContent>
        </Card>
    );
}

export default ScheduleForm;
