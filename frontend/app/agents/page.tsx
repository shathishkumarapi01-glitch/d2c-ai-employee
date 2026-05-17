"use client";

import { useEffect, useState } from "react";
import { fetchRecommendations, fetchMerchants, AgentRecommendation, Merchant, runAgent } from "@/lib/api";
import AgentRecommendationCard from "@/components/AgentRecommendationCard";
import { Brain, Play, Loader2, RefreshCw } from "lucide-react";

export default function AgentsPage() {
  const [recommendations, setRecommendations] = useState<AgentRecommendation[]>([]);
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [running, setRunning] = useState(false);

  const loadData = async () => {
    try {
      const [r, m] = await Promise.all([fetchRecommendations(), fetchMerchants()]);
      setRecommendations(r.recommendations);
      setMerchants(m.merchants);
    } catch (e) {
      console.error("Failed to load:", e);
    }
  };

  useEffect(() => { loadData(); }, []);

  const handleRunAgent = async () => {
    if (merchants.length === 0 || running) return;
    setRunning(true);
    try {
      await runAgent("ad_spend_analyzer", merchants[0].id);
      await loadData();
    } catch (e) {
      console.error("Agent run failed:", e);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8 animate-fade-in">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-brand-600/20 flex items-center justify-center">
            <Brain className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-100">AI Agent Recommendations</h1>
            <p className="text-xs text-gray-400">Autonomous ad spend analysis and optimization suggestions</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            className="glass px-3 py-2 rounded-lg text-xs flex items-center gap-2 text-gray-300 hover:border-brand-500/30 transition-all"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
          <button
            onClick={handleRunAgent}
            disabled={running || merchants.length === 0}
            className="px-4 py-2 rounded-lg gradient-brand text-white text-xs font-medium flex items-center gap-2
              hover:shadow-lg hover:shadow-brand-500/20 disabled:opacity-50 transition-all"
          >
            {running ? (
              <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Running...</>
            ) : (
              <><Play className="w-3.5 h-3.5" /> Run Agent</>
            )}
          </button>
        </div>
      </div>

      {recommendations.length > 0 ? (
        <div className="space-y-4">
          {recommendations.map((rec) => (
            <AgentRecommendationCard key={rec.id} recommendation={rec} />
          ))}
        </div>
      ) : (
        <div className="glass rounded-xl p-12 text-center animate-fade-in">
          <Brain className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <h3 className="text-gray-300 font-medium mb-2">No Recommendations Yet</h3>
          <p className="text-gray-500 text-sm mb-4">
            Seed demo data and run the ad spend analyzer to generate recommendations.
          </p>
        </div>
      )}
    </div>
  );
}
