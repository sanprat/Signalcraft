'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

export default function ChartSearchPage() {
    const [symbol, setSymbol] = useState('');
    const router = useRouter();

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        if (symbol.trim()) {
            router.push(`/chart/${symbol.trim().toUpperCase()}`);
        }
    };

    return (
        <div className="p-8 max-w-2xl mx-auto mt-10">
            <h1 className="text-3xl font-bold mb-2 text-gray-800">Historical Chart Viewer</h1>
            <p className="text-gray-500 mb-4">View 11 years of 1-Day historical data for any NIFTY 500 stock instantly.</p>
            <div className="mb-8">
                <Link href="/dashboard?segment=Stocks" className="text-blue-600 hover:text-blue-800 font-medium text-sm flex items-center gap-1">
                    ← Back to Stocks Dashboard
                </Link>
            </div>

            <form onSubmit={handleSearch} className="flex gap-4">
                <input
                    type="text"
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    placeholder="Enter NIFTY 500 Symbol (e.g., RELIANCE, TCS)"
                    className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm text-gray-800"
                    required
                />
                <button
                    type="submit"
                    className="px-8 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition shadow-sm"
                >
                    View Chart
                </button>
            </form>
        </div>
    );
}
