const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

export function isCompleteDateString(value: string | null | undefined): value is string {
    return typeof value === 'string' && DATE_RE.test(value)
}

export function isValidDateString(value: string | null | undefined): value is string {
    if (!isCompleteDateString(value)) {
        return false
    }

    const parsed = new Date(`${value}T00:00:00Z`)
    return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}

export function isValidDateRange(from?: string, to?: string): boolean {
    if (!isValidDateString(from) || !isValidDateString(to)) {
        return false
    }

    return from <= to
}

export function assertValidBacktestDates(from?: string, to?: string): void {
    if ((from && !isValidDateString(from)) || (to && !isValidDateString(to))) {
        throw new Error('Please enter a complete backtest date range in YYYY-MM-DD format')
    }

    if (from && to && !isValidDateRange(from, to)) {
        throw new Error('Backtest start date must be on or before the end date')
    }
}
