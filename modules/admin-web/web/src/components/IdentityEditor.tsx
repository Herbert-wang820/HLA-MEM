import { useEffect, useState, type FormEvent } from 'react'
import {
  createIdentityVersion,
  fetchIdentity,
  PersonaApiError,
  type PersonaIdentity,
  type TraitValue,
} from '../api/persona'

interface TraitDraft {
  trait: string
  value: string
  confidence: string
}

interface FormState {
  traits: TraitDraft[]
  narrative: string
  changeReason: string
}

const EMPTY_TRAIT: TraitDraft = { trait: '', value: '', confidence: '0.8' }

function toForm(identity: PersonaIdentity): FormState {
  return {
    traits: identity.traits.map((item) => ({
      trait: item.trait,
      value: item.value,
      confidence: String(item.confidence),
    })),
    narrative: identity.narrative,
    changeReason: '',
  }
}

function toPayload(traits: TraitDraft[]): TraitValue[] {
  return traits
    .map((item) => ({
      trait: item.trait.trim(),
      value: item.value.trim(),
      confidence: Number(item.confidence),
    }))
    .filter((item) => item.trait.length > 0 && item.value.length > 0)
}

export function IdentityEditor({ canEdit = true }: { canEdit?: boolean }) {
  const [identity, setIdentity] = useState<PersonaIdentity | null>(null)
  const [form, setForm] = useState<FormState>({ traits: [], narrative: '', changeReason: '' })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchIdentity(controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return
        setIdentity(value)
        setForm(toForm(value))
      })
      .catch((cause: Error) => {
        if (cause.name !== 'AbortError') setError(cause.message)
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  const updateTrait = (index: number, key: keyof TraitDraft, value: string) => {
    setForm((current) => ({
      ...current,
      traits: current.traits.map((item, position) => (position === index ? { ...item, [key]: value } : item)),
    }))
    setSaved(null)
  }

  const addTrait = () => {
    setForm((current) => ({ ...current, traits: [...current.traits, { ...EMPTY_TRAIT }] }))
    setSaved(null)
  }

  const removeTrait = (index: number) => {
    setForm((current) => ({ ...current, traits: current.traits.filter((_, position) => position !== index) }))
    setSaved(null)
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const traits = toPayload(form.traits)
    if (traits.length === 0) {
      setError('至少保留一个包含 trait 与 value 的特质。')
      return
    }
    if (!form.changeReason.trim()) {
      setError('请填写变更原因；身份层每次变更都会留痕。')
      return
    }
    const confirmed =
      typeof window.confirm === 'function'
        ? window.confirm('身份层变更会创建新版本且不可原地修改，确认提交？')
        : true
    if (!confirmed) return
    setSaving(true)
    setError(null)
    setSaved(null)
    try {
      const next = await createIdentityVersion({
        traits,
        narrative: form.narrative,
        changeReason: form.changeReason.trim(),
      })
      setIdentity(next)
      setForm(toForm(next))
      setSaved(`已创建身份版本 v${next.version}`)
    } catch (cause) {
      const message = cause instanceof PersonaApiError ? `${cause.code}: ${cause.message}` : (cause as Error).message
      setError(message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p className="empty">正在读取身份层…</p>

  return (
    <form className="settings" onSubmit={submit} aria-label="身份层编辑器">
      {identity ? (
        <p className="settings__meta">
          当前 v{identity.version} · 创建者 {identity.createdBy} · 生效于{' '}
          {new Date(identity.effectiveFrom).toLocaleString()}
        </p>
      ) : null}
      {error ? (
        <p className="form-message form-message--error" role="alert">
          {error}
        </p>
      ) : null}
      {saved ? <p className="form-message form-message--ok">{saved}</p> : null}

      <div className="field">
        <span>稳定特质</span>
        {form.traits.map((item, index) => (
          <div className="trait-row" key={`trait-${index}`}>
            <input
              aria-label={`特质 ${index + 1} 名称`}
              value={item.trait}
              onChange={(event) => updateTrait(index, 'trait', event.target.value)}
              placeholder="tone"
            />
            <input
              aria-label={`特质 ${index + 1} 取值`}
              value={item.value}
              onChange={(event) => updateTrait(index, 'value', event.target.value)}
              placeholder="温和、务实"
            />
            <input
              aria-label={`特质 ${index + 1} 置信度`}
              type="number"
              min="0"
              max="1"
              step="0.05"
              value={item.confidence}
              onChange={(event) => updateTrait(index, 'confidence', event.target.value)}
            />
            <button type="button" className="button" onClick={() => removeTrait(index)}>
              删除
            </button>
          </div>
        ))}
        <button type="button" className="button" onClick={addTrait}>
          添加特质
        </button>
      </div>

      <label className="field">
        <span>身份叙事</span>
        <textarea
          rows={6}
          maxLength={8000}
          value={form.narrative}
          onChange={(event) => {
            setForm((current) => ({ ...current, narrative: event.target.value }))
            setSaved(null)
          }}
        />
      </label>

      <label className="field">
        <span>变更原因</span>
        <input
          value={form.changeReason}
          maxLength={500}
          onChange={(event) => {
            setForm((current) => ({ ...current, changeReason: event.target.value }))
            setSaved(null)
          }}
          placeholder="例如：用户要求更直接"
        />
      </label>

      <p className="settings__note">
        保存会创建新的身份版本，不修改历史版本；也可在“提案审批”中批准模型或管理员提交的身份变更提案。
      </p>
      <button type="submit" className="button button--primary" disabled={saving || !canEdit}>
        {saving ? '保存中…' : '保存为新版本'}
      </button>
      {!canEdit ? (
        <p className="settings__note">当前账号只有只读权限（缺少 admin-web.persona.edit），保存仍会被后端拒绝。</p>
      ) : null}
    </form>
  )
}
