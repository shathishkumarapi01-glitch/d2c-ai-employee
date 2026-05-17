"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Loader2, Sparkles, History, ArrowRight, TrendingUp, Megaphone, Package, ShoppingCart, Database } from "lucide-react";
import {
  ApiError,
  createChatSession,
  fetchActiveChatSession,
  fetchChatHistory,
  sendChatMessage,
  ChatMessage,
  Citation,
} from "@/lib/api";
import CitationCard from "./CitationCard";

interface Props {
  merchantId: string;
  merchantName?: string;
}

export default function ChatInterface({ merchantId, merchantName }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [activeCitations, setActiveCitations] = useState<Citation[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [sessionStatus, setSessionStatus] = useState<string>("");
  const [restoring, setRestoring] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const requestVersionRef = useRef(0);

  const sessionStorageKey = `chat_session_merchant_${merchantId}`;
  const legacySessionStorageKey = `chat_session_${merchantId}`;
  const followupsStorageKey = `chat_followups_merchant_${merchantId}`;

  const resetChatSurface = () => {
    setMessages([]);
    setActiveCitations([]);
    setSuggestions([]);
  };

  const persistSessionId = (nextSessionId: string) => {
    setSessionId(nextSessionId);
    localStorage.setItem(sessionStorageKey, nextSessionId);
    localStorage.removeItem(legacySessionStorageKey);
  };

  const persistSuggestions = (nextSessionId: string, nextSuggestions: string[]) => {
    if (nextSuggestions.length === 0) {
      localStorage.removeItem(followupsStorageKey);
      return;
    }
    localStorage.setItem(
      followupsStorageKey,
      JSON.stringify({ sessionId: nextSessionId, suggestions: nextSuggestions }),
    );
  };

  const loadStoredSuggestions = (activeSessionId: string, hasAssistantMessage: boolean) => {
    if (!hasAssistantMessage) {
      setSuggestions([]);
      return;
    }

    const raw = localStorage.getItem(followupsStorageKey);
    if (!raw) {
      setSuggestions([]);
      return;
    }

    try {
      const parsed = JSON.parse(raw) as { sessionId?: string; suggestions?: string[] };
      if (parsed.sessionId === activeSessionId && Array.isArray(parsed.suggestions)) {
        setSuggestions(parsed.suggestions.slice(0, 3));
        return;
      }
    } catch {
      localStorage.removeItem(followupsStorageKey);
    }

    setSuggestions([]);
  };

  const getFriendlyErrorMessage = () =>
    "I couldn’t load that merchant conversation cleanly. I’ve reset the chat context, so please try the question again.";

  const getLoadingLabel = (messageText: string) => {
    const msg = messageText.toLowerCase();
    if (msg.includes("campaign") || msg.includes("roas") || msg.includes("spend")) {
      return "Reviewing campaign performance...";
    }
    if (msg.includes("inventory") || msg.includes("stock") || msg.includes("sku")) {
      return "Checking inventory signals...";
    }
    if (msg.includes("refund") || msg.includes("payment")) {
      return "Cross-checking orders and payments...";
    }
    return "Analyzing synced merchant data...";
  };

  const isSessionRecoveryError = (error: unknown) =>
    error instanceof ApiError &&
    [400, 404].includes(error.status) &&
    /session|merchant/i.test(error.detail.toLowerCase());

  const latestAssistantIndex = [...messages]
    .map((msg, index) => ({ msg, index }))
    .reverse()
    .find(({ msg }) => msg.role === "assistant")?.index ?? -1;

  useEffect(() => {
    let cancelled = false;
    requestVersionRef.current += 1;

    const loadSession = async () => {
      setRestoring(true);
      setLoading(false);
      resetChatSurface();
      setSessionId(undefined);
      setSessionStatus(
        merchantName ? `Loading ${merchantName} workspace...` : "Loading merchant workspace..."
      );

      try {
        const activeSession = await fetchActiveChatSession(merchantId);
        if (cancelled) return;
        persistSessionId(activeSession.session_id);

        try {
          const history = await fetchChatHistory(activeSession.session_id, merchantId);
          if (cancelled) return;

          if (history.messages.length > 0) {
            setMessages(history.messages);
            const lastAssistantMsg = [...history.messages].reverse().find(m => m.role === "assistant");
            if (lastAssistantMsg?.citations?.length) {
              setActiveCitations(lastAssistantMsg.citations);
            } else {
              setActiveCitations([]);
            }
            loadStoredSuggestions(activeSession.session_id, Boolean(lastAssistantMsg));
            setSessionStatus(`Restored ${history.messages.length} messages`);
          } else {
            setSessionStatus("Ready to analyze merchant operations");
          }
        } catch (e) {
          console.error("Failed to load chat history:", e);
          localStorage.removeItem(sessionStorageKey);
          localStorage.removeItem(legacySessionStorageKey);
          localStorage.removeItem(followupsStorageKey);
          if (!cancelled) {
            const freshSession = await createChatSession(merchantId);
            if (cancelled) return;
            persistSessionId(freshSession.session_id);
            resetChatSurface();
            setSessionStatus("Ready to analyze merchant operations");
          }
        }
      } catch (e) {
        console.error("Failed to resolve latest session:", e);
        if (!cancelled) {
          setSessionStatus("Ready to analyze merchant operations");
        }
      } finally {
        if (!cancelled) {
          setRestoring(false);
        }
      }
    };

    loadSession();

    return () => {
      cancelled = true;
    };
  }, [merchantId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, suggestions, loading]);

  useEffect(() => {
    if (merchantName) {
      setSessionStatus((current) =>
        current === "Ready to analyze merchant operations" ? `Working in ${merchantName}` : current
      );
    }
  }, [merchantName]);

  const applyAssistantResponse = (
    response: { session_id: string; message: string; citations: Citation[]; suggestions?: string[] },
    requestToken: number,
  ) => {
    if (requestToken !== requestVersionRef.current) return;

    const nextSuggestions = response.suggestions?.slice(0, 3) || [];
    persistSessionId(response.session_id);
    persistSuggestions(response.session_id, nextSuggestions);

    const assistantMessage: ChatMessage = {
      role: "assistant",
      content: response.message,
      citations: response.citations,
      suggestions: nextSuggestions,
    };

    setMessages((prev) => [...prev, assistantMessage]);
    setSuggestions(nextSuggestions);
    setActiveCitations(response.citations?.length > 0 ? response.citations : []);
    setSessionStatus(merchantName ? `Working in ${merchantName}` : "Connected to merchant data");
  };

  const handleSend = async (messageText: string = input) => {
    if (!messageText.trim() || loading || restoring) return;

    const requestToken = requestVersionRef.current;
    const userMessage: ChatMessage = { role: "user", content: messageText };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setSuggestions([]);
    setLoading(true);
    localStorage.removeItem(followupsStorageKey);
    setSessionStatus(getLoadingLabel(messageText));

    try {
      let response = await sendChatMessage(messageText, merchantId, sessionId);

      if (requestToken !== requestVersionRef.current) {
        return;
      }

      applyAssistantResponse(response, requestToken);
    } catch (error: unknown) {
      if (isSessionRecoveryError(error)) {
        try {
          const recoveredSession = await fetchActiveChatSession(merchantId);
          if (requestToken !== requestVersionRef.current) return;
          persistSessionId(recoveredSession.session_id);

          const recoveredResponse = await sendChatMessage(
            messageText,
            merchantId,
            recoveredSession.session_id,
          );

          applyAssistantResponse(recoveredResponse, requestToken);
          return;
        } catch (recoveryError) {
          console.error("Failed to recover merchant chat session:", recoveryError);
        }
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: getFriendlyErrorMessage(),
        },
      ]);
      setSessionStatus(merchantName ? `Working in ${merchantName}` : "Connected to merchant data");
    } finally {
      if (requestToken === requestVersionRef.current) {
        setLoading(false);
      }
    }
  };

  const handleClearHistory = async () => {
    try {
      requestVersionRef.current += 1;
      setRestoring(true);
      setLoading(false);
      const freshSession = await createChatSession(merchantId);
      persistSessionId(freshSession.session_id);
      localStorage.removeItem(followupsStorageKey);
      resetChatSurface();
      setSessionStatus("Started a new merchant conversation");
    } catch (error) {
      console.error("Failed to start a new chat session:", error);
      setSessionStatus(merchantName ? `Working in ${merchantName}` : "Connected to merchant data");
    } finally {
      setRestoring(false);
    }
  };

  const formatContent = (content: string) => {
    let formatted = content.replace(/\*\*(.+?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>');
    formatted = formatted.replace(
      /\[source:([^\]]+)\]/g,
      '<span class="citation-ref inline-flex rounded-md border border-brand-500/20 bg-brand-500/10 px-1.5 py-0.5 text-brand-300" title="Source: $1">[$1]</span>'
    );
    formatted = formatted.replace(/\n/g, "<br/>");
    return formatted;
  };

  const formatCitationRef = (citation: Citation) =>
    `[source:${citation.source_platform}.${citation.entity_type}.${citation.source_row_id}]`;

  return (
    <div className="flex gap-6 h-[calc(100vh-8rem)] relative">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col glass rounded-2xl overflow-hidden border border-surface-300/50 shadow-2xl">
        {/* Header */}
        <div className="px-6 py-4 border-b border-surface-300/50 bg-surface-100/50 flex items-center justify-between backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full gradient-brand flex items-center justify-center shadow-lg shadow-brand-500/20">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-gray-100">AI Business Copilot</h2>
              <p className="text-xs text-gray-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-accent-emerald animate-pulse"></span>
                {sessionStatus || (merchantName ? `Working in ${merchantName}` : "Connected to merchant data")}
              </p>
            </div>
          </div>
          {messages.length > 0 && (
            <button
              onClick={handleClearHistory}
              className="text-xs flex items-center gap-1.5 text-gray-400 hover:text-gray-200 transition-colors px-3 py-1.5 rounded-lg hover:bg-surface-300/50"
            >
              <History className="w-3.5 h-3.5" />
              New Chat
            </button>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {restoring && (
            <div className="max-w-4xl mx-auto mb-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-brand-500/20 bg-brand-500/10 px-3 py-1 text-xs text-brand-200">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Restoring merchant conversation...
              </div>
            </div>
          )}

          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center animate-fade-in px-4">
              <div className="w-20 h-20 rounded-3xl gradient-brand flex items-center justify-center mb-6 shadow-2xl shadow-brand-500/30 ring-1 ring-white/10">
                <Sparkles className="w-10 h-10 text-white" />
              </div>
              <h3 className="text-2xl font-bold text-white mb-3">
                I’m here to help analyze merchant operations
              </h3>
              <p className="text-gray-400 text-sm max-w-md mb-8 leading-relaxed">
                Ask about revenue, campaigns, inventory, refunds, or payments. I’ll use synced merchant data, keep the answer grounded, and show the supporting citations.
              </p>
              
              <div className="w-full max-w-2xl grid grid-cols-1 md:grid-cols-2 gap-3 mt-4 justify-center">
                {[
                  { icon: TrendingUp, text: "What was my revenue last week?" },
                  { icon: Megaphone, text: "Which campaigns have low ROAS?" },
                  { icon: Package, text: "Show low stock items" },
                  { icon: ShoppingCart, text: "Product catalog overview" },
                ].map((suggestion, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSend(suggestion.text)}
                    className="flex items-center gap-3 p-4 rounded-xl glass hover:bg-surface-300/50 text-left transition-all group border border-surface-300/50 hover:border-brand-500/30"
                  >
                    <div className="p-2 rounded-lg bg-surface-300 text-gray-300 group-hover:text-brand-400 group-hover:bg-brand-500/10 transition-colors">
                      <suggestion.icon className="w-4 h-4" />
                    </div>
                    <span className="text-sm font-medium text-gray-300 group-hover:text-white transition-colors">{suggestion.text}</span>
                  </button>
                ))}
              </div>
              <p className="mt-5 text-xs text-gray-500 max-w-lg">
                I won’t answer general trivia or unrelated questions. This workspace is scoped to merchant business intelligence.
              </p>
            </div>
          )}

              {messages.map((msg, i) => (
            <div
              key={msg.id || `${msg.role}-${i}`}
              className={`flex gap-4 animate-slide-up max-w-4xl mx-auto ${
                msg.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              {msg.role === "assistant" && (
                <div className="w-10 h-10 rounded-xl gradient-brand flex items-center justify-center flex-shrink-0 shadow-lg shadow-brand-500/20">
                  <Sparkles className="w-5 h-5 text-white" />
                </div>
              )}
              <div
                className={`max-w-[85%] rounded-2xl px-5 py-4 text-[15px] leading-relaxed shadow-sm ${
                  msg.role === "user"
                    ? "bg-surface-200 text-white rounded-br-sm border border-surface-300/50"
                    : "bg-surface-100 text-gray-200 rounded-bl-sm border border-brand-500/10"
                }`}
              >
                <div
                  className="prose prose-invert max-w-none"
                  dangerouslySetInnerHTML={{
                    __html: formatContent(msg.content),
                  }}
                />
                
                {msg.role === "assistant" && msg.citations && msg.citations.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-surface-300/50 flex items-start gap-2">
                    <Database className="w-3.5 h-3.5 text-brand-400 mt-0.5 flex-shrink-0" />
                    <div className="flex flex-wrap gap-1.5">
                      {msg.citations.slice(0, 3).map((c, j) => (
                        <span
                          key={j}
                          className="text-[10px] px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-300 border border-brand-500/20 font-mono break-all"
                          title={formatCitationRef(c)}
                        >
                          {formatCitationRef(c)}
                        </span>
                      ))}
                      {msg.citations.length > 3 && (
                        <span className="text-[10px] text-gray-500 flex items-center">
                          +{msg.citations.length - 3} more
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {msg.role === "assistant" && i === latestAssistantIndex && suggestions.length > 0 && !loading && (
                  <div className="mt-4 pt-4 border-t border-surface-300/50">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-gray-500 mb-2">
                      Suggested next questions
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {suggestions.map((suggestion, idx) => (
                        <button
                          key={`${suggestion}-${idx}`}
                          onClick={() => handleSend(suggestion)}
                          className="text-sm text-left px-3.5 py-2 rounded-full bg-surface-200 hover:bg-surface-300 text-gray-300 hover:text-white transition-all border border-surface-300/50 hover:border-brand-500/30 flex items-center gap-2 group"
                        >
                          <ArrowRight className="w-3.5 h-3.5 text-brand-400 opacity-70 group-hover:opacity-100 transition-opacity" />
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              {msg.role === "user" && (
                <div className="w-10 h-10 rounded-xl bg-surface-300 flex items-center justify-center flex-shrink-0 border border-surface-400/30">
                  <User className="w-5 h-5 text-gray-300" />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex gap-4 animate-slide-up max-w-4xl mx-auto">
              <div className="w-10 h-10 rounded-xl gradient-brand flex items-center justify-center flex-shrink-0 shadow-lg shadow-brand-500/20">
                <Bot className="w-5 h-5 text-white animate-pulse" />
              </div>
              <div className="bg-surface-100 border border-brand-500/10 rounded-2xl rounded-bl-sm px-5 py-4">
                <div className="flex items-center gap-3 text-brand-300 font-medium text-sm">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 bg-brand-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }}></span>
                    <span className="w-1.5 h-1.5 bg-brand-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></span>
                    <span className="w-1.5 h-1.5 bg-brand-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></span>
                  </div>
                  Analyzing your data...
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-surface-100/50 backdrop-blur-md border-t border-surface-300/50">
          <div className="max-w-4xl mx-auto relative flex items-center">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder={`Ask about ${merchantName || "this merchant"}: revenue, campaigns, inventory, refunds...`}
              className="flex-1 bg-surface-200 border border-surface-300/80 text-white placeholder-gray-500 rounded-2xl pl-5 pr-14 py-4 text-[15px] focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-transparent transition-all shadow-inner"
            />
            <button
              onClick={() => handleSend()}
              disabled={loading || restoring || !input.trim()}
              className="absolute right-2 w-10 h-10 rounded-xl gradient-brand flex items-center justify-center text-white disabled:opacity-50 hover:shadow-lg hover:shadow-brand-500/30 transition-all disabled:hover:shadow-none"
            >
              <Send className="w-4 h-4 ml-0.5" />
            </button>
          </div>
          <div className="text-center mt-3">
             <p className="text-[11px] text-gray-500">Responses stay inside merchant operations and are grounded in synced records only.</p>
          </div>
        </div>
      </div>

      {/* Citations Sidebar */}
      {activeCitations.length > 0 && (
        <div className="w-80 glass rounded-2xl p-5 overflow-y-auto animate-fade-in border border-surface-300/50 shadow-2xl flex flex-col">
          <div className="flex items-center gap-2 mb-4 pb-4 border-b border-surface-300/50">
            <div className="w-8 h-8 rounded-lg bg-accent-emerald/10 flex items-center justify-center">
               <Database className="w-4 h-4 text-accent-emerald" />
            </div>
            <div>
               <h3 className="text-sm font-semibold text-white">Active Citations</h3>
               <p className="text-[11px] text-gray-400">Sources for the latest response</p>
            </div>
          </div>
          
          <div className="space-y-3 flex-1 overflow-y-auto pr-1 custom-scrollbar">
            {activeCitations.map((citation, i) => (
              <CitationCard key={i} citation={citation} index={i + 1} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
