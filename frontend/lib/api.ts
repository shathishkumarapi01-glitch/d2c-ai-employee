/**
 * API client for the ShipRocket backend.
 * Centralizes all HTTP calls with error handling.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3005';

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });

  if (!res.ok) {
    const raw = await res.text();
    let detail = raw;

    try {
      const parsed = JSON.parse(raw);
      detail = parsed.detail || raw;
    } catch {
      detail = raw;
    }

    throw new ApiError(res.status, detail || `Request failed with status ${res.status}`);
  }

  return res.json();
}

// ── Dashboard ────────────────────────────────────────────
export async function fetchOverview() {
  return apiFetch<{
    merchants: number;
    products: number;
    orders: number;
    total_revenue: number;
    campaigns: number;
    total_ad_spend: number;
    source_records: number;
    agent_recommendations: number;
  }>('/api/v1/dashboard/overview');
}

export async function seedData() {
  return apiFetch<any>('/api/v1/dashboard/seed', { method: 'POST' });
}

// ── Merchants ────────────────────────────────────────────
export interface Merchant {
  id: string;
  name: string;
  domain: string | null;
  plan: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export async function fetchMerchants() {
  return apiFetch<{ merchants: Merchant[]; total: number }>('/api/v1/merchants');
}

export async function fetchMerchantDashboard(merchantId: string) {
  return apiFetch<{
    merchant_id: string;
    merchant_name: string;
    total_products: number;
    total_orders: number;
    total_revenue: number;
    total_ad_spend: number;
    active_campaigns: number;
    low_stock_items: number;
    recent_agent_recommendations: number;
  }>(`/api/v1/merchants/${merchantId}/dashboard`);
}

// ── Connectors ───────────────────────────────────────────
export interface ConnectorStatus {
  name: string;
  status: string;
  mock_mode: boolean;
  last_sync: string | null;
  error: string | null;
  records_synced: number;
}

export async function fetchConnectors(merchantId?: string) {
  const params = merchantId ? `?merchant_id=${merchantId}` : '';
  return apiFetch<{ connectors: ConnectorStatus[] }>(`/api/v1/connectors${params}`);
}

export async function syncConnector(name: string, merchantId: string) {
  return apiFetch<any>(`/api/v1/connectors/${name}/sync`, {
    method: 'POST',
    body: JSON.stringify({ merchant_id: merchantId }),
  });
}

// ── Chat ─────────────────────────────────────────────────
export interface Citation {
  source_platform: string;
  entity_type: string;
  source_row_id: string;
  field?: string;
  value?: any;
}

export interface ChatMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  suggestions?: string[];
  created_at?: string;
}

export interface ChatResponse {
  session_id: string;
  message: string;
  citations: Citation[];
  tool_calls_made: any[] | null;
  has_uncited_numbers: boolean;
  suggestions?: string[];
}

export async function sendChatMessage(message: string, merchantId: string, sessionId?: string) {
  return apiFetch<ChatResponse>('/api/v1/chat', {
    method: 'POST',
    body: JSON.stringify({
      message,
      merchant_id: merchantId,
      session_id: sessionId,
    }),
  });
}

export async function fetchChatHistory(sessionId: string, merchantId: string) {
  return apiFetch<{ session_id: string; merchant_id: string; messages: ChatMessage[] }>(
    `/api/v1/chat/history/${sessionId}?merchant_id=${merchantId}`
  );
}

export async function fetchActiveChatSession(merchantId: string) {
  return apiFetch<{
    session_id: string;
    merchant_id: string;
    title: string | null;
    updated_at: string;
    message_count: number;
  }>(`/api/v1/chat/sessions/active/${merchantId}`);
}

export async function fetchLatestChatSession(merchantId: string) {
  return apiFetch<{
    session_id: string;
    merchant_id: string;
    title: string | null;
    updated_at: string;
    message_count: number;
  } | null>(`/api/v1/chat/sessions/latest/${merchantId}`);
}

export async function createChatSession(merchantId: string) {
  return apiFetch<{
    session_id: string;
    merchant_id: string;
    title: string | null;
    updated_at: string;
    message_count: number;
  }>('/api/v1/chat/sessions', {
    method: 'POST',
    body: JSON.stringify({ merchant_id: merchantId }),
  });
}

// ── Agents ───────────────────────────────────────────────
export interface AgentRecommendation {
  id: string;
  merchant_id: string;
  agent_type: string;
  trigger: string;
  reasoning: string;
  recommendation: string;
  estimated_savings: number | null;
  confidence_score: number;
  citations: any[];
  status: string;
  metadata_extra?: Record<string, any> | null;
  created_at: string;
}

export async function fetchRecommendations(merchantId?: string) {
  const params = merchantId ? `?merchant_id=${merchantId}` : '';
  return apiFetch<{ recommendations: AgentRecommendation[]; total: number }>(
    `/api/v1/agents/recommendations${params}`
  );
}

export async function runAgent(agentType: string, merchantId: string) {
  return apiFetch<any>(`/api/v1/agents/run/${agentType}`, {
    method: 'POST',
    body: JSON.stringify({ merchant_id: merchantId, agent_type: agentType }),
  });
}
