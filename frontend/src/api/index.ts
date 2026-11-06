import { api } from './client'
import type {
  AccountRole,
  AdminOverview,
  AdminUser,
  AgentStatus,
  Assessment,
  AuditLog,
  AssessmentSummary,
  ChatMessage,
  ConsentRecord,
  Conversation,
  EmergencyEvent,
  ExtractedDocument,
  FeedbackRecord,
  FileItem,
  KnowledgeSource,
  PageData,
  Plan,
  PlanSummary,
  Profile,
  ProfilePatchBody,
  Reminder,
  ReportDetail,
  ReportSummary,
  RuntimeConfig,
  SecurityIncident,
  ServiceStatus,
  TokenPayload,
  TrackingSummary,
  Trend,
  UserInfo,
} from './types'

export const authApi = {
  register: (username: string, password: string, role: AccountRole = 'user', adminCode?: string) =>
    api<TokenPayload>('/auth/register', {
      body: {
        username,
        password,
        role,
        ...(adminCode !== undefined ? { admin_code: adminCode } : {}),
      },
    }),
  login: (username: string, password: string, expectedRole?: AccountRole) =>
    api<TokenPayload>('/auth/login', {
      body: { username, password, ...(expectedRole ? { expected_role: expectedRole } : {}) },
    }),
  logout: (refreshToken: string) => api<null>('/auth/logout', { body: { refresh_token: refreshToken } }),
  me: () => api<UserInfo>('/users/me'),
}

export const adminApi = {
  // /health/* 挂在 app 根路径（compose healthcheck 也用 /health/live），不在版本前缀下
  services: () => api<ServiceStatus>('/health/services', { base: '' }),
  incidents: (limit = 20, status?: string, severity?: string) =>
    api<SecurityIncident[]>('/admin/incidents', { params: { limit, status, severity } }),
  resolveIncident: (id: string) =>
    api<SecurityIncident>(`/admin/incidents/${id}/resolve`, { method: 'POST', body: {} }),
  users: (page = 1, pageSize = 20, filters?: { keyword?: string; role?: string; status?: string }) =>
    api<PageData<AdminUser>>('/admin/users', {
      params: { page, page_size: pageSize, ...filters },
    }),
  setRole: (id: string, role: AccountRole) =>
    api<AdminUser>(`/admin/users/${id}/role`, { method: 'PATCH', body: { role } }),
  setStatus: (id: string, status: 'active' | 'disabled') =>
    api<AdminUser>(`/admin/users/${id}/status`, { method: 'PATCH', body: { status } }),
  deleteUser: (id: string, confirmUsername: string) =>
    api<null>(`/admin/users/${id}`, { method: 'DELETE', params: { confirm_username: confirmUsername } }),
  overview: () => api<AdminOverview>('/admin/overview'),
  audits: (page = 1, pageSize = 20, filters?: { action?: string; actor_user_id?: string; result?: string }) =>
    api<PageData<AuditLog>>('/admin/audit-logs', {
      params: { page, page_size: pageSize, ...filters },
    }),
  runtime: () => api<RuntimeConfig>('/admin/runtime'),
  setRuntime: (payload: Partial<RuntimeConfig>) =>
    api<RuntimeConfig>('/admin/runtime', { method: 'PATCH', body: payload }),
  agents: () => api<AgentStatus[]>('/admin/agents'),
  workflowStats: () => api<Record<string, number>>('/admin/workflow-stats'),
  knowledge: () => api<{ chunks: number }>('/admin/knowledge'),
}

export const profileApi = {
  get: () => api<Profile>('/profiles/me'),
  patch: (payload: ProfilePatchBody) => api<Profile>('/profiles/me', { method: 'PATCH', body: payload }),
  addHistory: (payload: { history_type: string; condition_code: string; description?: string }) =>
    api<{ id: string }>('/profiles/me/histories', { body: payload }),
  upload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api<{ id: string; parse_status: string }>('/profiles/me/documents', { formData: form })
  },
  files: () => api<FileItem[]>('/profiles/me/documents'),
  emergencyEvents: () => api<EmergencyEvent[]>('/profiles/me/emergency-events'),
  extracted: (id: string) => api<ExtractedDocument>(`/profiles/me/documents/${id}/extracted`),
  applyExtracted: (id: string, metricCodes: string[]) =>
    api<{ applied: number; skipped: number }>(`/profiles/me/documents/${id}/apply`, {
      body: { metric_codes: metricCodes },
    }),
}

