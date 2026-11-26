import { useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, createTurn, newId, readTurnStream } from './api/orchestrator'
import { Composer } from './components/Composer'
import { DegradationBanner } from './components/DegradationBanner'
import { MessageList } from './components/MessageList'
import { DEV_PERMISSIONS, MENU, visibleMenu } from './config/menu'
import type { ChatMessage, MemoryRef } from './types'

const WELCOME: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  text: '你好，我是 HLA-MEM 对话端。编排器会读取人格身份层与适应层，并在需要时按有界规则调整适应层；身份层变更只能提请管理员审批。',
}

export default function App({ permissions = DEV_PERMISSIONS }: { permissions?: readonly string[] }) {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME])
  const [pending, setPending] = useState(false)
  const [banner, setBanner] = useState<string | null>(null)
  const [memories, setMemories] = useState<MemoryRef[]>([])
  const [personaNote, setPersonaNote] = useState<string | null>(null)
  const [sessionId] = useState(() => newId())
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const menu = useMemo(() => visibleMenu(MENU, permissions), [permissions])

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
  }, [messages, pending])

  useEffect(() => () => abortRef.current?.abort(), [])

  const send = async (text: string) => {
    const userMessage: ChatMessage = { id: newId(), role: 'user', text }
    const assistantId = newId()
    setMessages((current) => [...current, userMessage, { id: assistantId, role: 'assistant', text: '' }])
    setPending(true)
    setBanner(null)
    setMemories([])
    setPersonaNote(null)

    const controller = new AbortController()
    abortRef.current = controller
    try {
      const response = await createTurn({ sessionId, message: text, stream: true }, controller.signal)
      await readTurnStream(response, {
        onToken: (token) => {
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantId ? { ...message, text: message.text + token } : message,
            ),
          )
        },
        onDone: (result) => {
          setMemories(result.memories)
          if (result.persona.updated) {
            setPersonaNote(
              result.persona.identityProposalId
                ? `已提交身份变更提案 ${result.persona.identityProposalId}，等待管理员审批。`
                : `人格适应层已更新到 v${result.persona.adaptationVersion ?? '?'}。`,
            )
          }
          if (result.degraded) {
            setBanner(`回合 ${result.turnId} 以降级模式完成：${result.reasons.join('、') || '依赖不可用'}`)
          }
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantId && message.text === ''
                ? { ...message, text: '（空响应）' }
                : message,
            ),
          )
        },
        onError: (error) => {
          setBanner(`${error.code}：${error.message}`)
        },
      })
    } catch (error) {
      const apiError =
        error instanceof ApiError
          ? error
          : new ApiError('NETWORK_ERROR', '无法连接编排器，请确认服务已启动。', 0)
      setBanner(`${apiError.code}：${apiError.message}`)
      setMessages((current) => current.filter((message) => message.id !== assistantId))
    } finally {
      setPending(false)
      abortRef.current = null
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand__mark" aria-hidden="true">
            H
          </span>
          <div>
            <strong>HLA-MEM</strong>
            <span className="brand__sub">对话端</span>
          </div>
        </div>
        <nav aria-label="主导航">
          {menu.map((item) => (
            <div key={item.id} className="nav-group">
              <a className="nav-item nav-item--active" href={item.route}>
                {item.name}
              </a>
              {item.children?.map((child) => (
                <span key={child.id} className="nav-item nav-item--disabled" aria-disabled="true">
                  {child.name}
                  <em>阶段 0</em>
                </span>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar__footer">
          <span className="dot dot--idle" aria-hidden="true" />
          编排器未连接
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>对话</h1>
            <p className="topbar__sub">记忆增强的长期陪伴对话</p>
          </div>
          <span className="badge">编排器 · 人格已接入</span>
        </header>

        {banner ? <DegradationBanner message={banner} onDismiss={() => setBanner(null)} /> : null}
        {personaNote ? (
          <p className="persona-note" role="status">
            {personaNote}
          </p>
        ) : null}

        <section className="chat" aria-label="对话区域">
          <MessageList messages={messages} pending={pending} />
          <div ref={bottomRef} />
        </section>

        {memories.length > 0 ? (
          <aside className="recall" aria-label="本次回忆">
            <h2>本次回忆</h2>
            <ol>
              {memories.map((memory) => (
                <li key={memory.episodeId}>
                  <span className="recall__score">{Math.round(memory.score * 100)}%</span>
                  <p>{memory.excerpt ?? memory.episodeId}</p>
                </li>
              ))}
            </ol>
          </aside>
        ) : null}

        <Composer disabled={pending} onSend={send} />
        <p className="hint">
          适应层由模型在回复内通过隐藏标记有界调整；身份层变更只会生成提案，需管理员在管理端审批。消息不会离开本机。
        </p>
      </main>
    </div>
  )
}
