export type State = "red" | "yellow" | "green";

export type Metric = { label: string; value: number; state: State };

export type Reminder = {
  source_type: string;
  source_id: string;
  title: string;
  due_date: string;
  state: State;
  owner_hint?: string | null;
};

export type Action = {
  id: string;
  compliance_record_id: string;
  title: string;
  due_date: string;
  priority: string;
  status: string;
  due_state: State;
};

export type RecordItem = {
  id: string;
  title: string;
  category: string;
  status: string;
  priority: string;
  owner_user_id: string;
  legal_basis: string;
  control_type: string;
  due_date: string;
  review_date: string;
  risk_if_missing?: string | null;
  evidence_summary?: string | null;
  tags: string[];
  due_state: State;
  overdue: boolean;
  evidence: Evidence[];
  actions: Action[];
};

export type EmployeeProfile = {
  id: string;
  employee_id: string;
  contract_type: string;
  contract_start?: string | null;
  contract_end?: string | null;
  probation_until?: string | null;
  residence_permit_required: boolean;
  residence_permit_type?: string | null;
  residence_permit_valid_until?: string | null;
  work_permit_note?: string | null;
  driver_license_required: boolean;
  driver_license_classes: string[];
  driver_license_last_check?: string | null;
  driver_license_next_check?: string | null;
  first_aid_last_course?: string | null;
  first_aid_valid_until?: string | null;
  ipaf_last_training?: string | null;
  ipaf_valid_until?: string | null;
  general_instruction_last?: string | null;
  general_instruction_next?: string | null;
  occupational_health_required: boolean;
  occupational_health_last?: string | null;
  occupational_health_next?: string | null;
  ppe_issued_at?: string | null;
  notes?: string | null;
};

export type Employee = {
  id: string;
  branch_id: string;
  full_name: string;
  role: string;
  team?: string | null;
  start_date?: string | null;
  first_aider: boolean;
  skills: string[];
  profile?: EmployeeProfile | null;
};

export type Vehicle = {
  id: string;
  branch_id: string;
  license_plate: string;
  brand?: string | null;
  model?: string | null;
  vehicle_type?: string | null;
  vin?: string | null;
  first_registration?: string | null;
  ownership_type?: string | null;
  assigned_employee_id?: string | null;
  mileage?: number | null;
  hu_due_date?: string | null;
  uvv_last_check?: string | null;
  uvv_next_check?: string | null;
  service_due_date?: string | null;
  tire_type?: string | null;
  tire_change_due_date?: string | null;
  insurance_valid_until?: string | null;
  fuel_card_number?: string | null;
  equipment: string[];
  notes?: string | null;
};

export type Assessment = {
  id: string;
  branch_id: string;
  title: string;
  assessment_date: string;
  team_structure?: string | null;
  customer_clusters?: string | null;
  service_portfolio?: string | null;
  project_types?: string | null;
  service_share?: string | null;
  main_problems?: string | null;
  management_ratings: Record<string, string>;
  next_actions: { title?: string }[];
  notes?: string | null;
};

export type Cockpit = {
  metrics: Metric[];
  reminders: Reminder[];
  overdue_compliance: RecordItem[];
  due_soon_compliance: RecordItem[];
  open_actions: Action[];
  pipeline_value: number;
  service_due_count: number;
  vehicle_due_count: number;
  employee_due_count: number;
};

export type Branch = { id: string; name: string };
export type User = { id: string; display_name: string };

export type Bootstrap = {
  branches: Branch[];
  users: User[];
  auth_mode: string;
  permissions: string[];
};

export type Principal = {
  user_id: string;
  display_name: string;
  email?: string | null;
  role_name?: string | null;
  permissions: string[];
  source: string;
};

export type DevUser = { id: string; display_name: string; role_name?: string | null };

export function can(permissions: string[], required: string): boolean {
  if (permissions.includes("*") || permissions.includes(required)) return true;
  return permissions.includes(`${required.split(":")[0]}:*`);
}

export type Evidence = {
  id: string;
  compliance_record_id: string;
  file_name: string;
  storage_path: string;
  mime_type?: string | null;
  file_size_bytes?: number | null;
  evidence_type: string;
  description?: string | null;
  uploaded_at: string;
};

export type Account = {
  id: string;
  name: string;
  branch_id: string;
  account_type: string;
  owner_user_id?: string | null;
  industry?: string | null;
  notes?: string | null;
};

export type Opportunity = {
  id: string;
  account_id: string;
  title: string;
  offer_status: string;
  probability: number;
  expected_volume: number;
  next_step?: string | null;
  follow_up_date?: string | null;
  strategic_relevance: string;
};

export type ServiceContract = {
  id: string;
  account_id: string;
  title: string;
  sla_response_hours?: number | null;
  next_maintenance_at?: string | null;
  upsell_hint?: string | null;
};

export type AgentRun = {
  id: string;
  use_case: string;
  source_entity_id: string;
  status: string;
  request_payload: Record<string, unknown>;
  response_payload?: Record<string, unknown> | null;
  created_at: string;
  completed_at?: string | null;
};
