"use client";

import { fetchMerchantDashboard } from "@/lib/api";
import { useEffect, useState } from "react";
import { Package, ShoppingCart, TrendingUp, Megaphone, AlertTriangle, Brain } from "lucide-react";

interface Props {
  merchantId: string;
  merchantName: string;
}

interface DashData {
  total_products: number;
  total_orders: number;
  total_revenue: number;
  total_ad_spend: number;
  active_campaigns: number;
  low_stock_items: number;
  recent_agent_recommendations: number;
}

export default function MerchantOverview({ merchantId, merchantName }: Props) {
  const [data, setData] = useState<DashData | null>(null);

  useEffect(() => {
    fetchMerchantDashboard(merchantId).then(setData).catch(console.error);
  }, [merchantId]);

  if (!data) return <div className="text-gray-500 text-sm">Loading...</div>;

  const metrics = [
    { label: "Products", value: data.total_products, icon: Package, color: "text-brand-400" },
    { label: "Orders", value: data.total_orders, icon: ShoppingCart, color: "text-accent-emerald" },
    { label: "Revenue", value: `₹${data.total_revenue.toLocaleString()}`, icon: TrendingUp, color: "text-accent-emerald" },
    { label: "Ad Spend", value: `₹${data.total_ad_spend.toLocaleString()}`, icon: Megaphone, color: "text-accent-sky" },
    { label: "Active Campaigns", value: data.active_campaigns, icon: Megaphone, color: "text-accent-amber" },
    { label: "Low Stock", value: data.low_stock_items, icon: AlertTriangle, color: "text-accent-rose" },
    { label: "AI Recommendations", value: data.recent_agent_recommendations, icon: Brain, color: "text-brand-400" },
  ];

  return (
    <div>
      <h3 className="text-lg font-semibold mb-3">{merchantName}</h3>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {metrics.map((m) => {
          const Icon = m.icon;
          return (
            <div key={m.label} className="glass rounded-lg p-3 hover:border-brand-500/20 transition-all">
              <div className="flex items-center gap-2 mb-1">
                <Icon className={`w-4 h-4 ${m.color}`} />
                <span className="text-xs text-gray-400">{m.label}</span>
              </div>
              <p className="text-lg font-semibold text-gray-100">{m.value}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
