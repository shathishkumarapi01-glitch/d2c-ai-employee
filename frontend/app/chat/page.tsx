"use client";

import { useEffect, useState } from "react";
import { fetchMerchants, Merchant } from "@/lib/api";
import ChatInterface from "@/components/ChatInterface";
import { MessageSquare, ChevronDown } from "lucide-react";

export default function ChatPage() {
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [selectedMerchant, setSelectedMerchant] = useState<string>("");
  const [showDropdown, setShowDropdown] = useState(false);

  useEffect(() => {
    fetchMerchants().then((res) => {
      setMerchants(res.merchants);
      if (res.merchants.length > 0) {
        const storedMerchant = localStorage.getItem("selected_merchant_id");
        const nextMerchant =
          res.merchants.find((merchant) => merchant.id === storedMerchant)?.id ||
          res.merchants[0].id;
        setSelectedMerchant(nextMerchant);
      }
    }).catch(console.error);
  }, []);

  useEffect(() => {
    if (selectedMerchant) {
      localStorage.setItem("selected_merchant_id", selectedMerchant);
    }
  }, [selectedMerchant]);

  const currentMerchant = merchants.find((m) => m.id === selectedMerchant);

  return (
    <div className="p-8 max-w-7xl mx-auto h-screen flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 animate-fade-in">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-brand-600/20 flex items-center justify-center">
            <MessageSquare className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-100">AI Chat</h1>
            <p className="text-xs text-gray-400">Citation-grounded business intelligence</p>
          </div>
        </div>

        {/* Merchant selector */}
        <div className="relative">
          <button
            onClick={() => setShowDropdown(!showDropdown)}
            className="glass px-4 py-2 rounded-lg text-sm flex items-center gap-2 hover:border-brand-500/30 transition-all"
          >
            <span className="text-gray-300">
              {currentMerchant?.name || "Select Merchant"}
            </span>
            <ChevronDown className="w-4 h-4 text-gray-400" />
          </button>
          {showDropdown && merchants.length > 0 && (
            <div className="absolute right-0 mt-1 w-48 glass rounded-lg overflow-hidden z-50 shadow-xl">
              {merchants.map((m) => (
                <button
                  key={m.id}
                  onClick={() => { setSelectedMerchant(m.id); setShowDropdown(false); }}
                  className={`w-full text-left px-4 py-2 text-sm hover:bg-surface-200 transition-colors
                    ${m.id === selectedMerchant ? "text-brand-400 bg-brand-600/10" : "text-gray-300"}`}
                >
                  {m.name}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Chat */}
      {selectedMerchant ? (
        <div className="flex-1 min-h-0">
          <ChatInterface
            merchantId={selectedMerchant}
            merchantName={currentMerchant?.name}
          />
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-gray-400">
            No merchants found. Seed demo data from the dashboard first.
          </p>
        </div>
      )}
    </div>
  );
}
