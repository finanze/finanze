// src/lib/formatters.ts

export const formatCurrency = (
    value: number,
    locale: string,
    mainCurrency: string,
    currencyCode?: string
): string => {
    const displayCurrency = currencyCode || mainCurrency
    return new Intl.NumberFormat(locale, {
        style: 'currency',
        currency: displayCurrency,
        minimumFractionDigits: 2,
    }).format(value)
}

export const formatPercentage = (value: number, locale: string): string => {
    return new Intl.NumberFormat(locale, {
        style: 'percent',
        minimumFractionDigits: 1,
        maximumFractionDigits: 2,
    }).format(value / 100)
}

export const formatNumber = (value: number, locale: string): string => {
    return new Intl.NumberFormat(locale, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 4,
    }).format(value)
}

export const formatDate = (dateString: string, locale: string): string => {
    return new Intl.DateTimeFormat(locale, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
    }).format(new Date(dateString))
}
