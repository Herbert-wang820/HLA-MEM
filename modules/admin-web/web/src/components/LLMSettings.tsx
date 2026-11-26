import { useEffect, useState, type FormEvent } from 'react'
import { fetchLLMConfig, saveLLMConfig, type LLMConfigView } from '../api/llm'

interface FormState {
  enabled: boolean
  baseUrl: string
  model: string
  temperature: string
  maxTokens: string
}

const EMPTY: FormState = {
  enabled: false,
  baseUrl: 'https://api.openai.com/v1',
  model: 'gpt-4o-mini',
  temperature: '0.7',
  maxTokens: '512',
}

function toForm(config: LLMConfigView): FormState {
  return {
    enabled: config.enabled,
    baseUrl: config.baseUrl,
    model: config.model,
    temperature: String(config.temperature),
    maxTokens: String(config.maxTokens),
  }
}

export function LLMSettings() {
  const [config, setConfig] = useState<LLMConfigView | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY)
  const [apiKey, setApiKey] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    fetchLLMConfig()
      .then((value) => {
        if (controller.signal.aborted) return
        setConfig(value)
        setForm(toForm(value))
      })
      .catch((cause: Error) => setError(cause.message))
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }))
    setSaved(false)
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      const next = await saveLLMConfig({
        enabled: form.enabled,
        baseUrl: form.baseUrl.trim(),
        model: form.model.trim(),
        apiKey: apiKey.trim() ? apiKey.trim() : undefined,
        temperature: Number(form.temperature),
        maxTokens: Number(form.maxTokens),
      })
      setConfig(next)
      setForm(toForm(next))
      setApiKey('')
      setSaved(true)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p className="empty">正在读取模型配置…</p>

  return (
    <form className="settings" onSubmit={submit}>
      {error ? (
        <p className="form-message form-message--error" role="alert">
          {error}
        </p>
      ) : null}
      {saved ? <p className="form-message form-message--ok">已保存</p> : null}

      <label className="check">
        <input
          type="checkbox"
          checked={form.enabled}
          onChange={(event) => update('enabled', event.target.checked)}
        />
        启用大模型（关闭时使用确定性模板回复）
      </label>

      <label className="field">
        <span>Base URL</span>
        <input
          value={form.baseUrl}
          onChange={(event) => update('baseUrl', event.target.value)}
          placeholder="https://api.openai.com/v1"
          required={form.enabled}
        />
      </label>

      <label className="field">
        <span>模型</span>
        <input
          value={form.model}
          onChange={(event) => update('model', event.target.value)}
          placeholder="gpt-4o-mini"
          required={form.enabled}
        />
      </label>

      <label className="field">
        <span>API Key</span>
        <input
          type="password"
          value={apiKey}
          onChange={(event) => {
            setApiKey(event.target.value)
            setSaved(false)
          }}
          placeholder={config?.apiKeySet ? '已保存，留空保持不变' : 'sk-...'}
          autoComplete="new-password"
        />
      </label>

      <div className="field-row">
        <label className="field">
          <span>温度</span>
          <input
            type="number"
            min="0"
            max="2"
            step="0.1"
            value={form.temperature}
            onChange={(event) => update('temperature', event.target.value)}
          />
        </label>
        <label className="field">
          <span>最大 tokens</span>
          <input
            type="number"
            min="1"
            max="8192"
            value={form.maxTokens}
            onChange={(event) => update('maxTokens', event.target.value)}
          />
        </label>
      </div>

      <p className="settings__note">
        API Key 只写不读，保存在编排器本机文件的 0600 权限下；页面和接口都不会回显密钥。演示用途，生产请改用密钥管理服务。
      </p>
      <p className="settings__meta">
        状态：{config?.enabled ? '已启用' : '未启用'} · 密钥：{config?.apiKeySet ? '已保存' : '未保存'}
        {config?.updatedAt ? ` · 更新于 ${new Date(config.updatedAt).toLocaleString()}` : ''}
      </p>

      <button type="submit" className="button button--primary" disabled={saving}>
        {saving ? '保存中…' : '保存'}
      </button>
    </form>
  )
}
