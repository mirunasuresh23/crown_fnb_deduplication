"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

interface ReviewGroup {
    id: string;
    items: any[];
    match_type: string;
    confidence: number;
}

export default function ReviewQueue() {
    const [groups, setGroups] = useState<ReviewGroup[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // Fetch review list from backend
        const fetchReviews = async () => {
            try {
                const res = await fetch("http://localhost:8000/api/review/list");
                const data = await res.json();
                setGroups(data.reviews || [
                    // Mock data for demonstration
                    {
                        id: "fuzzy_101",
                        match_type: "fuzzy_embedding",
                        confidence: 0.78,
                        items: [
                            { item_code: "A001", barcode: "123", DESCR: "Standard Widget", DESCR60: "Std Widget Blue" },
                            { item_code: "B002", barcode: "456", DESCR: "Widget Standard", DESCR60: "Widget Standard Blue XL" }
                        ]
                    }
                ]);
                setLoading(false);
            } catch (e) {
                setLoading(false);
            }
        };
        fetchReviews();
    }, []);

    const handleDecision = async (groupId: string, decision: "merge" | "discard") => {
        // Submit decision to backend
        await fetch("http://localhost:8000/api/review/decision", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ group_id: groupId, decision }),
        });
        setGroups(groups.filter(g => g.id !== groupId));
    };

    return (
        <main className="min-h-screen bg-slate-900 text-white p-8">
            <div className="max-w-5xl mx-auto">
                <header className="flex justify-between items-center mb-12">
                    <div>
                        <Link href="/" className="text-blue-400 hover:text-blue-300 text-sm mb-2 block">← Back to Dashboard</Link>
                        <h1 className="text-4xl font-bold">Review Queue</h1>
                    </div>
                    <div className="bg-slate-800 px-4 py-2 rounded-lg border border-slate-700">
                        <span className="text-slate-400 text-sm">Remaining:</span> <span className="font-bold">{groups.length}</span>
                    </div>
                </header>

                {loading ? (
                    <div className="text-center py-20 animate-pulse text-slate-500">Loading queue...</div>
                ) : groups.length === 0 ? (
                    <div className="text-center py-20 bg-slate-800/30 rounded-2xl border border-dashed border-slate-700">
                        <p className="text-slate-400">Queue is empty. Everything looks clean!</p>
                    </div>
                ) : (
                    <div className="space-y-6">
                        {groups.map((group) => (
                            <div key={group.id} className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
                                <div className="bg-slate-700/50 p-4 flex justify-between items-center border-b border-slate-700">
                                    <div className="flex items-center gap-4">
                                        <span className="bg-blue-900/40 text-blue-400 text-xs font-bold px-2 py-1 rounded uppercase tracking-wider">
                                            {group.match_type.replace('_', ' ')}
                                        </span>
                                        <span className="text-slate-300 text-sm">Confidence: {(group.confidence * 100).toFixed(0)}%</span>
                                    </div>
                                    <div className="flex gap-2">
                                        <button
                                            onClick={() => handleDecision(group.id, "merge")}
                                            className="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-1.5 rounded-lg text-sm font-bold transition-colors"
                                        >
                                            Merge Items
                                        </button>
                                        <button
                                            onClick={() => handleDecision(group.id, "discard")}
                                            className="bg-red-600/20 hover:bg-red-600/40 text-red-400 border border-red-900 px-4 py-1.5 rounded-lg text-sm font-bold transition-all"
                                        >
                                            Keep Separate
                                        </button>
                                    </div>
                                </div>
                                <div className="p-0">
                                    <table className="w-full text-left text-sm">
                                        <thead>
                                            <tr className="bg-slate-800/50 text-slate-500 uppercase text-[10px] tracking-widest border-b border-slate-700/50">
                                                <th className="px-6 py-3">Code</th>
                                                <th className="px-6 py-3">Barcode</th>
                                                <th className="px-6 py-3">DESCR</th>
                                                <th className="px-6 py-3">DESCR60</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-700/50">
                                            {group.items.map((item, idx) => (
                                                <tr key={idx} className="hover:bg-slate-700/30 transition-colors">
                                                    <td className="px-6 py-4 font-mono text-blue-300">{item.item_code}</td>
                                                    <td className="px-6 py-4">{item.barcode}</td>
                                                    <td className="px-6 py-4">{item.DESCR}</td>
                                                    <td className="px-6 py-4 text-slate-400">{item.DESCR60}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </main>
    );
}
