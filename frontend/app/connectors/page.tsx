"use client";

import { useEffect, useState } from "react";
import { fetchConnectors, fetchMerchants, ConnectorStatus, Merchant } from "@/lib/api";
import ConnectorStatusCard from "@/components/ConnectorStatusCard";
import { Plug, RefreshCw, ChevronDown } from "lucide-react";

export default function ConnectorsPage() {
  const [connectors, setConnectors] = useState<ConnectorStatus[]>([]);
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [selectedMerchant, setSelectedMerchant] = useState<string>("");
  const [showDropdown, setShowDropdown] = useState(false);

  const loadData = async () => {
    try {
      const m = await fetchMerchants();
      setMerchants(m.merchants);
      const storedMerchant = localStorage.getItem("selected_merchant_id");
      const nextMerchant =
        m.merchants.find((merchant) => merchant.id === storedMerchant)?.id ||
        m.merchants[0]?.id ||
        "";
      setSelectedMerchant((current) => current || nextMerchant);
    } catch (e) {
      console.error("Failed to load:", e);
    }
  };

  useEffect(() => { loadData(); }, []);
  useEffect(() => {
    if (!selectedMerchant) return;
    localStorage.setItem("selected_merchant_id", selectedMerchant);
    fetchConnectors(selectedMerchant).then((c) => setConnectors(c.connectors)).catch(console.error);
  }, [selectedMerchant]);

  const currentMerchant = merchants.find((merchant) => merchant.id === selectedMerchant);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-8 animate-fade-in">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-brand-600/20 flex items-center justify-center">
            <Plug className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-100">Connectors</h1>
            <p className="text-xs text-gray-400">Manage data source integrations</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <button
              onClick={() => setShowDropdown((value) => !value)}
              className="glass px-4 py-2 rounded-lg text-sm flex items-center gap-2 hover:border-brand-500/30 transition-all"
            >
              <span className="text-gray-300">{currentMerchant?.name || "Select Merchant"}</span>
              <ChevronDown className="w-4 h-4 text-gray-400" />
            </button>
            {showDropdown && merchants.length > 0 && (
              <div className="absolute right-0 mt-1 w-56 glass rounded-lg overflow-hidden z-50 shadow-xl">
                {merchants.map((merchant) => (
                  <button
                    key={merchant.id}
                    onClick={() => {
                      setSelectedMerchant(merchant.id);
                      setShowDropdown(false);
                    }}
                    className={`w-full text-left px-4 py-2 text-sm hover:bg-surface-200 transition-colors ${
                      merchant.id === selectedMerchant ? "text-brand-400 bg-brand-600/10" : "text-gray-300"
                    }`}
                  >
                    {merchant.name}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button
            onClick={() => selectedMerchant ? fetchConnectors(selectedMerchant).then((c) => setConnectors(c.connectors)) : loadData()}
            className="glass px-3 py-2 rounded-lg text-xs flex items-center gap-2 text-gray-300 hover:border-brand-500/30 transition-all"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 animate-fade-in">
        {connectors.map((connector) => (
          <ConnectorStatusCard
            key={connector.name}
            connector={connector}
            merchantId={selectedMerchant}
            onSyncComplete={() => {
              if (selectedMerchant) {
                fetchConnectors(selectedMerchant).then((c) => setConnectors(c.connectors)).catch(console.error);
              }
            }}
          />
        ))}
      </div>

      {connectors.length === 0 && (
        <div className="text-center text-gray-400 py-12">
          <p>No connectors loaded. Is the backend running?</p>
        </div>
      )}
    </div>
  );
}
