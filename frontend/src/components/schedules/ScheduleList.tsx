/**
 * ScheduleList - Displays and manages scheduled job searches.
 * Shows schedule list with enable/disable toggles and run-now buttons.
 */

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    useSchedules,
    useToggleSchedule,
    useDeleteSchedule,
    useRunScheduleNow,
    useSchedulerStatus,
} from '@/services/api';
import type { ScheduledSearch } from '@/services/api';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToastActions } from '@/components/ui/toast';
import {
    Calendar,
    Clock,
    Play,
    Pause,
    Trash2,
    Loader2,
    Settings,
    Plus,
    CheckCircle2,
    XCircle,
    AlertCircle,
    Edit,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface ScheduleListProps {
    onEdit?: (schedule: ScheduledSearch) => void;
    onCreateNew?: () => void;
}

export function ScheduleList({ onEdit, onCreateNew }: ScheduleListProps) {
    const toast = useToastActions();
    const { data: schedulesData, isLoading, error } = useSchedules();
    const { data: statusData } = useSchedulerStatus();
    const toggleMutation = useToggleSchedule();
    const deleteMutation = useDeleteSchedule();
    const runNowMutation = useRunScheduleNow();

    const [deletingId, setDeletingId] = useState<number | null>(null);

    const schedules = schedulesData?.schedules || [];

    const handleToggle = async (schedule: ScheduledSearch) => {
        try {
            const result = await toggleMutation.mutateAsync(schedule.id);
            toast.success(
                result.enabled ? 'Schedule Enabled' : 'Schedule Disabled',
                `"${schedule.name}" has been ${result.enabled ? 'enabled' : 'disabled'}`
            );
        } catch {
            toast.error('Error', 'Failed to toggle schedule');
        }
    };

    const handleDelete = async (schedule: ScheduledSearch) => {
        if (!confirm(`Delete schedule "${schedule.name}"? This cannot be undone.`)) {
            return;
        }
        setDeletingId(schedule.id);
        try {
            await deleteMutation.mutateAsync(schedule.id);
            toast.success('Schedule Deleted', `"${schedule.name}" has been deleted`);
        } catch {
            toast.error('Error', 'Failed to delete schedule');
        } finally {
            setDeletingId(null);
        }
    };

    const handleRunNow = async (schedule: ScheduledSearch) => {
        try {
            await runNowMutation.mutateAsync(schedule.id);
            toast.success('Search Started', `"${schedule.name}" is running in the background`);
        } catch {
            toast.error('Error', 'Failed to start search');
        }
    };

    const formatNextRun = (nextRunAt?: string) => {
        if (!nextRunAt) return 'Not scheduled';
        const date = new Date(nextRunAt);
        const now = new Date();
        const diffMs = date.getTime() - now.getTime();

        if (diffMs < 0) return 'Overdue';
        if (diffMs < 60 * 1000) return 'Less than a minute';
        if (diffMs < 60 * 60 * 1000) {
            const mins = Math.floor(diffMs / (60 * 1000));
            return `In ${mins} minute${mins > 1 ? 's' : ''}`;
        }
        if (diffMs < 24 * 60 * 60 * 1000) {
            const hours = Math.floor(diffMs / (60 * 60 * 1000));
            return `In ${hours} hour${hours > 1 ? 's' : ''}`;
        }
        return date.toLocaleDateString(undefined, {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const getStatusBadge = (status?: string) => {
        switch (status) {
            case 'success':
                return (
                    <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                        <CheckCircle2 className="h-3 w-3 mr-1" />
                        Success
                    </Badge>
                );
            case 'error':
                return (
                    <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
                        <XCircle className="h-3 w-3 mr-1" />
                        Error
                    </Badge>
                );
            case 'running':
                return (
                    <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                        <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                        Running
                    </Badge>
                );
            default:
                return (
                    <Badge variant="outline" className="bg-gray-50 text-gray-500 border-gray-200">
                        <AlertCircle className="h-3 w-3 mr-1" />
                        Never run
                    </Badge>
                );
        }
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center p-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (error) {
        return (
            <Card className="border-red-200 bg-red-50">
                <CardContent className="p-6 text-center">
                    <XCircle className="h-10 w-10 mx-auto text-red-500 mb-3" />
                    <p className="text-red-600">Failed to load schedules</p>
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            {/* Scheduler Status Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className={cn(
                        "w-3 h-3 rounded-full",
                        statusData?.running ? "bg-green-500 animate-pulse" : "bg-gray-400"
                    )} />
                    <span className="text-sm text-muted-foreground">
                        {statusData?.running ? 'Scheduler running' : 'Scheduler stopped'}
                        {statusData?.active_schedules !== undefined && (
                            <span> • {statusData.active_schedules} active schedule{statusData.active_schedules !== 1 ? 's' : ''}</span>
                        )}
                    </span>
                </div>
                <Button onClick={onCreateNew} size="sm">
                    <Plus className="h-4 w-4 mr-2" />
                    New Schedule
                </Button>
            </div>

            {/* Schedule List */}
            {schedules.length === 0 ? (
                <Card className="border-dashed">
                    <CardContent className="flex flex-col items-center justify-center p-12 text-center">
                        <Calendar className="h-12 w-12 text-muted-foreground/30 mb-4" />
                        <h3 className="text-lg font-medium text-muted-foreground">No Scheduled Searches</h3>
                        <p className="text-sm text-muted-foreground mt-1 mb-4">
                            Create a schedule to automatically run job searches at specific times
                        </p>
                        <Button onClick={onCreateNew}>
                            <Plus className="h-4 w-4 mr-2" />
                            Create First Schedule
                        </Button>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-3">
                    <AnimatePresence initial={false}>
                        {schedules.map((schedule, index) => (
                            <motion.div
                                key={schedule.id}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, x: -20 }}
                                transition={{ delay: index * 0.05 }}
                            >
                                <Card className={cn(
                                    "transition-colors",
                                    !schedule.enabled && "opacity-60 bg-muted/30"
                                )}>
                                    <CardContent className="p-4">
                                        <div className="flex items-start justify-between gap-4">
                                            {/* Left: Schedule Info */}
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <h4 className="font-medium truncate">{schedule.name}</h4>
                                                    {schedule.enabled ? (
                                                        <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200 text-xs">
                                                            Active
                                                        </Badge>
                                                    ) : (
                                                        <Badge variant="outline" className="bg-gray-50 text-gray-500 border-gray-200 text-xs">
                                                            Paused
                                                        </Badge>
                                                    )}
                                                </div>

                                                <div className="text-sm text-muted-foreground mb-2">
                                                    <span className="font-medium">{schedule.keyword}</span>
                                                    {schedule.location && <span> • {schedule.location}</span>}
                                                    {schedule.work_arrangement && <span> • {schedule.work_arrangement}</span>}
                                                </div>

                                                <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                                                    <div className="flex items-center gap-1">
                                                        <Clock className="h-3 w-3" />
                                                        <span>{schedule.run_times?.join(', ') || 'No times set'}</span>
                                                    </div>
                                                    <div className="flex items-center gap-1">
                                                        <Settings className="h-3 w-3" />
                                                        <span>{schedule.max_results} results</span>
                                                    </div>
                                                    {schedule.enabled && schedule.next_run_at && (
                                                        <div className="flex items-center gap-1">
                                                            <Calendar className="h-3 w-3" />
                                                            <span>Next: {formatNextRun(schedule.next_run_at)}</span>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>

                                            {/* Right: Status & Actions */}
                                            <div className="flex flex-col items-end gap-2 shrink-0">
                                                {getStatusBadge(schedule.last_run_status)}

                                                <div className="flex items-center gap-1">
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        onClick={() => handleRunNow(schedule)}
                                                        disabled={runNowMutation.isPending}
                                                        title="Run now"
                                                    >
                                                        {runNowMutation.isPending && runNowMutation.variables === schedule.id ? (
                                                            <Loader2 className="h-4 w-4 animate-spin" />
                                                        ) : (
                                                            <Play className="h-4 w-4" />
                                                        )}
                                                    </Button>

                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        onClick={() => handleToggle(schedule)}
                                                        disabled={toggleMutation.isPending}
                                                        title={schedule.enabled ? 'Pause' : 'Enable'}
                                                    >
                                                        {toggleMutation.isPending && toggleMutation.variables === schedule.id ? (
                                                            <Loader2 className="h-4 w-4 animate-spin" />
                                                        ) : schedule.enabled ? (
                                                            <Pause className="h-4 w-4" />
                                                        ) : (
                                                            <Play className="h-4 w-4 text-green-600" />
                                                        )}
                                                    </Button>

                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        onClick={() => onEdit?.(schedule)}
                                                        title="Edit"
                                                    >
                                                        <Edit className="h-4 w-4" />
                                                    </Button>

                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        onClick={() => handleDelete(schedule)}
                                                        disabled={deletingId === schedule.id}
                                                        title="Delete"
                                                        className="text-red-500 hover:text-red-600 hover:bg-red-50"
                                                    >
                                                        {deletingId === schedule.id ? (
                                                            <Loader2 className="h-4 w-4 animate-spin" />
                                                        ) : (
                                                            <Trash2 className="h-4 w-4" />
                                                        )}
                                                    </Button>
                                                </div>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                </div>
            )}
        </div>
    );
}

export default ScheduleList;
