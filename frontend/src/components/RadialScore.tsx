import { motion } from 'framer-motion';

export function RadialScore({ score, size = 64, strokeWidth = 5 }: { score: number; size?: number; strokeWidth?: number }) {
    const radius = (size - strokeWidth) / 2;
    const circumference = radius * 2 * Math.PI;
    const offset = circumference - (score / 100) * circumference;

    // Dynamic gradient based on score
    const getGradientColors = () => {
        if (score >= 70) return { start: '#10b981', end: '#34d399' }; // Emerald
        if (score >= 50) return { start: '#f59e0b', end: '#fbbf24' }; // Amber
        return { start: '#ef4444', end: '#f87171' }; // Red
    };

    const colors = getGradientColors();
    const gradientId = `score-gradient-${score}-${Math.random().toString(36).substr(2, 9)}`;

    return (
        <div className="relative" style={{ width: size, height: size }}>
            <svg width={size} height={size} className="-rotate-90">
                <defs>
                    <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor={colors.start} />
                        <stop offset="100%" stopColor={colors.end} />
                    </linearGradient>
                </defs>
                {/* Background circle */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={strokeWidth}
                    className="text-muted/30"
                />
                {/* Progress circle */}
                <motion.circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke={`url(#${gradientId})`}
                    strokeWidth={strokeWidth}
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    initial={{ strokeDashoffset: circumference }}
                    animate={{ strokeDashoffset: offset }}
                    transition={{ duration: 0.8, ease: "easeOut", delay: 0.2 }}
                />
            </svg>
            {/* Center score */}
            <div className="absolute inset-0 flex items-center justify-center">
                <motion.span
                    className="text-base font-bold tabular-nums tracking-tight"
                    initial={{ opacity: 0, scale: 0.5 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.3, delay: 0.5 }}
                >
                    {Math.round(score)}%
                </motion.span>
            </div>
        </div>
    );
}
