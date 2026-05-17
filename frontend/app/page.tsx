"use client";

import { useEffect, useState } from "react";
import { fetchOverview, seedData } from "@/lib/api";
import {
  Store, Package, ShoppingCart, TrendingUp,
  Megaphone, Database, Brain, Loader2, Sparkles, Rocket,
  CheckCircle2, XCircle
} from "lucide-react";

interface Overview {
  merchants: number;
  products: number;
  orders: number;
  total_revenue: number;
  campaigns: number;
  total_ad_spend: number;
  source_records: number;
  agent_recommendations: number;
}

export default function DashboardPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [seeding, setSeeding] = useState(false);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 5000);
  };

  const loadData = async () => {
    try {
      const overview = await fetchOverview();
      setData(overview);
    } catch (e) {
      console.error("Failed to load overview:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const handleSeed = async () => {
    setSeeding(true);
    setToast(null);
    try {
      await seedData();
      await loadData();
      showToast("Demo data seeded successfully!", "success");
    } catch (e) {
      console.error("Seed failed:", e);
      showToast(e instanceof Error ? e.message : "Failed to seed demo data", "error");
    } finally {
      setSeeding(false);
    }
  };

  const metrics = data ? [
    { label: "Merchants", value: data.merchants, icon: Store, color: "text-brand-400", bg: "bg-brand-600/10" },
    { label: "Products", value: data.products, icon: Package, color: "text-accent-sky", bg: "bg-accent-sky/10" },
    { label: "Orders", value: data.orders, icon: ShoppingCart, color: "text-accent-emerald", bg: "bg-accent-emerald/10" },
    { label: "Revenue", value: `₹${data.total_revenue.toLocaleString()}`, icon: TrendingUp, color: "text-accent-emerald", bg: "bg-accent-emerald/10" },
    { label: "Campaigns", value: data.campaigns, icon: Megaphone, color: "text-accent-amber", bg: "bg-accent-amber/10" },
    { label: "Ad Spend", value: `₹${data.total_ad_spend.toLocaleString()}`, icon: Megaphone, color: "text-accent-amber", bg: "bg-accent-amber/10" },
    { label: "Source Records", value: data.source_records, icon: Database, color: "text-gray-400", bg: "bg-gray-500/10" },
    { label: "AI Recommendations", value: data.agent_recommendations, icon: Brain, color: "text-brand-400", bg: "bg-brand-600/10" },
  ] : [];

  return (
    <div className="p-8 max-w-7xl mx-auto relative">
      {/* Toast Notification */}
      {toast && (
        <div className={`fixed bottom-4 right-4 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg animate-fade-in text-sm font-medium text-white
          ${toast.type === 'success' ? 'bg-accent-emerald' : 'bg-red-500'}`}>
          {toast.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
          {toast.message}
        </div>
      )}

      {/* Header */}
      <div className="mb-8 animate-fade-in flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl gradient-brand flex items-center justify-center shadow-lg shadow-brand-500/20">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold gradient-text">Platform Overview</h1>
            <p className="text-sm text-gray-400">ShipRocket AI Employee Platform — D2C Intelligence</p>
          </div>
        </div>
        
        {/* Persistent top-right button when seeded */}
        {data && data.merchants > 0 && (
          <button
            onClick={handleSeed}
            disabled={seeding}
            className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 text-sm font-medium
              disabled:opacity-50 transition-all flex items-center gap-2 border border-gray-700"
          >
            {seeding ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Seeding...</>
            ) : (
              <><Database className="w-4 h-4" /> Reset Demo Data</>
            )}
          </button>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
        </div>
      ) : data && data.merchants === 0 ? (
        /* Seed prompt */
        <div className="glass rounded-2xl p-12 text-center animate-fade-in max-w-lg mx-auto">
          <div className="w-16 h-16 rounded-2xl gradient-brand flex items-center justify-center mx-auto mb-6 shadow-lg shadow-brand-500/20">
            <Rocket className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-xl font-semibold mb-2 text-gray-100">Welcome to ShipRocket AI</h2>
          <p className="text-gray-400 mb-6 text-sm">
            Seed the database with demo merchants, products, orders,
            campaigns, and AI agent recommendations.
          </p>
          <button
            onClick={handleSeed}
            disabled={seeding}
            className="px-6 py-3 rounded-xl gradient-brand text-white font-medium text-sm
              hover:shadow-lg hover:shadow-brand-500/30 disabled:opacity-50 transition-all
              flex items-center gap-2 mx-auto"
          >
            {seeding ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Seeding Data...</>
            ) : (
              <><Sparkles className="w-4 h-4" /> Seed Demo Data</>
            )}
          </button>
        </div>
      ) : (
        /* Metrics grid */
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 animate-fade-in">
          {metrics.map((m, i) => {
            const Icon = m.icon;
            return (
              <div
                key={m.label}
                className="glass rounded-xl p-5 hover:border-brand-500/20 transition-all group"
                style={{ animationDelay: `${i * 50}ms` }}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${m.bg}`}>
                    <Icon className={`w-4.5 h-4.5 ${m.color}`} size={18} />
                  </div>
                </div>
                <p className="text-2xl font-bold text-gray-100">{m.value}</p>
                <p className="text-xs text-gray-400 mt-1">{m.label}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
