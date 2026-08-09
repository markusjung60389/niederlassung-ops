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
  branch_id?: string;
  /** The rule this is an instance of, if any. */
  rule_id?: string | null;
  /** "group" or "branch": whether the branch may change the obligation. */
  rule_scope?: string | null;
  status: string;
  priority: string;
  owner_user_id: string;
  legal_basis: string;
  control_type: string;
  recurrence?: string | null;
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

export type QualificationType = {
  id: string;
  code: string;
  name: string;
  category: string;
  /** null means the entry applies group-wide. */
  branch_id?: string | null;
  validity_months?: number | null;
  reminder_days: number;
  evidence_required: boolean;
  legal_basis?: string | null;
  description?: string | null;
  active: boolean;
};

export type JobRoleRequirement = {
  id: string;
  job_role_id: string;
  qualification_type_id: string;
  mandatory: boolean;
  note?: string | null;
  qualification_name: string;
  qualification_code: string;
};

export type JobRole = {
  id: string;
  name: string;
  description?: string | null;
  branch_id?: string | null;
  active: boolean;
  requirements: JobRoleRequirement[];
  employee_count: number;
};

export type Qualification = {
  id: string;
  employee_id: string;
  title: string;
  qualification_type: string;
  qualification_type_id?: string | null;
  issued_on?: string | null;
  valid_until?: string | null;
  document_id?: string | null;
  reminder_days: number;
  due_state: State;
  overdue: boolean;
};

/** One line of the qualification matrix: required vs. recorded. */
export type RequirementState = {
  qualification_type_id: string;
  code: string;
  name: string;
  category: string;
  mandatory: boolean;
  state: "ok" | "expiring" | "expired" | "missing" | "undated" | "evidence_missing";
  valid_until?: string | null;
  issued_on?: string | null;
  qualification_id?: string | null;
  has_evidence: boolean;
  /** Set when the branch has an exception from this group requirement. */
  override_mode?: string | null;
  override_reason?: string | null;
};

export type Readiness = "ready" | "limited" | "blocked";

export type Employee = {
  id: string;
  branch_id: string;
  full_name: string;
  role: string;
  job_role_id?: string | null;
  job_role_name?: string | null;
  team?: string | null;
  start_date?: string | null;
  status: string;
  exit_date?: string | null;
  first_aider: boolean;
  skills: string[];
  notes?: string | null;
  profile?: EmployeeProfile | null;
  qualifications: Qualification[];
  requirements: RequirementState[];
  readiness: Readiness;
  due_state: State;
  open_requirements: number;
  next_due_title?: string | null;
  next_due_date?: string | null;
  /** Home branch plus every branch the person is deployed to. */
  branch_ids: string[];
  /** Deployability per branch: requirements differ, so the verdict does too. */
  readiness_by_branch: Record<string, Readiness>;
};

export type MatrixCell = {
  qualification_type_id: string;
  state: string;
  mandatory: boolean;
  valid_until?: string | null;
  has_evidence: boolean;
};

export type MatrixRow = {
  employee_id: string;
  full_name: string;
  job_role_id?: string | null;
  job_role_name?: string | null;
  readiness: Readiness;
  cells: MatrixCell[];
};

export type QualificationMatrix = {
  qualification_types: QualificationType[];
  rows: MatrixRow[];
};

export type ComplianceTemplate = {
  key: string;
  title: string;
  category: string;
  control_type: string;
  recurrence: string;
  legal_basis: string;
  priority: string;
  risk_if_missing: string;
};

