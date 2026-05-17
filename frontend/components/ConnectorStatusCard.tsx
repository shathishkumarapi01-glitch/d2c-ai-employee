"use client";

import { useState } from "react";
import { ConnectorStatus, syncConnector } from "@/lib/api";
import { RefreshCw, Plug, CheckCircle, AlertCircle, Loader2, Cpu } from "lucide-react";

interface Props {
  connector: ConnectorStatus;
  merchantId?: string;
  onSyncComplete?: () => void;
}

export default function ConnectorStatusCard({ connector, merchantId, onSyncComplete }: Props) {
  const [syncing, setSyncing] = useState(false);

  const handleSync = async () => {
    if (!merchantId || syncing) return;
    setSyncing(true);
    try {
      await syncConnector(connector.name, merchantId);
      onSyncComplete?.();
    } catch (error) {
      console.error("Sync failed:", error);
    } finally {
      setSyncing(false);
    }
  };

  const statusConfig: Record<string, { icon: any; color: string; bg: string; label: string }> = {
    healthy: { icon: CheckCircle, color: "text-accent-emerald", bg: "bg-accent-emerald/10 border-accent-emerald/20", label: "Connected" },
    mock: { icon: Cpu, color: "text-accent-amber", bg: "bg-accent-amber/10 border-accent-amber/20", label: "Mock Mode" },
    degraded: { icon: AlertCircle, color: "text-accent-amber", bg: "bg-accent-amber/10 border-accent-amber/20", label: "Degraded" },
    error: { icon: AlertCircle, color: "text-accent-rose", bg: "bg-accent-rose/10 border-accent-rose/20", label: "Error" },
  };

  const config = statusConfig[connector.status] || statusConfig.error;
  const StatusIcon = config.icon;

  const platformNames: Record<string, string> = {
    shopify: "Shopify",
    meta_ads: "Meta Ads",
    google_sheets: "Google Sheets",
    razorpay: "Razorpay",
  };

  const platformDescriptions: Record<string, string> = {
    shopify: "Orders, products, inventory sync",
    meta_ads: "Campaign performance metrics",
    google_sheets: "Custom data imports",
    razorpay: "Payments and refund records",
  };

  return (
    <div className="glass rounded-xl p-5 hover:border-brand-500/30 transition-all group">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${config.bg} border`}>
            <Plug className={`w-5 h-5 ${config.color}`} />
          </div>
          <div>
            <h3 className="font-semibold text-gray-100 text-sm">
              {platformNames[connector.name] || connector.name}
            </h3>
            <p className="text-xs text-gray-500">
              {platformDescriptions[connector.name] || "Data connector"}
            </p>
          </div>
        </div>
        <div className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs ${config.bg} border`}>
          <StatusIcon className={`w-3 h-3 ${config.color}`} />
          <span className={config.color}>{config.label}</span>
        </div>
      </div>

      <div className="space-y-2 mb-4">
        <div className="flex justify-between text-xs">
          <span className="text-gray-400">Last Sync</span>
          <span className="text-gray-300">
            {connector.last_sync
              ? new Date(connector.last_sync).toLocaleString()
              : "Never"}
          </span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-gray-400">Synced Records</span>
          <span className="text-gray-300">{connector.records_synced}</span>
        </div>
        {connector.mock_mode && (
          <div className="flex justify-between text-xs">
            <span className="text-gray-400">Mode</span>
            <span className="text-accent-amber">Mock (no API key)</span>
          </div>
        )}
      </div>

      {merchantId && (
        <button
          onClick={handleSync}
          disabled={syncing}
          className="w-full py-2 rounded-lg text-xs font-medium flex items-center justify-center gap-2 
            bg-surface-200 text-gray-300 hover:bg-surface-300 hover:text-gray-100 
            disabled:opacity-50 transition-all"
        >
          {syncing ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <RefreshCw className="w-3.5 h-3.5" />
          )}
          {syncing ? "Syncing..." : "Sync Now"}
        </button>
      )}
    </div>
  );
}
