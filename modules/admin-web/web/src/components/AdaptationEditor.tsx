import { useEffect, useState, type FormEvent } from 'react'
import { fetchAdaptation, PersonaApiError, updateAdaptation, type Adaptation } from '../api/persona'

interface FormState {
  values: Record<string, string>
  newDimension: string
  reason: string
}

function toForm(adaptation: Adaptation): FormState {
  return {
    values: Object.fromEntries(Object.entries(adaptation.values).map(([key, value]) => [key, String(value)])),
    newDimension: '',
    reason: '',
  }
}

const MAX_DELTA = 0.15

export function AdaptationEditor({ canEdit = true }: { canEdit?: boolean }) {
  const [adaptation, setAdaptation] = useState<Adaptation | null>(null)
  const [form, setForm] = useState<FormState>({ values: {}, newDimension: '', reason: '' })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchAdaptation(controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return
        setAdaptation(value)
        setForm(toForm(value))
      })
      .catch((cause: Error) => {
        if (cause.name !== 'AbortError') setError(cause.message)
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  const updateValue = (dimension: string, value: string) => {
    setForm((current) => ({ ...current, values: { ...current.values, [dimension]: value } }))
    setSaved(null)
  }

  const addDimension = () => {
    const name = form.newDimension.trim()
    if (!name) return
    setForm((current) => ({
      ...current,
      values: { ...current.values, [name]: current.values[name] ?? '0' },
      newDimension: '',
    }))
    setSaved(null)
  }

  const removeDimension = (dimension: string) => {
    setForm((current) => {
      const next = { ...current.values }
      delete next[dimension]
      return { ...current, values: next }
    })
    setSaved(null)
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!adaptation) return
    if (!form.reason.trim()) {
      setError('请填写调整原因；适应层每次漂移都会写入审计。')
      return
    }
    const deltas: Record<string, number> = {}
    for (const [dimension, raw] of Object.entries(form.values)) {
      const next = Number(raw)
      const before = adaptation.values[dimension] ?? 0
      const delta = Number((next - before).toFixed(6))
      if (!Number.isFinite(delta)) {
        setError(`维度 ${dimension} 的取值无效。`)
        return
      }
      if (Math.abs(delta) > MAX_DELTA) {
        setError(`维度 ${dimension} 的单次变化 ${delta} 超过上限 ${MAX_DELTA}。`)
        return
      }
      if (Math.abs(delta) > 1e-9) deltas[dimension] = delta
    }
    if (Object.keys(deltas).length === 0) {
      setError('没有变化可提交。')
      return
    }
    setSaving(true)
    setError(null)
    setSaved(null)
    try {
      const next = await updateAdaptation({
        expectedVersion: adaptation.version,
        deltas,
        reason: form.reason.trim(),
      })
      setAdaptation(next)
      setForm(toForm(next))
      setSaved(`已更新适应层 v${next.version}`)
    } catch (cause) {
      const message = cause instanceof PersonaApiError ? `${cause.code}: ${cause.message}` : (cause as Error).message
      setError(message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p className="empty">正在读取适应层…</p>

  const drift = adaptation?.drift ?? 0

  return (
    <form className="settings" onSubmit={submit} aria-label="适应层编辑器">
      {adaptation ? (
        <p className="settings__meta">
          当前 v{adaptation.version} · 窗口漂移 {drift.toFixed(3)} / 0.30 · 更新于{' '}
          {new Date(adaptation.updatedAt).toLocaleString()}
        </p>
      ) : null}
      {error ? (
        <p className="form-message form-message--error" role="alert">
          {error}
        </p>
      ) : null}
      {saved ? <p className="form-message form-message--ok">{saved}</p> : null}

      <div className="field">
        <span>维度取值（0–1，单次变化 ≤ {MAX_DELTA}）</span>
        {Object.entries(form.values).map(([dimension, value]) => (
          <div className="trait-row" key={dimension}>
            <input aria-label={`维度 ${dimension} 名称`} value={dimension} readOnly />
            <input
              aria-label={`维度 ${dimension} 取值`}
              type="number"
              min="0"
              max="1"
              step="0.01"
              value={value}
              onChange={(event) => updateValue(dimension, event.target.value)}
            />
            <button type="button" className="button" onClick={() => removeDimension(dimension)}>
              删除
            </button>
          </div>
        ))}
        <div className="trait-row">
          <input
            aria-label="新维度名称"
            value={form.newDimension}
            onChange={(event) => setForm((current) => ({ ...current, newDimension: event.target.value }))}
            placeholder="例如 focus"
          />
          <button type="button" className="button" onClick={addDimension}>
            添加维度
          </button>
        </div>
      </div>

      <label className="field">
        <span>调整原因</span>
        <input
          value={form.reason}
          maxLength={500}
          onChange={(event) => {
            setForm((current) => ({ ...current, reason: event.target.value }))
            setSaved(null)
          }}
          placeholder="例如：用户希望更简洁"
        />
      </label>

      <p className="settings__note">
        适应层有界更新：每维单次 |Δ| ≤ 0.15，24 小时窗口累计漂移 ≤ 0.30；超限由 persona-state 返回 409/422，前端不会截断。
      </p>
      <button type="submit" className="button button--primary" disabled={saving || !canEdit}>
        {saving ? '保存中…' : '提交调整'}
      </button>
      {!canEdit ? (
        <p className="settings__note">当前账号只有只读权限（缺少 admin-web.persona.edit），提交仍会被后端拒绝。</p>
      ) : null}
    </form>
  )
}
