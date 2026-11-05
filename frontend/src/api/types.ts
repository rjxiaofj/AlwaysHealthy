export interface ApiEnvelope<T> {
  code: string
  message: string
  data: T
  request_id: string
}

export interface PageData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface UserInfo {
  id: string
  username: string
  email: string | null
  role: string
  status: string
  created_at: string
  last_login_at: string | null
}

export interface TokenPayload {
  access_token: string
  refresh_token: string
  expires_in: number
  user_id: string
  username: string
  role: string
}

export interface MedicalHistory {
  id: string
  history_type: string
  condition_code: string
  description: string | null
  recorded_at: string
}

export interface Profile {
  id: string
  birth_date: string | null
  age: number | null
  age_years: number | null
  sex: string | null
  height_cm: number | null
  weight_kg: number | null
  bmi: number | null
  waist_cm: number | null
  occupation: string | null
  lifestyle: Record<string, unknown>
  profile_version: number
  medical_histories: MedicalHistory[]
}

// 空值统一用 null：后端按字段是否出现区分「不改」，按 null 识别「清空」，
// 所以这里不能写成可选字段，漏传一个键就等于那次编辑不生效
export interface ProfilePatchBody {
  birth_date: string | null
  sex: string | null
  height_cm: number | null
  weight_kg: number | null
  waist_cm: number | null
  occupation: string | null
  lifestyle: Record<string, number | string | null>
}

export interface RiskFactor {
  rule_id: string
  indicator: string
  label: string
  value: number | string | null
  unit: string
  message: string
  risk_level: string
}

export interface EvidenceSource {
  source_id: string
  title: string
  version: string
  page: number | null
  excerpt?: string
}

export interface Dimension {
  dimension: string
  level: string
  risk_factors: RiskFactor[]
  missing_data: string[]
  explanation: string
  limitations: string[]
  evidence_sources: EvidenceSource[]
}

export interface Recommendation {
  id: string
  dimension: string
  category: string
  priority: string
  title: string
  description: string
  action_items: string[]
  cautions: string[]
  requires_professional_consultation: boolean
}

export interface Assessment {
  id: string
  overall_level: string
  urgency: string
  rule_engine_version: string
  knowledge_version: string
  created_at: string
  profile_version: number
  dimensions: Dimension[]
  recommendations: Recommendation[]
}

export interface AssessmentSummary {
  id: string
  overall_level: string
  urgency: string
  created_at: string
  profile_version: number
}

export interface Task {
  id: string
  title: string
  category: string
  description: string | null
  scheduled_date: string
  scheduled_time: string | null
  frequency: string | null
  duration_minutes: number | null
  completion_criteria: string
  checkin_type: string
  reminder_enabled: boolean
  status: string
  checkin_status: string | null
}

export interface PlanVersion {
  id: string
  version_no: number
  status: string
  change_reason: string | null
  created_at: string
  content: Record<string, unknown>
}

export interface PlanAdjustment {
  version_id: string | null
  reason: string | null
  status: string
  created_at: string
  feedback: string | null
}

export interface PlanPendingTask {
  id: string
  title: string
  scheduled_date: string
  scheduled_time: string | null
  duration_minutes: number | null
}

export interface PlanPendingVersion {
  id: string
  version_no: number
  change_reason: string | null
  tasks: PlanPendingTask[]
}

export interface Plan {
  id: string
  title: string
  duration_days: number
  start_date: string
  end_date: string
  status: string
  current_version_id: string | null
  assessment_id: string | null
  created_at: string
  adjustment: PlanAdjustment | null
  pending_version: PlanPendingVersion | null
  tasks: Task[]
  versions: PlanVersion[]
}

export interface PlanSummary {
  id: string
  title: string
  duration_days: number
  start_date: string
  end_date: string
  status: string
  created_at: string
  current_version_id: string | null
}

export interface Conversation {
  id: string
  title: string
  status: string
  created_at: string
  updated_at: string
  last_message: string | null
}

export interface ChatMessage {
  id: string
  role: string
  content: string
  message_type: string
  meta: Record<string, unknown>
  created_at: string
}

export interface RunInfo {
  id: string
  status: string
  run_type: string
  started_at: string
  completed_at: string | null
  error_code: string | null
  meta: Record<string, unknown>
}

export interface ReportSummary {
  id: string
  report_type: string
  title: string
  created_at: string
}

export interface ReportSection {
  heading: string
  paragraphs: string[]
  items: string[]
}

export interface ReportDetail {
  id: string
  report_type: string
  title: string
  created_at: string
  content: {
    disclaimer?: string
    overall_level?: string
    urgency?: string
    sections: ReportSection[]
  }
}

export interface KnowledgeSource {
  source_id: string
  title: string
  issuing_org: string
  document_type: string
  version: string
  publish_date: string | null
  effective_status: string
  applicable_population: string
  dimensions: string[]
  original_url: string | null
  import_date: string
}

export interface Reminder {
  id: string
  notification_type: string
  title: string
  content: string
  related_object_id: string | null
  read_at: string | null
  created_at: string
}

export interface MetricPoint {
  measured_at: string
  value: number
}

export interface Trend {
  metric_code: string
  label: string
  unit: string
  points: MetricPoint[]
  latest: number | null
  average: number | null
  minimum: number | null
  maximum: number | null
  change: number | null
}

export interface TrackingSummary {
  period_start: string
  period_end: string
  completion_rate: number
  task_total: number
  task_completed: number
  metrics: Trend[]
  notes: string[]
}

export interface FileItem {
  id: string
  original_filename: string
  mime_type: string
  file_size: number
  parse_status: string
  created_at: string
}

export interface ExtractedField {
  metric_code: string
  label: string
  unit: string
  value: number
  raw: string
}

export interface ExtractedDocument {
  id: string
  parse_status: string
  parse_message: string
  fields: ExtractedField[]
}

export interface FeedbackRecord {
  id: string
  recorded_at: string
  mood_status: string | null
  fatigue_level: string | null
  physical_feeling: string | null
  execution_difficulty: string | null
  additional_feedback: string | null
}

export interface EmergencyEvent {
  id: string
  triggered_at: string
  trigger_reason: string
  matched_rules: Array<{ rule_id?: string; label?: string }>
  urgency: string
  response_status: string
}

export interface ConsentRecord {
  id: string
  consent_type: string
  label: string
  policy_version: string
  consent_status: string
  consented_at: string
  revoked_at: string | null
}

export interface ConfirmationPayload {
  run_id: string
  approval_type: 'profile' | 'plan'
  message: string
  summary: Record<string, unknown>
  assessment_id: string | null
  plan_id: string | null
  plan_version_id: string | null
}
