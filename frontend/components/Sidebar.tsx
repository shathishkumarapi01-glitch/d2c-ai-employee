"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  MessageSquare,
  Plug,
  Brain,
  Store,
  Sparkles,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/chat", label: "AI Chat", icon: MessageSquare },
  { href: "/connectors", label: "Connectors", icon: Plug },
  { href: "/agents", label: "AI Agents", icon: Brain },
  { href: "/merchants", label: "Merchants", icon: Store },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-screen w-64 bg-surface-50 border-r border-surface-300 flex flex-col z-50">
      {/* Logo */}
      <div className="p-6 border-b border-surface-300">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-9 h-9 rounded-lg gradient-brand flex items-center justify-center shadow-lg shadow-brand-500/20 group-hover:shadow-brand-500/40 transition-shadow">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-lg gradient-text">ShipRocket AI</h1>
            <p className="text-[10px] text-gray-500 uppercase tracking-widest">
              D2C Intelligence
            </p>
          </div>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-3 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`
                flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
                transition-all duration-200 group
                ${
                  isActive
                    ? "bg-brand-600/20 text-brand-300 border border-brand-500/20"
                    : "text-gray-400 hover:text-gray-200 hover:bg-surface-200"
                }
              `}
            >
              <Icon
                className={`w-4.5 h-4.5 ${
                  isActive
                    ? "text-brand-400"
                    : "text-gray-500 group-hover:text-gray-300"
                }`}
                size={18}
              />
              {item.label}
              {isActive && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse-slow" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-surface-300">
        <div className="glass rounded-lg p-3">
          <p className="text-xs text-gray-400">
            <span className="text-accent-emerald">●</span> Mock Mode Active
          </p>
          <p className="text-[10px] text-gray-500 mt-1">
            Add API keys for live data
          </p>
        </div>
      </div>
    </aside>
  );
}
