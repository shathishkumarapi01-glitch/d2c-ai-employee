"use client";

import { Citation } from "@/lib/api";
import { Database } from "lucide-react";

interface Props {
  citation: Citation;
  index: number;
}

export default function CitationCard({ citation, index }: Props) {
  const platformColors: Record<string, string> = {
    shopify: "text-accent-emerald",
    meta_ads: "text-accent-sky",
    google_sheets: "text-accent-amber",
    razorpay: "text-brand-300",
  };

  const platformBgs: Record<string, string> = {
    shopify: "bg-accent-emerald/10 border-accent-emerald/20",
    meta_ads: "bg-accent-sky/10 border-accent-sky/20",
    google_sheets: "bg-accent-amber/10 border-accent-amber/20",
    razorpay: "bg-brand-500/10 border-brand-500/20",
  };

  const color = platformColors[citation.source_platform] || "text-gray-400";
  const bg = platformBgs[citation.source_platform] || "bg-surface-200 border-surface-300";
  const citationRef = `[source:${citation.source_platform}.${citation.entity_type}.${citation.source_row_id}]`;

  return (
    <div className={`rounded-lg p-2.5 border text-xs ${bg} transition-all hover:scale-[1.02]`}>
      <div className="flex items-center gap-1.5 mb-1">
        <Database className={`w-3 h-3 ${color}`} />
        <span className={`font-medium ${color}`}>
          [{index}]
        </span>
        <span className="text-gray-400 capitalize">
          {citation.source_platform.replace("_", " ")}
        </span>
      </div>
      <div className="text-gray-300 font-mono text-[10px] break-all">
        {citationRef}
      </div>
      {citation.field && (
        <div className="text-gray-500 mt-0.5">
          Field: {citation.field} = {String(citation.value)}
        </div>
      )}
    </div>
  );
}
