import type { ProfilePatchBody } from '@/api/types'

export interface ProfileForm {
  birth_date: string
  sex: string
  height_cm: string
  weight_kg: string
  waist_cm: string
  occupation: string
  sleep_hours: string
  exercise_days: string
  sedentary_hours: string
  smoking_status: string
  drinking_frequency: string
}

// 空串是清空，不是「不改」。两者必须能区分开：后端按字段是否出现判断，
// 少传一个键等于什么都不做，所以清空要显式发 null
function asNumberOrNull(text: string, label: string): number | null {
  const raw = text.trim()
  if (raw === '') return null
  const parsed = Number(raw)
  if (!Number.isFinite(parsed)) throw new Error(`${label}要填数字`)
  return parsed
}

export function buildProfilePatch(form: ProfileForm): ProfilePatchBody {
  return {
    birth_date: form.birth_date || null,
    sex: form.sex || null,
    height_cm: asNumberOrNull(form.height_cm, '身高'),
    weight_kg: asNumberOrNull(form.weight_kg, '体重'),
    waist_cm: asNumberOrNull(form.waist_cm, '腰围'),
    occupation: form.occupation.trim() || null,
    // 五个子键每次都给全，清掉的那项发 null，后端据此删键
    lifestyle: {
      sleep_hours: asNumberOrNull(form.sleep_hours, '平均睡眠时长'),
      exercise_days: asNumberOrNull(form.exercise_days, '每周运动天数'),
      sedentary_hours: asNumberOrNull(form.sedentary_hours, '每日久坐时长'),
      smoking_status: form.smoking_status || null,
      drinking_frequency: form.drinking_frequency || null,
    },
  }
}

export function formFromProfile(profile: {
  birth_date: string | null
  sex: string | null
  height_cm: number | null
  weight_kg: number | null
  waist_cm: number | null
  occupation: string | null
  lifestyle: Record<string, unknown>
}): ProfileForm {
  const lifestyle = profile.lifestyle || {}
  // 数字 0 与空串都算「没填」以外的正常值，这里只把 null 与 undefined 当没填
  const text = (value: unknown) => (value === null || value === undefined ? '' : String(value))
  return {
    birth_date: text(profile.birth_date),
    sex: text(profile.sex),
    height_cm: text(profile.height_cm),
    weight_kg: text(profile.weight_kg),
    waist_cm: text(profile.waist_cm),
    occupation: text(profile.occupation),
    sleep_hours: text(lifestyle.sleep_hours),
    exercise_days: text(lifestyle.exercise_days),
    sedentary_hours: text(lifestyle.sedentary_hours),
    smoking_status: text(lifestyle.smoking_status),
    drinking_frequency: text(lifestyle.drinking_frequency),
  }
}

export interface AgeSource {
  text: string
  hint: string
}

// 后端把「按生日算」与「对话里报的年龄」合成同一个 age，前端靠 birth_date 有没有值判断来源。
// 聊天里只说了年龄时 age_years 有值而 birth_date 为空，表单原来完全看不到这个年龄
export function ageSource(profile: { birth_date: string | null; age: number | null }): AgeSource {
  if (profile.age === null || profile.age === undefined) {
    return { text: '', hint: '填写出生日期后自动计算年龄' }
  }
  const text = `${profile.age} 岁`
  if (profile.birth_date) {
    return { text, hint: '按出生日期计算' }
  }
  return { text, hint: '来自对话中提到的年龄，补充出生日期可以更精确' }
}
