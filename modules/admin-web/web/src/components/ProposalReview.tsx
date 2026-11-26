import { useCallback, useEffect, useState } from 'react'
import {
  fetchProposals,
  PersonaApiError,
  reviewProposal,
  type IdentityChangeSet,
  type Proposal,
} from '../api/persona'

function changesSummary(changes: IdentityChangeSet): string {
  const traits = changes.traits.map((item) => `${item.trait}=${item.value}`).join('；') || '无特质'
  const narrative = changes.narrative.length > 0 ? `${changes.narrative.slice(0, 120)}${changes.narrative.length > 120 ? '…' : ''}` : '（空叙事）'
  return `${traits}｜${narrative}`
}

export function ProposalReview() {
  const [items, setItems] = useState<Proposal[]>([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    try {
      const page = await fetchProposals(signal)
      setItems(page.items)
    } catch (cause) {
      if ((cause as Error).name !== 'AbortError') setError((cause as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  const review = async (proposal: Proposal, decision: 'approve' | 'reject') => {
    const prompt =
      decision === 'approve'
        ? '批准后会立即创建新的身份版本，确认批准？'
        : '确认拒绝该提案？'
    const confirmed = typeof window.confirm === 'function' ? window.confirm(prompt) : true
    if (!confirmed) return
    setBusyId(proposal.proposalId)
    setError(null)
    setMessage(null)
    try {
      const updated = await reviewProposal(proposal.proposalId, {
        decision,
        note: note.trim() || undefined,
      })
      setItems((current) => current.map((item) => (item.proposalId === updated.proposalId ? updated : item)))
      setNote('')
      setMessage(`${decision === 'approve' ? '已批准' : '已拒绝'} ${updated.proposalId}`)
    } catch (cause) {
      const text = cause instanceof PersonaApiError ? `${cause.code}: ${cause.message}` : (cause as Error).message
      setError(text)
    } finally {
      setBusyId(null)
    }
  }

  if (loading) return <p className="empty">正在读取提案…</p>

  return (
    <div className="settings" aria-label="提案审批">
      {error ? (
        <p className="form-message form-message--error" role="alert">
          {error}
        </p>
      ) : null}
      {message ? <p className="form-message form-message--ok">{message}</p> : null}
      <div className="toolbar">
        <button type="button" className="button" onClick={() => void load()}>
          刷新
        </button>
        <span className="toolbar__hint">提案由模型或管理员创建；批准后由 persona-state 生成新身份版本。</span>
      </div>

      {items.length === 0 ? <p className="empty">当前没有提案。</p> : null}

      <ul className="proposal-list">
        {items.map((item) => (
          <li key={item.proposalId} className="proposal">
            <div className="proposal__head">
              <strong>{item.status === 'pending' ? '待审批' : item.status === 'approved' ? '已批准' : '已拒绝'}</strong>
              <span className="settings__meta">
                {item.proposalId} · {item.proposer} · {new Date(item.createdAt).toLocaleString()}
              </span>
            </div>
            <p className="proposal__rationale">{item.rationale}</p>
            <p className="proposal__changes">{changesSummary(item.changes)}</p>
            {item.evidenceEpisodeIds.length > 0 ? (
              <p className="settings__meta">证据：{item.evidenceEpisodeIds.join('、')}</p>
            ) : null}
            {item.reviewer ? (
              <p className="settings__meta">
                审阅：{item.reviewer}
                {item.reviewNote ? ` · ${item.reviewNote}` : ''}
              </p>
            ) : null}
            {item.status === 'pending' ? (
              <div className="proposal__actions">
                <button
                  type="button"
                  className="button button--primary"
                  disabled={busyId === item.proposalId}
                  onClick={() => void review(item, 'approve')}
                >
                  批准
                </button>
                <button
                  type="button"
                  className="button"
                  disabled={busyId === item.proposalId}
                  onClick={() => void review(item, 'reject')}
                >
                  拒绝
                </button>
              </div>
            ) : null}
          </li>
        ))}
      </ul>

      <label className="field">
        <span>审批备注（可选，≤2000）</span>
        <input value={note} maxLength={2000} onChange={(event) => setNote(event.target.value)} />
      </label>
    </div>
  )
}