export type Vehicle = {
  id: string;
  /** The branch that owns it. */
  branch_id: string;
  /** Set while it stands somewhere else. */
  current_branch_id?: string | null;
  current_branch_name?: string | null;
  /** Where it actually is: current branch, or home when not on loan. */
  location_branch_id?: string | null;
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
  assigned_employee_name?: string | null;
  due_state: State;
  next_due_title?: string | null;
  next_due_date?: string | null;
  /** Set when the assigned driver's licence check has lapsed. */
  driver_alert?: string | null;
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

export type FirstAiderStatus = {
  headcount: number;
  trained: number;
  required: number;
  state: State;
};

export type Cockpit = {
  metrics: Metric[];
  reminders: Reminder[];
  overdue_compliance: RecordItem[];
  due_soon_compliance: RecordItem[];
  open_actions: Action[];
  expiring_qualifications: Qualification[];
  pipeline_value: number;
  service_due_count: number;
  vehicle_due_count: number;
  employee_due_count: number;
  blocked_employees: number;
  limited_employees: number;
  first_aiders?: FirstAiderStatus | null;
};

export type Branch = {
  id: string;
  name: string;
  /** Short marker for tight cells and the branch switcher. */
  code?: string | null;
  location?: string | null;
  active?: boolean;
  manager_user_id?: string | null;
};

/** One row of the area manager's overview: the same figures for every branch. */
export type PortfolioRow = {
  branch_id: string;
  branch_name: string;
  code?: string | null;
  headcount: number;
  blocked: number;
  limited: number;
  overdue_compliance: number;
  due_vehicles: number;
  first_aiders_trained: number;
  first_aiders_required: number;
  open_exceptions: number;
  new_exceptions: number;
  state: State;
};

/** A branch deviating from a group requirement, with its reason. */
export type RequirementOverride = {
  id: string;
  branch_id: string;
  branch_name: string;
  requirement_id: string;
  job_role_id: string;
  job_role_name: string;
  qualification_name: string;
  mode: "excluded" | "mandatory" | "optional";
  reason: string;
  valid_until?: string | null;
  created_by?: string | null;
  created_at: string;
  acknowledged_at?: string | null;
  revoked_at?: string | null;
  revoked_reason?: string | null;
  revoked_effective_from?: string | null;
  active: boolean;
};

/** The obligation itself, separate from each branch's work on it. */
export type ComplianceRule = {
  id: string;
  title: string;
  category: string;
  control_type: string;
  recurrence: string;
  legal_basis: string;
  priority: string;
  risk_if_missing?: string | null;
  /** null means group-wide. */
  branch_id?: string | null;
  branch_name?: string | null;
  valid_from?: string | null;
  first_due_date?: string | null;
  active: boolean;
  record_count: number;
  branch_ids: string[];
};

export type ScopeChangePreview = {
  creates_in: string[];
  detaches_in: string[];
  unchanged_in: string[];
  newly_blocked_employees: number;
};
export type User = { id: string; display_name: string };

/** An account as the user administration sees it. */
export type Account = {
  id: string;
  display_name: string;
  email: string;
  is_active: boolean;
  role_id?: string | null;
  role_name?: string | null;
  all_branches: boolean;
  branch_ids: string[];
  /** How this account signs in: Microsoft, password, or not yet at all. */
  has_password: boolean;
  external_id?: string | null;
  must_change_password: boolean;
  last_login_at?: string | null;
  locked_until?: string | null;
  created_at: string;
};

export type RoleInfo = {
  id: string;
  name: string;
  description?: string | null;
  permissions: string[];
  /** One of the presets: kept in sync by the backend, not editable. */
  system: boolean;
  user_count: number;
};

export type PermissionInfo = {
  key: string;
  area: string;
  label: string;
  description: string;
};

export type Bootstrap = {
  branches: Branch[];
  users: User[];
  auth_mode: string;
  permissions: string[];
  /** False once the emergency password login has been switched off. */
  password_login_enabled?: boolean;
};

export type Principal = {
  user_id: string;
  display_name: string;
  email?: string | null;
  role_name?: string | null;
  permissions: string[];
  source: string;
  /** True while the start password is still in place. */
  must_change_password?: boolean;
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

/* Vertrieb ist aus der Oberflaeche entfernt. Tabellen und Endpunkte bestehen
   weiter (siehe CHANGELOG), Typen dafuer braucht das Frontend nicht mehr. */

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
