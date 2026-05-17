"use client";

import { useEffect, useState } from "react";
import { fetchMerchants, Merchant } from "@/lib/api";
import MerchantOverview from "@/components/MerchantOverview";
import { Store } from "lucide-react";

export default function MerchantsPage() {
  const [merchants, setMerchants] = useState<Merchant[]>([]);

  useEffect(() => {
    fetchMerchants().then((res) => setMerchants(res.merchants)).catch(console.error);
  }, []);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex items-center gap-3 mb-8 animate-fade-in">
        <div className="w-10 h-10 rounded-xl bg-brand-600/20 flex items-center justify-center">
          <Store className="w-5 h-5 text-brand-400" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-gray-100">Merchants</h1>
          <p className="text-xs text-gray-400">Per-merchant overview and metrics</p>
        </div>
      </div>

      {merchants.length > 0 ? (
        <div className="space-y-8 animate-fade-in">
          {merchants.map((merchant) => (
            <div key={merchant.id} className="glass rounded-xl p-6">
              <MerchantOverview
                merchantId={merchant.id}
                merchantName={merchant.name}
              />
              <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
                <span>Domain: {merchant.domain || "—"}</span>
                <span>Plan: <span className="text-brand-400 capitalize">{merchant.plan}</span></span>
                <span>Since: {new Date(merchant.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="glass rounded-xl p-12 text-center animate-fade-in">
          <Store className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <h3 className="text-gray-300 font-medium mb-2">No Merchants</h3>
          <p className="text-gray-500 text-sm">
            Seed demo data from the dashboard to create sample merchants.
          </p>
        </div>
      )}
    </div>
  );
}
