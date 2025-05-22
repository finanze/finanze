import { Translations } from '@/i18n'

export function formatTimeAgo(date: Date | string, t: Translations): string {
    const now = new Date()
    const seconds = Math.round(
        (now.getTime() - new Date(date).getTime()) / 1000
    )

    if (seconds < 5) {
        return t.time.justNow
    }

    const minutes = Math.round(seconds / 60)
    if (minutes < 60) {
        return minutes === 1
            ? t.time.minuteAgo
            : t.time.minutesAgo.replace('{count}', minutes.toString())
    }

    const hours = Math.round(minutes / 60)
    if (hours < 24) {
        return hours === 1
            ? t.time.hourAgo
            : t.time.hoursAgo.replace('{count}', hours.toString())
    }

    const days = Math.round(hours / 24)
    if (days < 7) {
        return days === 1
            ? t.time.dayAgo
            : t.time.daysAgo.replace('{count}', days.toString())
    }

    const weeks = Math.round(days / 7)
    if (weeks < 4) {
        // Approximation for months
        return weeks === 1
            ? t.time.weekAgo
            : t.time.weeksAgo.replace('{count}', weeks.toString())
    }

    const months = Math.round(days / 30) // Approximation
    if (months < 12) {
        return months === 1
            ? t.time.monthAgo
            : t.time.monthsAgo.replace('{count}', months.toString())
    }

    const years = Math.round(days / 365) // Approximation
    return years === 1
        ? t.time.yearAgo
        : t.time.yearsAgo.replace('{count}', years.toString())
}
