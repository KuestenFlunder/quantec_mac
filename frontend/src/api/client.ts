import type {
  Client,
  ClientCreate,
  ClientUpdate,
  Target,
  TargetCreate,
  TargetUpdate,
  HealingSheet,
  HealingSheetCreate,
  HealingSheetUpdate,
  HealingSheetItem,
  HealingSheetItemCreate,

  MorphicCategoryInfo,
  MorphicTheme,
  MorphicItem,
  Schedule,

  ScheduleUpdate,
  SendJob,
  ScanStartRequest,
  ScanStatusResponse,
  ScanResultsResponse,
  ScanAcceptRequest,
  BackgroundTask,
  SendRequest,
} from '../types';

const API_BASE = 'http://localhost:8000/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`API Error ${response.status}: ${errorBody}`);
  }
  return response.json() as Promise<T>;
}

// -- Clients --

export function fetchClients(): Promise<Client[]> {
  return request('/clients');
}

export function fetchClient(id: number): Promise<Client> {
  return request(`/clients/${id}`);
}

export function createClient(data: ClientCreate): Promise<Client> {
  return request('/clients', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateClient(id: number, data: ClientUpdate): Promise<Client> {
  return request(`/clients/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function deleteClient(id: number): Promise<void> {
  return request(`/clients/${id}`, { method: 'DELETE' });
}

// -- Targets --

export function fetchTargets(clientId: number): Promise<Target[]> {
  return request(`/clients/${clientId}/targets`);
}

export function fetchTarget(id: number): Promise<Target> {
  return request(`/targets/${id}`);
}

export function createTarget(clientId: number, data: TargetCreate): Promise<Target> {
  return request(`/clients/${clientId}/targets`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateTarget(id: number, data: TargetUpdate): Promise<Target> {
  return request(`/targets/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function deleteTarget(id: number): Promise<void> {
  return request(`/targets/${id}`, { method: 'DELETE' });
}

// -- Healing Sheets --

export function fetchSheets(targetId: number): Promise<HealingSheet[]> {
  return request(`/targets/${targetId}/sheets`);
}

export function fetchAllSheets(): Promise<HealingSheet[]> {
  return request('/sheets');
}

export function fetchSheet(id: number): Promise<HealingSheet> {
  return request(`/sheets/${id}`);
}

export function createSheet(targetId: number, data: HealingSheetCreate): Promise<HealingSheet> {
  return request(`/targets/${targetId}/sheets`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateSheet(id: number, data: HealingSheetUpdate): Promise<HealingSheet> {
  return request(`/sheets/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function deleteSheet(id: number): Promise<void> {
  return request(`/sheets/${id}`, { method: 'DELETE' });
}

// -- Healing Sheet Items --

export function fetchSheetItems(sheetId: number): Promise<HealingSheetItem[]> {
  return request(`/sheets/${sheetId}/items`);
}

export function createSheetItem(sheetId: number, data: HealingSheetItemCreate): Promise<HealingSheetItem> {
  return request(`/sheets/${sheetId}/items`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function deleteSheetItem(sheetId: number, itemId: number): Promise<void> {
  return request(`/sheets/${sheetId}/items/${itemId}`, { method: 'DELETE' });
}

// -- Morphic Field --

export function fetchMorphicThemes(): Promise<MorphicTheme[]> {
  return request('/morphic/themes');
}

export function fetchMorphicCategories(themeId?: number): Promise<MorphicCategoryInfo[]> {
  const params = themeId !== undefined ? `?theme_id=${themeId}` : '';
  return request(`/morphic/categories${params}`);
}

export function fetchMorphicItems(categoryId: number): Promise<MorphicItem[]> {
  return request(`/morphic/items/${categoryId}`);
}

export function searchMorphicItems(query: string, mode: 'fulltext' | 'semantic' = 'fulltext'): Promise<MorphicItem[]> {
  return request(`/morphic/search?q=${encodeURIComponent(query)}&type=${mode}`);
}

// -- Scan --

export function startScan(data: ScanStartRequest): Promise<BackgroundTask> {
  return request('/scan/start', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function getScanStatus(): Promise<ScanStatusResponse> {
  return request('/scan/status');
}

export function getScanResults(taskId?: string): Promise<ScanResultsResponse> {
  const params = taskId ? `?task_id=${taskId}` : '';
  return request(`/scan/results${params}`);
}

export function acceptScanResults(data: ScanAcceptRequest): Promise<{ added: number }> {
  return request('/scan/accept', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function getTaskStatus(taskId: string): Promise<BackgroundTask> {
  return request(`/scan/tasks/${taskId}`);
}

export function cancelTask(taskId: string): Promise<{ task_id: string; status: string }> {
  return request(`/scan/tasks/${taskId}/cancel`, { method: 'POST' });
}

// -- Hardware Diode --

const HW_API = 'http://localhost:8000/api/hardware';

export interface HardwareScanFullResult {
  stage1_categories: Array<{
    category_id: number;
    category_name: string;
    theme_name: string | null;
    item_count: number;
    score: number;
  }>;
  stage2_items: Array<{
    item_id: number;
    category_id: number;
    category_name: string;
    text_primary: string | null;
    text_secondary: string | null;
    score: number;
  }>;
  total_categories_scanned: number;
  total_items_scanned: number;
  method: string;
  signal_quality: number;
}

export interface HardwareCategoryScanResult {
  total_categories: number;
  results: Array<{
    category_id: number;
    category_name: string;
    theme_name: string | null;
    item_count: number;
    score: number;
  }>;
  signal_quality: number;
  method: string;
}

export interface HardwareItemScanResult {
  total_items: number;
  results: Array<{
    item_id: number;
    category_id: number;
    category_name: string;
    text_primary: string | null;
    text_secondary: string | null;
    score: number;
  }>;
  signal_quality: number;
  method: string;
}

export function getHardwareStatus(): Promise<{ connected: boolean; signal_quality: number; device_url: string }> {
  return fetch(`${HW_API}/status`).then(r => r.json());
}

export function connectHardware(): Promise<{ connected: boolean; message: string }> {
  return fetch(`${HW_API}/connect`, { method: 'POST' }).then(r => r.json());
}

export function runFullScan(params: {
  theme_id?: number;
  category_cycles?: number;
  item_cycles?: number;
  top_categories?: number;
  top_items?: number;
  method?: string;
}): Promise<HardwareScanFullResult> {
  const qs = new URLSearchParams();
  if (params.theme_id != null) qs.set('theme_id', String(params.theme_id));
  if (params.category_cycles) qs.set('category_cycles', String(params.category_cycles));
  if (params.item_cycles) qs.set('item_cycles', String(params.item_cycles));
  if (params.top_categories) qs.set('top_categories', String(params.top_categories));
  if (params.top_items) qs.set('top_items', String(params.top_items));
  if (params.method) qs.set('method', params.method);
  return fetch(`${HW_API}/scan/full?${qs}`, { method: 'POST' }).then(r => r.json());
}

export function runCategoryScan(params: {
  theme_id?: number;
  cycles?: number;
  top_n?: number;
  method?: string;
}): Promise<HardwareCategoryScanResult> {
  const qs = new URLSearchParams();
  if (params.theme_id != null) qs.set('theme_id', String(params.theme_id));
  if (params.cycles) qs.set('cycles', String(params.cycles));
  if (params.top_n) qs.set('top_n', String(params.top_n));
  if (params.method) qs.set('method', params.method);
  return fetch(`${HW_API}/scan/categories?${qs}`, { method: 'POST' }).then(r => r.json());
}

export function runItemScan(params: {
  category_ids: number[];
  cycles?: number;
  top_n?: number;
  method?: string;
}): Promise<HardwareItemScanResult> {
  const qs = new URLSearchParams();
  qs.set('category_ids', params.category_ids.join(','));
  if (params.cycles) qs.set('cycles', String(params.cycles));
  if (params.top_n) qs.set('top_n', String(params.top_n));
  if (params.method) qs.set('method', params.method);
  return fetch(`${HW_API}/scan/items?${qs}`, { method: 'POST' }).then(r => r.json());
}

// -- Send --

export function startDirectSend(sheetId: number, data?: SendRequest): Promise<BackgroundTask> {
  return request(`/send/start/${sheetId}`, {
    method: 'POST',
    body: JSON.stringify(data ?? { duration: 120.0 }),
  });
}

// -- Schedules --

export function fetchSchedule(scheduleId: number): Promise<Schedule> {
  return request(`/send/schedules/${scheduleId}`);
}

export function updateSchedule(scheduleId: number, data: ScheduleUpdate): Promise<Schedule> {
  return request(`/send/schedules/${scheduleId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function deleteSchedule(scheduleId: number): Promise<void> {
  return request(`/send/schedules/${scheduleId}`, { method: 'DELETE' });
}

export function fetchScheduleJobs(scheduleId: number): Promise<SendJob[]> {
  return request(`/send/schedules/${scheduleId}/jobs`);
}
