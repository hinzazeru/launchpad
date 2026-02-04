import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useLikedBullets, useDeleteLikedBullet, useUniqueRoles } from '@/services/api';
import type { LikedBullet } from '@/services/api';
import { Trash2, Copy, CheckCircle2, Briefcase, Building2, Calendar, Sparkles, Search, Filter, X } from 'lucide-react';
import { useState, useMemo } from 'react';
import { useToastActions } from '@/components/ui/toast';

function SavedBulletCard({
    bullet,
    onDelete,
    index
}: {
    bullet: LikedBullet;
    onDelete: (id: number) => void;
    index: number;
}) {
    const [copied, setCopied] = useState<'original' | 'rewritten' | null>(null);
    const toast = useToastActions();

    const handleCopy = (text: string, type: 'original' | 'rewritten') => {
        navigator.clipboard.writeText(text);
        setCopied(type);
        toast.success('Copied to clipboard', 'Text has been copied to your clipboard.');
        setTimeout(() => setCopied(null), 3000); // Extended from 2000ms to 3000ms
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.3, delay: index * 0.05 }}
        >
            <Card className="group border-border/50 hover:shadow-md transition-shadow overflow-hidden">
                {/* Header - Context */}
                <div className="bg-muted/30 border-b border-border/50 px-4 py-3 flex items-start justify-between gap-4">
                    <div className="flex flex-col gap-1 min-w-0">
                        {(bullet.role_title || bullet.company) ? (
                            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                                {bullet.role_title && (
                                    <span className="font-semibold text-foreground flex items-center gap-1.5">
                                        <Briefcase className="w-3.5 h-3.5 text-primary" />
                                        {bullet.role_title}
                                    </span>
                                )}
                                {bullet.company && (
                                    <span className="text-muted-foreground flex items-center gap-1.5">
                                        <Building2 className="w-3.5 h-3.5" />
                                        {bullet.company}
                                    </span>
                                )}
                            </div>
                        ) : (
                            <span className="text-sm font-medium text-muted-foreground">Unknown Role context</span>
                        )}
                        <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
                            <Calendar className="w-3 h-3" />
                            <span>Saved on {new Date(bullet.created_at).toLocaleDateString()}</span>
                        </div>
                    </div>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="text-muted-foreground hover:text-red-500 hover:bg-red-50 -my-1 -mr-2"
                        onClick={() => onDelete(bullet.id)}
                    >
                        <Trash2 className="w-4 h-4" />
                    </Button>
                </div>

                <CardContent className="p-0">
                    <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x border-border/50">
                        {/* Original */}
                        <div className="p-4 space-y-2 relative group/section">
                            <div className="flex items-center justify-between mb-2">
                                <Badge variant="outline" className="text-xs font-normal text-muted-foreground">Original Bullet</Badge>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-6 w-6 opacity-0 group-hover/section:opacity-100 transition-opacity"
                                    onClick={() => handleCopy(bullet.original_text, 'original')}
                                >
                                    {copied === 'original' ? <CheckCircle2 className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                                </Button>
                            </div>
                            <p className="text-sm text-muted-foreground leading-relaxed">{bullet.original_text}</p>
                        </div>

                        {/* Rewritten */}
                        <div className="p-4 space-y-2 relative bg-emerald-500/5 group/section">
                            <div className="flex items-center justify-between mb-2">
                                <Badge variant="default" className="text-xs bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20 hover:bg-emerald-500/20">
                                    <Sparkles className="w-3 h-3 mr-1" />
                                    AI Rewrite
                                </Badge>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-6 w-6 opacity-0 group-hover/section:opacity-100 transition-opacity"
                                    onClick={() => handleCopy(bullet.rewritten_text, 'rewritten')}
                                >
                                    {copied === 'rewritten' ? <CheckCircle2 className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                                </Button>
                            </div>
                            <p className="text-sm text-foreground font-medium leading-relaxed">{bullet.rewritten_text}</p>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </motion.div>
    );
}

