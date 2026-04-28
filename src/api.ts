const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export type ViewerInfo = {
  authenticated: boolean;
  owner_id: string;
  guest_id: string;
  api_key_source: 'managed' | 'manual' | 'manual_override';
  user: {
    id: number;
    email: string;
    username: string;
    role: string;
  } | null;
};

export type AuthKeyGroup = {
  id: string;
  name: string;
  platform: string;
};

export type AuthKeyGroupsResult = {
  items: AuthKeyGroup[];
  selected_group_id: string;
  create_group_url: string;
};

export type AppConfig = {
  owner_id: string;
  model: string;
  default_size: string;
  default_quality: string;
  user_name: string;
  managed_by_auth: boolean;
  api_key_set: boolean;
  api_key_hint: string;
  api_key_source: 'managed' | 'manual' | 'manual_override';
  api_key_editable: boolean;
  authenticated: boolean;
};

export type HistoryItem = {
  id: string;
  owner_id: string;
  mode: 'generate' | 'edit';
  prompt: string;
  model: string;
  size: string;
  aspect_ratio: string;
  quality: string;
  status: 'succeeded' | 'failed';
  image_url: string | null;
  image_path: string | null;
  input_image_url: string | null;
  input_image_path: string | null;
  revised_prompt: string | null;
  usage: Record<string, unknown> | null;
  provider_response: Record<string, unknown> | null;
  error: string | null;
  published: boolean;
  published_case_id: string | null;
  published_inspiration_id: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ImageTask = {
  id: string;
  owner_id: string;
  mode: 'generate' | 'edit';
  prompt: string;
  model: string;
  size: string;
  aspect_ratio: string;
  quality: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  error: string | null;
  items: HistoryItem[];
  result: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type CaseItem = {
  id: string;
  owner_id: string;
  history_id: string | null;
  title: string;
  author: string | null;
  prompt: string;
  image_url: string | null;
  image_path: string | null;
  model: string;
  size: string;
  aspect_ratio: string;
  quality: string;
  status: 'visible' | 'hidden' | 'deleted';
  source_type: 'user_history' | 'admin_manual';
  created_by_admin: boolean;
  like_count: number;
  comment_count: number;
  liked: boolean;
  created_at: string;
  updated_at: string;
};

export type CaseComment = {
  id: string;
  case_id: string;
  owner_id: string;
  author: string | null;
  body: string;
  status: 'visible' | 'hidden' | 'deleted';
  case_title?: string;
  can_edit: boolean;
  can_delete: boolean;
  created_at: string;
  updated_at: string;
};

export type CaseStats = {
  total: number;
  user_cases: number;
  admin_cases: number;
  likes: number;
  comments: number;
  last_case_at: string | null;
};

export type CaseSort = 'latest' | 'likes' | 'comments';

export type CaseListResponse = {
  items: CaseItem[];
  total: number;
  limit: number;
  offset: number;
  sort: CaseSort;
};

export type BalanceInfo = {
  ok: boolean;
  remaining: number | null;
  message?: string;
  raw: Record<string, unknown> | null;
};

export type AccountInfo = {
  viewer: ViewerInfo;
  user: {
    name: string;
    email: string | null;
    username: string | null;
    role: string | null;
    authenticated: boolean;
    guest: boolean;
    api_key_set: boolean;
    api_key_source: 'managed' | 'manual' | 'manual_override';
    model: string;
  };
  balance: BalanceInfo;
  stats: {
    total: number;
    succeeded: number;
    edits: number;
    last_generation_at: string | null;
  };
};

export type LedgerEntry = {
  id: string;
  owner_id: string;
  event_type: string;
  amount: number;
  currency: string;
  description: string;
  history_id: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
};

export type GeneratePayload = {
  prompt: string;
  model?: string;
  size?: string;
  aspect_ratio?: string;
  quality?: string;
  n?: number;
};

export type PublicAuthSettings = {
  registration_enabled: boolean;
  email_verify_enabled: boolean;
  force_email_on_third_party_signup: boolean;
  promo_code_enabled: boolean;
  invitation_code_enabled: boolean;
  totp_enabled: boolean;
  turnstile_enabled: boolean;
  turnstile_site_key: string;
  backend_mode_enabled: boolean;
  site_name: string;
  site_subtitle: string;
};

export type SiteSettings = {
  default_locale: 'zh-CN' | 'en-US' | string;
  announcement: {
    enabled: boolean;
    title: string;
    body: string;
    updated_at: string | null;
  };
  upstream?: {
    provider_base_url: string;
    auth_base_url: string;
    effective_provider_base_url: string;
    effective_auth_base_url: string;
  };
  image_retention: {
    days: number;
  };
  viewer: {
    authenticated: boolean;
    is_admin: boolean;
  };
};

export type LoginResult = {
  ok: boolean;
  viewer?: ViewerInfo;
  requires_2fa?: boolean;
  temp_token?: string;
  user_email_masked?: string;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    ...options,
    headers: {
      ...(options?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(options?.headers || {}),
    },
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = data?.detail || data?.message || response.statusText;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data as T;
}

export function getSession() {
  return request<ViewerInfo>('/api/auth/session');
}

export function getSiteSettings() {
  return request<SiteSettings>('/api/site-settings');
}

export function updateSiteSettings(payload: {
  default_locale?: 'zh-CN' | 'en-US';
  announcement_enabled?: boolean;
  announcement_title?: string;
  announcement_body?: string;
  provider_base_url?: string;
  auth_base_url?: string;
}) {
  return request<SiteSettings>('/api/site-settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function getAuthPublicSettings() {
  return request<PublicAuthSettings>('/api/auth/public-settings');
}

export function sendVerifyCode(payload: { email: string; turnstile_token?: string }) {
  return request<{ message: string; countdown: number }>('/api/auth/send-verify-code', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function registerAccount(payload: {
  email: string;
  password: string;
  verify_code?: string;
  turnstile_token?: string;
  promo_code?: string;
  invitation_code?: string;
}) {
  return request<LoginResult>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function loginAccount(payload: { email: string; password: string; turnstile_token?: string }) {
  return request<LoginResult>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function loginAccount2FA(payload: { temp_token: string; totp_code: string }) {
  return request<LoginResult>('/api/auth/login/2fa', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function logoutAccount() {
  return request<{ ok: boolean }>('/api/auth/logout', {
    method: 'POST',
    body: JSON.stringify({}),
  });
}

export function getAuthKeyGroups() {
  return request<AuthKeyGroupsResult>('/api/auth/key-groups');
}

export function selectAuthKeyGroup(groupId: string) {
  return request<{ ok: boolean; group: AuthKeyGroup; config: AppConfig }>('/api/auth/key-groups/select', {
    method: 'POST',
    body: JSON.stringify({ group_id: groupId }),
  });
}

export function getConfig() {
  return request<AppConfig>('/api/config');
}

export function saveConfig(config: Partial<AppConfig> & { api_key?: string; clear_api_key?: boolean }) {
  return request<AppConfig>('/api/config', {
    method: 'PUT',
    body: JSON.stringify(config),
  });
}

export function testConfig() {
  return request<{ ok: boolean; models: string[] }>('/api/config/test', { method: 'POST' });
}

export function getAccount() {
  return request<AccountInfo>('/api/account');
}

export function getBalance() {
  return request<BalanceInfo>('/api/balance');
}

export function getLedger(limit = 20) {
  return request<{ items: LedgerEntry[] }>(`/api/ledger?limit=${limit}`);
}

export function getHistory(params: { limit?: number; offset?: number; q?: string } = {}) {
  const search = new URLSearchParams();
  if (params.limit) search.set('limit', String(params.limit));
  if (params.offset) search.set('offset', String(params.offset));
  if (params.q) search.set('q', params.q);
  const query = search.toString();
  return request<{ items: HistoryItem[] }>(`/api/history${query ? `?${query}` : ''}`);
}

export function getCases(params: { limit?: number; offset?: number; q?: string; sort?: CaseSort } = {}) {
  const search = new URLSearchParams();
  if (params.limit) search.set('limit', String(params.limit));
  if (params.offset) search.set('offset', String(params.offset));
  if (params.q) search.set('q', params.q);
  if (params.sort) search.set('sort', params.sort);
  const query = search.toString();
  return request<CaseListResponse>(`/api/cases${query ? `?${query}` : ''}`);
}

export function getCaseStats() {
  return request<CaseStats>('/api/cases/stats');
}

export function getCase(id: string) {
  return request<CaseItem>(`/api/cases/${id}`);
}

export function likeCase(id: string) {
  return request<CaseItem>(`/api/cases/${id}/like`, { method: 'POST', body: JSON.stringify({}) });
}

export function unlikeCase(id: string) {
  return request<CaseItem>(`/api/cases/${id}/like`, { method: 'DELETE' });
}

export function getCaseComments(id: string) {
  return request<{ items: CaseComment[] }>(`/api/cases/${id}/comments`);
}

export function createCaseComment(id: string, body: string) {
  return request<CaseComment>(`/api/cases/${id}/comments`, { method: 'POST', body: JSON.stringify({ body }) });
}

export function updateCaseComment(id: string, payload: { body?: string; status?: 'visible' | 'hidden' | 'deleted' }) {
  return request<CaseComment>(`/api/comments/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
}

export function deleteCaseComment(id: string) {
  return request<CaseComment>(`/api/comments/${id}`, { method: 'DELETE' });
}

export function listAdminCases(params: { limit?: number; offset?: number; q?: string } = {}) {
  const search = new URLSearchParams();
  if (params.limit) search.set('limit', String(params.limit));
  if (params.offset) search.set('offset', String(params.offset));
  if (params.q) search.set('q', params.q);
  const query = search.toString();
  return request<{ items: CaseItem[] }>(`/api/admin/cases${query ? `?${query}` : ''}`);
}

export function createAdminCase(payload: Partial<CaseItem> & { title: string; prompt: string }) {
  return request<CaseItem>('/api/admin/cases', { method: 'POST', body: JSON.stringify(payload) });
}

export function updateAdminCase(id: string, payload: Partial<CaseItem>) {
  return request<CaseItem>(`/api/admin/cases/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
}

export function deleteAdminCase(id: string) {
  return request<CaseItem>(`/api/admin/cases/${id}`, { method: 'DELETE' });
}

export function createAdminComment(payload: {
  case_id: string;
  body: string;
  author?: string;
  status?: 'visible' | 'hidden' | 'deleted';
}) {
  return request<CaseComment>('/api/admin/comments', { method: 'POST', body: JSON.stringify(payload) });
}

export function listAdminComments(params: { limit?: number; offset?: number } = {}) {
  const search = new URLSearchParams();
  if (params.limit) search.set('limit', String(params.limit));
  if (params.offset) search.set('offset', String(params.offset));
  const query = search.toString();
  return request<{ items: CaseComment[] }>(`/api/admin/comments${query ? `?${query}` : ''}`);
}

export function deleteHistory(id: string) {
  return request<{ ok: boolean }>(`/api/history/${id}`, { method: 'DELETE' });
}

export function publishHistory(id: string) {
  return request<{ ok: boolean; item: HistoryItem; case: CaseItem }>(`/api/history/${id}/publish`, {
    method: 'POST',
  });
}

export function unpublishHistory(id: string) {
  return request<{ ok: boolean; item: HistoryItem }>(`/api/history/${id}/publish`, { method: 'DELETE' });
}

export function generateImage(payload: GeneratePayload) {
  return request<ImageTask>('/api/images/generate', {
    method: 'POST',
    body: JSON.stringify({ n: 1, ...payload }),
  });
}

export function editImage(payload: GeneratePayload, images: File | File[]) {
  const form = new FormData();
  const imageList = Array.isArray(images) ? images : [images];
  form.set('prompt', payload.prompt);
  if (payload.model) form.set('model', payload.model);
  if (payload.size) form.set('size', payload.size);
  if (payload.aspect_ratio) form.set('aspect_ratio', payload.aspect_ratio);
  if (payload.quality) form.set('quality', payload.quality);
  form.set('n', String(payload.n || 1));
  imageList.forEach((image) => form.append('image', image));
  return request<ImageTask>('/api/images/edit', {
    method: 'POST',
    body: form,
  });
}

export function getImageTask(taskId: string) {
  return request<ImageTask>(`/api/tasks/${taskId}`);
}

export function listImageTasks(params: { limit?: number; status?: string[] } = {}) {
  const search = new URLSearchParams();
  if (params.limit) search.set('limit', String(params.limit));
  if (params.status && params.status.length > 0) search.set('status', params.status.join(','));
  const query = search.toString();
  return request<{ items: ImageTask[] }>(`/api/tasks${query ? `?${query}` : ''}`);
}

export async function waitForImageTask(
  taskId: string,
  options: {
    intervalMs?: number;
    timeoutMs?: number;
    onUpdate?: (task: ImageTask) => void;
  } = {},
) {
  const intervalMs = options.intervalMs ?? 1500;
  const timeoutMs = options.timeoutMs ?? 15 * 60 * 1000;
  const startedAt = Date.now();

  while (true) {
    const task = await getImageTask(taskId);
    options.onUpdate?.(task);
    if (task.status === 'succeeded' || task.status === 'failed') {
      return task;
    }
    if (Date.now() - startedAt >= timeoutMs) {
      throw new Error('Image task polling timed out');
    }
    await new Promise((resolve) => window.setTimeout(resolve, intervalMs));
  }
}

export function formatBalance(balance: BalanceInfo | undefined) {
  if (!balance || balance.remaining === null || Number.isNaN(balance.remaining)) {
    return '--';
  }
  return balance.remaining.toFixed(4);
}

export function formatDate(value: string | null | undefined) {
  if (!value) return '--';
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}
