"use client";

import { useState } from "react";
import Link from "next/link";

export default function Home() {
  const [projectId, setProjectId] = useState("crown-cdw-intelia-dev");
  const [datasetId, setDatasetId] = useState("");
  const [tableId, setTableId] = useState("");
  const [status, setStatus] = useState<"idle" | "running" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  const handleRunDedup = async () => {
    console.log("Button clicked, triggering dedup...");
    setStatus("running");
    setMessage("Initializing deduplication agent...");

    try {
      console.log(`Fetching: http://localhost:8000/api/dedup/trigger with data:`, { dataset_id: datasetId, table_id: tableId });
      const response = await fetch("http://localhost:8000/api/dedup/trigger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dataset_id: datasetId, table_id: tableId }),
      });

      console.log("Response received status:", response.status);
      const data = await response.json();
      console.log("Response data:", data);
      if (response.ok) {
        setStatus("success");
        setMessage(`Success! Processed ${data.processed_count} records. Results saved to: ${data.output_table} (v: ${data.v})`);
      } else {
        setStatus("error");
        setMessage(`Error: ${data.detail}`);
      }
    } catch (error) {
      setStatus("error");
      setMessage("Failed to connect to backend service.");
    }
  };

  return (
    <main className="min-h-screen bg-slate-900 text-white p-8 font-[family-name:var(--font-geist-sans)]">
      <div className="max-w-4xl mx-auto">
        <header className="mb-12">
          <h1 className="text-5xl font-extrabold bg-gradient-to-r from-blue-400 to-emerald-400 bg-clip-text text-transparent mb-4">
            Dedup Agent
          </h1>
          <p className="text-slate-400 text-lg">
            AI-powered data deduplication with BigQuery integration.
          </p>
        </header>

        <section className="bg-slate-800/50 border border-slate-700 rounded-2xl p-8 backdrop-blur-sm shadow-xl">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Project ID</label>
              <input
                type="text"
                value={projectId}
                disabled
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-3 text-slate-300 cursor-not-allowed"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Dataset ID</label>
              <input
                type="text"
                placeholder="e.g. inventory_data"
                value={datasetId}
                onChange={(e) => setDatasetId(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-3 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition-all"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-400 mb-2">Table ID</label>
              <input
                type="text"
                placeholder="e.g. items_to_dedup"
                value={tableId}
                onChange={(e) => setTableId(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-3 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition-all"
              />
            </div>
          </div>

          <button
            onClick={handleRunDedup}
            disabled={status === "running"}
            className={`w-full py-4 rounded-xl font-bold text-lg transition-all transform active:scale-[0.98] ${status === "running"
              ? "bg-slate-700 cursor-wait"
              : "bg-gradient-to-r from-blue-600 to-emerald-600 hover:from-blue-500 hover:to-emerald-500 shadow-lg shadow-blue-900/20"
              }`}
          >
            {status === "running" ? "Processing..." : "Trigger Deduplication"}
          </button>

          {message && (
            <div className={`mt-6 p-4 rounded-lg border ${status === "success" ? "bg-emerald-900/20 border-emerald-800 text-emerald-400" :
              status === "error" ? "bg-red-900/20 border-red-800 text-red-400" :
                "bg-blue-900/20 border-blue-800 text-blue-400"
              }`}>
              {message}
            </div>
          )}
        </section>

        <section className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-slate-800/30 border border-slate-800 p-6 rounded-xl hover:border-slate-700 transition-colors">
            <h3 className="font-bold mb-2">Review Queue</h3>
            <p className="text-sm text-slate-500 mb-4">Manual review required for low-confidence matches.</p>
            <Link href="/review" className="text-blue-400 hover:text-blue-300 text-sm font-medium">Open Queue →</Link>
          </div>
          <div className="bg-slate-800/30 border border-slate-800 p-6 rounded-xl hover:border-slate-700 transition-colors">
            <h3 className="font-bold mb-2">History</h3>
            <p className="text-sm text-slate-500">View previous deduplication runs and metrics.</p>
          </div>
          <div className="bg-slate-800/30 border border-slate-800 p-6 rounded-xl hover:border-slate-700 transition-colors">
            <h3 className="font-bold mb-2">Settings</h3>
            <p className="text-sm text-slate-500">Configure matching thresholds and AI models.</p>
          </div>
        </section>
      </div>
    </main>
  );
}
