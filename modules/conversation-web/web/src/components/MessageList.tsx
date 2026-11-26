import type { ChatMessage } from '../types'

interface MessageListProps {
  messages: ChatMessage[]
  pending: boolean
}

export function MessageList({ messages, pending }: MessageListProps) {
  return (
    <ol className="messages" aria-label="消息列表">
      {messages.map((message) => (
        <li key={message.id} className={`message message--${message.role}`}>
          <span className="message__role">{roleLabel(message.role)}</span>
          <p className="message__text">{message.text}</p>
        </li>
      ))}
      {pending ? (
        <li className="message message--assistant" aria-live="polite">
          <span className="message__role">助手</span>
          <p className="message__text message__text--pending">正在生成…</p>
        </li>
      ) : null}
    </ol>
  )
}

function roleLabel(role: ChatMessage['role']): string {
  if (role === 'user') return '你'
  if (role === 'system') return '系统'
  return '助手'
}
