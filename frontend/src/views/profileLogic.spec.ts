import { describe, expect, it } from 'vitest'

import { buildProfilePatch, formFromProfile } from '@/views/profileLogic'
import type { ProfileForm } from '@/views/profileLogic'

function form(overrides: Partial<ProfileForm> = {}): ProfileForm {
  return {
    birth_date: '',
    sex: '',
    height_cm: '',
    weight_kg: '',
    waist_cm: '',
    occupation: '',
    sleep_hours: '',
    exercise_days: '',
    sedentary_hours: '',
    smoking_status: '',
    drinking_frequency: '',
    ...overrides,
  }
}

describe('档案保存的请求体', () => {
  it('全空时每个字段都是 null，不是缺键', () => {
    const body = buildProfilePatch(form())

    expect(body.birth_date).toBeNull()
    expect(body.sex).toBeNull()
    expect(body.height_cm).toBeNull()
    expect(body.occupation).toBeNull()
    expect(Object.keys(body.lifestyle).sort()).toEqual([
      'drinking_frequency',
      'exercise_days',
      'sedentary_hours',
      'sleep_hours',
      'smoking_status',
    ])
    expect(Object.values(body.lifestyle)).toEqual([null, null, null, null, null])
  })

  it('数值按数字发，不保留字符串形式', () => {
    const body = buildProfilePatch(form({ height_cm: '170.5', weight_kg: '62', waist_cm: '78' }))

    expect(body.height_cm).toBe(170.5)
    expect(body.weight_kg).toBe(62)
    expect(body.waist_cm).toBe(78)
  })

  it('运动天数为 0 是有效值，不当成没填', () => {
    const body = buildProfilePatch(form({ exercise_days: '0', sedentary_hours: '0' }))

    expect(body.lifestyle.exercise_days).toBe(0)
    expect(body.lifestyle.sedentary_hours).toBe(0)
  })

  it('只填一项时其他项仍然是 null，后端据此删键', () => {
    const body = buildProfilePatch(form({ sleep_hours: '7.5' }))

    expect(body.lifestyle.sleep_hours).toBe(7.5)
    expect(body.lifestyle.exercise_days).toBeNull()
    expect(body.lifestyle.smoking_status).toBeNull()
  })

  it('职业前后空格会去掉，纯空格当作没填', () => {
    expect(buildProfilePatch(form({ occupation: '  教师  ' })).occupation).toBe('教师')
    expect(buildProfilePatch(form({ occupation: '   ' })).occupation).toBeNull()
  })

  it('数值填了非数字时报错，不静默变成 null', () => {
    expect(() => buildProfilePatch(form({ weight_kg: 'abc' }))).toThrow('体重要填数字')
    expect(() => buildProfilePatch(form({ sleep_hours: '七小时' }))).toThrow('平均睡眠时长要填数字')
  })

  it('数值两端有空格也能解析', () => {
    expect(buildProfilePatch(form({ weight_kg: ' 62 ' })).weight_kg).toBe(62)
  })
})

describe('回填表单', () => {
  it('null 回填为空串，0 回填为 "0"', () => {
    const filled = formFromProfile({
      birth_date: null,
      sex: null,
      height_cm: null,
      weight_kg: null,
      waist_cm: null,
      occupation: null,
      lifestyle: { exercise_days: 0, sedentary_hours: 6, sleep_hours: null },
    })

    expect(filled.birth_date).toBe('')
    expect(filled.exercise_days).toBe('0')
    expect(filled.sedentary_hours).toBe('6')
    expect(filled.sleep_hours).toBe('')
  })

  it('小数不会变成科学计数法', () => {
    const filled = formFromProfile({
      birth_date: '1990-05-01',
      sex: 'male',
      height_cm: 170.5,
      weight_kg: 62.25,
      waist_cm: null,
      occupation: '教师',
      lifestyle: {},
    })

    expect(filled.height_cm).toBe('170.5')
    expect(filled.weight_kg).toBe('62.25')
    expect(filled.birth_date).toBe('1990-05-01')
  })

  it('回填后再保存得到同样的值，不会因为格式差异误判成改动', () => {
    const profile = {
      birth_date: '1990-05-01',
      sex: 'male',
      height_cm: 170.5,
      weight_kg: 62,
      waist_cm: null,
      occupation: '教师',
      lifestyle: { sleep_hours: 7.5, exercise_days: 0, smoking_status: 'never' },
    }

    const body = buildProfilePatch(formFromProfile(profile))

    expect(body).toEqual({
      birth_date: '1990-05-01',
      sex: 'male',
      height_cm: 170.5,
      weight_kg: 62,
      waist_cm: null,
      occupation: '教师',
      lifestyle: {
        sleep_hours: 7.5,
        exercise_days: 0,
        sedentary_hours: null,
        smoking_status: 'never',
        drinking_frequency: null,
      },
    })
  })
})