export function SavedBullets() {
    const [searchTerm, setSearchTerm] = useState('');
    const [roleFilter, setRoleFilter] = useState<string>('__all__');

    const { data: bulletsData, isLoading } = useLikedBullets({
        role_filter: roleFilter === '__all__' ? undefined : roleFilter,
    });
    const { data: uniqueRoles } = useUniqueRoles();
    const deleteMutation = useDeleteLikedBullet();
    const toast = useToastActions();

    // Filter bullets by search term (client-side filtering for text search)
    const filteredBullets = useMemo(() => {
        if (!bulletsData?.items) return [];
        if (!searchTerm) return bulletsData.items;

        const term = searchTerm.toLowerCase();
        return bulletsData.items.filter(b =>
            b.original_text.toLowerCase().includes(term) ||
            b.rewritten_text.toLowerCase().includes(term) ||
            b.role_title?.toLowerCase().includes(term) ||
            b.company?.toLowerCase().includes(term)
        );
    }, [bulletsData?.items, searchTerm]);

    const handleDelete = (id: number) => {
        if (!confirm('Remove this saved bullet?')) return;
        deleteMutation.mutate(id, {
            onSuccess: () => {
                toast.success('Deleted', 'Bullet removed from saved items.');
            }
        });
    };

    const clearFilters = () => {
        setSearchTerm('');
        setRoleFilter('__all__');
    };

    const hasFilters = searchTerm || roleFilter !== '__all__';

    if (isLoading) {
        return (
            <div className="space-y-4">
                {/* Search/Filter Skeleton */}
                <div className="flex gap-3">
                    <div className="h-10 flex-1 bg-muted/30 rounded-lg animate-pulse" />
                    <div className="h-10 w-48 bg-muted/30 rounded-lg animate-pulse" />
                </div>
                {/* Card Skeletons */}
                <div className="grid grid-cols-1 gap-4">
                    {[1, 2].map(i => (
                        <div key={i} className="h-40 bg-muted/30 rounded-lg animate-pulse" />
                    ))}
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Search and Filter Bar */}
            <div className="flex flex-col sm:flex-row gap-3">
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search bullets..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="pl-9"
                    />
                </div>
                <div className="flex gap-2">
                    <Select value={roleFilter} onValueChange={setRoleFilter}>
                        <SelectTrigger className="w-48">
                            <div className="flex items-center gap-2">
                                <Filter className="h-4 w-4 text-muted-foreground" />
                                <SelectValue placeholder="Filter by role" />
                            </div>
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="__all__">All Roles</SelectItem>
                            {uniqueRoles?.map(role => (
                                <SelectItem key={role} value={role}>{role}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    {hasFilters && (
                        <Button variant="ghost" size="icon" onClick={clearFilters} title="Clear filters">
                            <X className="h-4 w-4" />
                        </Button>
                    )}
                </div>
            </div>

            {/* Results Count */}
            {bulletsData && (
                <div className="text-sm text-muted-foreground">
                    Showing {filteredBullets.length} of {bulletsData.total} saved bullets
                    {hasFilters && ' (filtered)'}
                </div>
            )}

            {/* Empty State */}
            {filteredBullets.length === 0 && (
                <Card className="border-dashed border-border">
                    <CardContent className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
                        <Sparkles className="h-10 w-10 mb-3 opacity-20" />
                        {hasFilters ? (
                            <>
                                <p className="font-medium">No bullets match your filters</p>
                                <p className="text-sm">Try adjusting your search or filter criteria.</p>
                                <Button variant="ghost" className="mt-3" onClick={clearFilters}>
                                    Clear Filters
                                </Button>
                            </>
                        ) : (
                            <>
                                <p className="font-medium">No saved bullets yet</p>
                                <p className="text-sm">Click the heart icon on AI suggestions to save them here.</p>
                            </>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Bullets List */}
            {filteredBullets.length > 0 && (
                <AnimatePresence mode="popLayout">
                    {filteredBullets.map((bullet, index) => (
                        <SavedBulletCard
                            key={bullet.id}
                            bullet={bullet}
                            index={index}
                            onDelete={handleDelete}
                        />
                    ))}
                </AnimatePresence>
            )}
        </div>
    );
}
