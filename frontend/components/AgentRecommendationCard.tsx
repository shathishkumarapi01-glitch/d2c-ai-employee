"use client";

import { AgentRecommendation } from "@/lib/api";
import {
  Brain,
  TrendingDown,
  AlertTriangle,
  Clock,
  DollarSign,
} from "lucide-react";

interface Props {
  recommendation: AgentRecommendation;
}

export default function AgentRecommendationCard({
  recommendation: rec,
}: Props) {
  const severityConfig: Record<
    string,
    { color: string; bg: string; icon: any }
  > = {
    critical: {
      color: "text-accent-rose",
      bg: "bg-accent-rose/10 border-accent-rose/20",
      icon: AlertTriangle,
    },
    high: {
      color: "text-accent-amber",
      bg: "bg-accent-amber/10 border-accent-amber/20",
      icon: TrendingDown,
    },
    medium: {
      color: "text-accent-sky",
      bg: "bg-accent-sky/10 border-accent-sky/20",
      icon: Brain,
    },
  };

  const statusConfig: Record<string, { color: string; label: string }> = {
    pending: { color: "text-accent-amber", label: "Pending Review" },
    reviewed: { color: "text-accent-sky", label: "Reviewed" },
    accepted: { color: "text-accent-emerald", label: "Accepted" },
    dismissed: { color: "text-gray-500", label: "Dismissed" },
  };

  const severity = rec.metadata_extra?.severity || "medium";
  const sConfig = severityConfig[severity] || severityConfig.medium;
  const stConfig = statusConfig[rec.status] || statusConfig.pending;
  const SeverityIcon = sConfig.icon;

  return (
    <div className="glass rounded-xl p-5 hover:border-brand-500/20 transition-all animate-slide-up">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div
            className={`w-9 h-9 rounded-lg flex items-center justify-center ${sConfig.bg} border`}
          >
            <SeverityIcon className={`w-4 h-4 ${sConfig.color}`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                {rec.agent_type.replace(/_/g, " ")}
              </span>
              <span className={`text-xs ${sConfig.color} uppercase`}>
                {severity}
              </span>
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <Clock className="w-3 h-3 text-gray-500" />
              <span className="text-xs text-gray-500">
                {new Date(rec.created_at).toLocaleString()}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <span className={`text-xs ${stConfig.color}`}>{stConfig.label}</span>
        </div>
      </div>

      {/* Recommendation */}
      <div className="mb-3">
        <p
          className="text-sm text-gray-200 leading-relaxed"
          dangerouslySetInnerHTML={{
            __html: rec.recommendation.replace(
              /\*\*(.+?)\*\*/g,
              "<strong>$1</strong>"
            ),
          }}
        />
      </div>

      {/* Reasoning (collapsed) */}
      <details className="mb-3">
        <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-300 transition-colors">
          View reasoning chain
        </summary>
        <p className="text-xs text-gray-400 mt-2 leading-relaxed pl-3 border-l-2 border-surface-300">
          {rec.reasoning}
        </p>
      </details>

      {/* Metrics row */}
      <div className="flex items-center gap-4 pt-3 border-t border-surface-300">
        {rec.estimated_savings != null && (
          <div className="flex items-center gap-1.5">
            <DollarSign className="w-3.5 h-3.5 text-accent-emerald" />
            <span className="text-xs text-gray-300">
              Save ₹{rec.estimated_savings.toLocaleString()}
            </span>
          </div>
        )}
        <div className="flex items-center gap-1.5">
          <div className="w-12 h-1.5 rounded-full bg-surface-300 overflow-hidden">
            <div
              className="h-full rounded-full bg-brand-500"
              style={{ width: `${rec.confidence_score * 100}%` }}
            />
          </div>
          <span className="text-xs text-gray-400">
            {(rec.confidence_score * 100).toFixed(0)}% confidence
          </span>
        </div>
        {rec.citations?.length > 0 && (
          <div className="flex items-center gap-1">
            <span className="text-xs text-gray-500">
              {rec.citations.length} source
              {rec.citations.length > 1 ? "s" : ""}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
