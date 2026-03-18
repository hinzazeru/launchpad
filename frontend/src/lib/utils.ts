import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** All frontend timestamps display in Eastern Time. */
const DISPLAY_TZ = 'America/New_York';

/** Format as "Mar 18, 1:32 PM" in ET. */
export function formatDateTime(isoString: string | null): string {
  if (!isoString) return '--';
  return new Date(isoString).toLocaleString('en-US', {
    timeZone: DISPLAY_TZ,
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

/** Format as "Mar 18" in ET. */
export function formatDateShort(isoString: string): string {
  return new Date(isoString).toLocaleDateString('en-US', {
    timeZone: DISPLAY_TZ,
    month: 'short',
    day: 'numeric',
  });
}

/** Format as "3/18/2026" in ET. */
export function formatDateLocal(isoString: string): string {
  return new Date(isoString).toLocaleDateString('en-US', {
    timeZone: DISPLAY_TZ,
  });
}

/** Format with weekday: "Tue, Mar 18, 1:32 PM" in ET. */
export function formatDateTimeFull(isoString: string): string {
  return new Date(isoString).toLocaleDateString('en-US', {
    timeZone: DISPLAY_TZ,
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
