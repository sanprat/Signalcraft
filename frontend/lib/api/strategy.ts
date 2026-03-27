/**
 * Strategy V2 API Client
 * API functions for validating, backtesting, and saving strategies
 */

import { config, getAuthHeaders } from '@/lib/config'
import type {
    StrategyV2,
    ValidationResult,
    SaveStrategyRequest,
    SaveStrategyResponse,
    LoadStrategyResponse,
    IndicatorDefinition,
} from '@/lib/types/strategy'

const API_BASE = config.apiBaseUrl

/**
 * Validate a strategy JSON payload
 */
export async function validateStrategy(strategy: StrategyV2): Promise<ValidationResult> {
    try {
        const response = await fetch(`${API_BASE}/api/strategy/v2/validate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders(),
            },
            body: JSON.stringify(strategy),
        })

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Validation failed' }))
            return {
                valid: false,
                errors: [error.detail || 'Validation failed'],
                warnings: [],
            }
        }

        return await response.json()
    } catch (error) {
        console.error('Strategy validation error:', error)
        return {
            valid: false,
            errors: ['Network error - could not connect to server'],
            warnings: [],
        }
    }
}

/**
 * Run a backtest on a strategy
 */
export async function backtestStrategy(
    strategy: StrategyV2,
    mode: 'quick' | 'full' = 'quick'
): Promise<any> {
    try {
        const response = await fetch(`${API_BASE}/api/strategy/v2/backtest`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders(),
            },
            body: JSON.stringify({ strategy, mode }),
        })

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Backtest failed' }))
            throw new Error(error.detail || 'Backtest failed')
        }

        return await response.json()
    } catch (error) {
        console.error('Backtest error:', error)
        throw error
    }
}

/**
 * Run a quick backtest (last N days)
 */
export async function quickBacktest(
    strategy: StrategyV2,
    days: number = 90
): Promise<any> {
    try {
        const response = await fetch(`${API_BASE}/api/strategy/v2/backtest/quick?days=${days}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders(),
            },
            body: JSON.stringify(strategy),
        })

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Quick backtest failed' }))
            throw new Error(error.detail || 'Quick backtest failed')
        }

        return await response.json()
    } catch (error) {
        console.error('Quick backtest error:', error)
        throw error
    }
}

/**
 * Save a strategy
 */
export async function saveStrategy(
    strategy: StrategyV2,
    strategyId?: string
): Promise<SaveStrategyResponse> {
    try {
        const request: SaveStrategyRequest = {
            strategy,
            strategy_id: strategyId,
        }

        const response = await fetch(`${API_BASE}/api/strategy/v2/save`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders(),
            },
            body: JSON.stringify(request),
        })

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Save failed' }))
            throw new Error(error.detail || 'Save failed')
        }

        return await response.json()
    } catch (error) {
        console.error('Save strategy error:', error)
        throw error
    }
}

/**
 * Load a strategy by ID
 */
export async function loadStrategy(strategyId: string): Promise<LoadStrategyResponse> {
    try {
        const response = await fetch(`${API_BASE}/api/strategy/v2/load/${strategyId}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders(),
            },
        })

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Load failed' }))
            throw new Error(error.detail || 'Load failed')
        }

        return await response.json()
    } catch (error) {
        console.error('Load strategy error:', error)
        throw error
    }
}

/**
 * List all strategies for the current user
 */
export async function listStrategies(): Promise<any[]> {
    try {
        const response = await fetch(`${API_BASE}/api/strategy/v2/list`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders(),
            },
        })

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'List failed' }))
            throw new Error(error.detail || 'List failed')
        }

        return await response.json()
    } catch (error) {
        console.error('List strategies error:', error)
        throw error
    }
}

/**
 * Delete a strategy by ID
 */
export async function deleteStrategy(strategyId: string): Promise<void> {
    try {
        const response = await fetch(`${API_BASE}/api/strategy/v2/${strategyId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders(),
            },
        })

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Delete failed' }))
            throw new Error(error.detail || 'Delete failed')
        }
    } catch (error) {
        console.error('Delete strategy error:', error)
        throw error
    }
}

/**
 * Get list of available indicators from the backend
 */
export async function getIndicators(): Promise<IndicatorDefinition[]> {
    try {
        const response = await fetch(`${API_BASE}/api/strategy/v2/indicators`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders(),
            },
        })

        if (!response.ok) {
            // Fallback to local list
            return []
        }

        return await response.json()
    } catch (error) {
        console.error('Get indicators error:', error)
        return []
    }
}

/**
 * Get NIFTY 500 symbols from the backend
 */
export async function getSymbols(): Promise<string[]> {
    try {
        const response = await fetch(`${API_BASE}/api/stocks`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders(),
            },
        })

        if (!response.ok) {
            // Fallback to common stocks
            return [
                'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'HINDUNILVR', 'ITC',
                'KOTAKBANK', 'LT', 'SBIN', 'AXISBANK', 'ASIANPAINT', 'NESTLEIND', 'MARUTI',
                'BAJFINANCE', 'HDFC', 'ADANIPORTS', 'BRITANNIA', 'TITAN', 'ULTRACEMCO',
            ]
        }

        const data = await response.json()
        return data.stocks || []
    } catch (error) {
        console.error('Get symbols error:', error)
        return []
    }
}
