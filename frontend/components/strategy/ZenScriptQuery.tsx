'use client'

import { useState } from 'react'
import { Sparkles, Loader2, ArrowDown } from 'lucide-react'
import type { ConfigNLPResponse, NLPParseResponse, NLPSection } from '@/lib/types/strategy'
import { parseStrategyQuery } from '@/lib/api/strategy'

interface ZenScriptQueryProps {
    section: NLPSection
    title: string
    description: string
    placeholder: string
    successLabel: string
    onApply: (result: NLPParseResponse) => void
}

export function ZenScriptQuery({
    section,
    title,
    description,
    placeholder,
    successLabel,
    onApply,
}: ZenScriptQueryProps) {
    const [query, setQuery] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [successMsg, setSuccessMsg] = useState<string | null>(null)
    const [hintLines, setHintLines] = useState<string[]>([])

    const handleGenerate = async () => {
        if (!query.trim()) return

        setIsLoading(true)
        setError(null)
        setSuccessMsg(null)
        setHintLines([])

        try {
            const data = await parseStrategyQuery({ section, query })
            onApply(data)

            const countLabel = (() => {
                if (data.section === 'entry') return `${data.conditions.length} condition(s)`
                if (data.section === 'exit') return `${data.exit_rules.length} exit rule(s)`
                return successLabel
            })()

            setSuccessMsg(`Applied ${countLabel}.`)
            if (data.section === 'config' && (data as ConfigNLPResponse).symbol_matches?.length) {
                const configData = data as ConfigNLPResponse
                setHintLines(
                    (configData.symbol_matches || []).map(
                        (match) => `${match.input} -> ${match.symbol}`
                    )
                )
            }
            setTimeout(() => setSuccessMsg(null), 3000)
        } catch (err: any) {
            setError(err.message)
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden mb-6">
            <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border-b border-blue-100 px-5 py-4">
                <div className="flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-indigo-600" />
                    <h3 className="text-sm font-bold text-slate-800">{title}</h3>
                </div>
                <p className="mt-1 text-xs leading-5 text-slate-600">{description}</p>
            </div>

            <div className="p-5">
                <textarea
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={placeholder}
                    className="min-h-[100px] w-full resize-y rounded-lg border border-slate-300 bg-white p-4 font-sans text-sm font-medium leading-relaxed text-slate-800 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 placeholder:text-slate-400"
                />

                {error && (
                    <div className="mt-3 rounded-lg bg-red-50 px-4 py-3 text-xs font-medium text-red-700 border border-red-100">
                        {error}
                    </div>
                )}

                {successMsg && (
                    <div className="mt-3 rounded-lg bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-700 border border-emerald-100">
                        <div className="flex items-center gap-2">
                            <ArrowDown className="h-4 w-4" />
                            {successMsg}
                        </div>
                        {hintLines.length > 0 && (
                            <div className="mt-2 border-t border-emerald-100 pt-2 text-[11px] leading-5 text-emerald-800">
                                Interpreted symbols: {hintLines.join(' • ')}
                            </div>
                        )}
                    </div>
                )}

                <div className="mt-4 flex justify-end">
                    <button
                        onClick={handleGenerate}
                        disabled={isLoading || !query.trim()}
                        className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-bold text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50 shadow-sm"
                    >
                        {isLoading ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Sparkles className="h-4 w-4" />
                        )}
                        Generate Visual Rules
                    </button>
                </div>
            </div>
        </div>
    )
}
