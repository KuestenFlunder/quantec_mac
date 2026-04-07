export interface Client {
  id: number;
  first_name: string;
  last_name: string;
  title: string | null;
  salutation: string | null;
  letter_salutation: string | null;
  email: string | null;
  phone_home: string | null;
  phone_business: string | null;
  phone_mobile: string | null;
  address_street: string | null;
  address_zip: string | null;
  address_city: string | null;
  address_country: string | null;
  date_of_birth: string | null;
  gender: string | null;
  notes: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ClientCreate {
  first_name: string;
  last_name: string;
  title?: string | null;
  salutation?: string | null;
  letter_salutation?: string | null;
  email?: string | null;
  phone_home?: string | null;
  phone_business?: string | null;
  phone_mobile?: string | null;
  address_street?: string | null;
  address_zip?: string | null;
  address_city?: string | null;
  address_country?: string | null;
  date_of_birth?: string | null;
  gender?: string | null;
  notes?: string | null;
  active?: boolean;
}

export type ClientUpdate = Partial<ClientCreate>;

export interface Target {
  id: number;
  client_id: number;
  name: string;
  target_type: string | null;
  gender: string | null;
  date_of_birth: string | null;
  notes: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TargetCreate {
  name: string;
  target_type?: string | null;
  gender?: string | null;
  date_of_birth?: string | null;
  notes?: string | null;
  active?: boolean;
}

export type TargetUpdate = Partial<TargetCreate>;

export interface HealingSheet {
  id: number;
  target_id: number;
  name: string;
  send_type: string | null;
  sort_order: number;
  use_hs_picture: boolean;
  use_target_picture: boolean;
  has_advice: boolean;
  advice_text: string | null;
  is_template: boolean;
  active: boolean;
  expiry_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface HealingSheetCreate {
  name: string;
  send_type?: string | null;
  sort_order?: number;
  use_hs_picture?: boolean;
  use_target_picture?: boolean;
  has_advice?: boolean;
  advice_text?: string | null;
  is_template?: boolean;
  active?: boolean;
  expiry_date?: string | null;
}

export type HealingSheetUpdate = Partial<HealingSheetCreate>;

export interface HealingSheetItem {
  id: number;
  healing_sheet_id: number;
  sort_index: number;
  text: string | null;
  comment: string | null;
  potency_kind: string | null;
  potency_value: string | null;
  potency_intensity: number | null;
  qrs_factor: number | null;
  color: string | null;
  suppress_printing: boolean;
  ignore_on_check: boolean;
  do_not_extend: boolean;
  mistake_count: number;
  changed_by_butler: boolean;
  morphic_field_item_id: number | null;
  created_at: string;
}

export interface HealingSheetItemCreate {
  sort_index?: number;
  text?: string | null;
  comment?: string | null;
  potency_kind?: string | null;
  potency_value?: string | null;
  potency_intensity?: number | null;
  qrs_factor?: number | null;
  color?: string | null;
  suppress_printing?: boolean;
  ignore_on_check?: boolean;
  do_not_extend?: boolean;
  morphic_field_item_id?: number | null;
}

export interface Schedule {
  id: number;
  healing_sheet_id: number;
  schedule_type: string | null;
  start_date: string | null;
  end_date: string | null;
  interval_duration: number | null;
  send_duration: number | null;
  active: boolean;
  butler_active: boolean;
  created_at: string;
}

export interface ScheduleCreate {
  schedule_type?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  interval_duration?: number | null;
  send_duration?: number | null;
  active?: boolean;
  butler_active?: boolean;
}

export type ScheduleUpdate = Partial<ScheduleCreate>;

export interface MorphicCategory {
  id: number;
  name: string;
  theme: string | null;
  item_count: number;
}

export interface MorphicTheme {
  id: number;
  name: string;
  sort_order: number;
}

export interface MorphicCategoryInfo {
  id: number;
  name: string;
  theme_id: number | null;
  theme_name: string | null;
  parent_id: number | null;
  depth: number;
  item_count: number;
  description: string | null;
}

export interface MorphicItem {
  id: number;
  category_id: number;
  category_name: string;
  text_primary: string | null;
  text_secondary: string | null;
  quality_score: number | null;
  similarity: number | null;
}

export interface SendJob {
  id: number;
  schedule_id: number;
  scheduled_start: string | null;
  actual_start: string | null;
  actual_end: string | null;
  duration: number | null;
  status: string;
  created_at: string;
}

// -- Scan Types --

export interface ScanStartRequest {
  category_ids: number[];
  cycles: number;
  diode_type: string;
  top_n: number;
}

export interface ScanResultItem {
  rank: number;
  raw_score: number;
  score: number;
  item_id: number;
  category_id: number;
  category_name: string;
  text_primary: string | null;
  text_secondary: string | null;
  quality_score: number | null;
}

export interface ScanResultsResponse {
  task_id: string;
  status: string;
  total_items: number;
  cycles: number;
  diode_type: string;
  category_ids: number[];
  top_n: number;
  results: ScanResultItem[];
}

export interface DeviceStatus {
  connected: boolean;
  device_info: string | null;
  signal_quality: number;
  message: string;
}

export interface ScanStatusResponse {
  device: DeviceStatus;
  current_task: BackgroundTask | null;
}

export interface BackgroundTask {
  task_id: string;
  task_type: string;
  status: string;
  progress: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  result: Record<string, unknown> | null;
}

export interface ScanAcceptRequest {
  healing_sheet_id: number;
  item_ids: number[];
}

// -- Send Types --

export interface SendRequest {
  duration: number;
  schedule_id?: number | null;
}

export type NavSection =
  | 'clients'
  | 'morphic'
  | 'scanner'
  | 'send'
  | 'schedule'
  | 'reports'
  | 'database'
  | 'settings';