export const chatApi = {
  create: (title?: string) => api<{ id: string; thread_id: string }>('/conversations', { body: { title } }),
  list: () => api<Conversation[]>('/conversations'),
  messages: (id: string) => api<ChatMessage[]>(`/conversations/${id}/messages`),
}

export const assessmentApi = {
  create: () => api<Assessment>('/assessments', { body: {} }),
  list: (page = 1, pageSize = 10) =>
    api<PageData<AssessmentSummary>>('/assessments', { params: { page, page_size: pageSize } }),
  latest: () => api<Assessment | null>('/assessments/latest'),
  detail: (id: string) => api<Assessment>(`/assessments/${id}`),
}

export const planApi = {
  generate: (durationDays: number, goal?: string) =>
    api<Plan>('/plans/generate', { body: { duration_days: durationDays, goal } }),
  list: () => api<PlanSummary[]>('/plans'),
  detail: (id: string) => api<Plan>(`/plans/${id}`),
  approve: (id: string, versionId: string) =>
    api<Plan>(`/plans/${id}/approve`, { body: { version_id: versionId } }),
  adjust: (id: string, reason: string) => api<{ version_id: string }>(`/plans/${id}/adjust`, { body: { reason } }),
  adjustmentFeedback: (id: string, versionId: string, feedback: string) =>
    api<{ version_id: string | null; feedback: string }>(`/plans/${id}/adjustment-feedback`, {
      body: { version_id: versionId, feedback },
    }),
  rejectVersion: (id: string, versionId: string) =>
    api<Plan>(`/plans/${id}/versions/${versionId}/reject`, { body: {} }),
  removeDraftTask: (id: string, versionId: string, taskId: string) =>
    api<Plan>(`/plans/${id}/versions/${versionId}/tasks/${taskId}`, { method: 'DELETE' }),
  shift: (id: string, startDate: string, reason?: string) =>
    api<Plan>(`/plans/${id}/shift`, { body: { start_date: startDate, reason } }),
  cancel: (id: string) => api<null>(`/plans/${id}/cancel`, { body: {} }),
  checkin: (taskId: string, status: string, feedback?: string) =>
    api<{ id: string; status: string }>(`/tasks/${taskId}/checkins`, { body: { status, feedback } }),
  patchTask: (
    taskId: string,
    // 时间传 null 表示清空，省略字段表示不改，两者含义不同
    payload: { scheduled_date?: string; scheduled_time?: string | null; reminder_enabled?: boolean },
  ) =>
    api<{ id: string; scheduled_date: string; scheduled_time: string | null; reminder_enabled: boolean }>(
      `/tasks/${taskId}`,
      { method: 'PATCH', body: payload },
    ),
}

export const trackingApi = {
  addMetric: (metricCode: string, value: number, measuredAt: string, context: Record<string, unknown> = {}) =>
    api<{ id: string }>('/tracking/metrics', {
      body: { metric_code: metricCode, value, measured_at: measuredAt, context },
    }),
  feedback: (payload: Record<string, unknown>) => api<{ id: string }>('/tracking/feedback', { body: payload }),
  feedbackList: (days = 30) => api<FeedbackRecord[]>('/tracking/feedback', { params: { days } }),
  summary: (planId?: string) => api<TrackingSummary>('/tracking/summary', { params: { plan_id: planId } }),
  trends: (codes: string[], days: number) =>
    api<Trend[]>('/tracking/trends', { params: { codes: codes.join(','), days } }),
  reassessment: (reason: string) => api<null>('/tracking/reassessment', { body: { reason } }),
}

export const reportApi = {
  list: () => api<ReportSummary[]>('/reports'),
  detail: (id: string) => api<ReportDetail>(`/reports/${id}`),
  createTracking: (planId: string) => api<ReportDetail>(`/plans/${planId}/report`, { body: {} }),
  exportUrl: (id: string) => `${window.location.origin}/api/v1/reports/${id}/export`,
  printUrl: (id: string) => `${window.location.origin}/api/v1/reports/${id}/print`,
}

export const reminderApi = {
  list: () => api<Reminder[]>('/reminders'),
  read: (id: string) => api<null>(`/reminders/${id}/read`, { body: {} }),
}

export const knowledgeApi = {
  sources: () => api<KnowledgeSource[]>('/knowledge/sources'),
}

export const consentApi = {
  list: () => api<ConsentRecord[]>('/consents'),
  set: (consentType: string, granted: boolean) =>
    api<{ id: string; consent_status: string }>('/consents', {
      body: { consent_type: consentType, policy_version: 'v1', granted },
    }),
}
