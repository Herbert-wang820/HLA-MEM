import { useState, type FormEvent, type KeyboardEvent } from 'react'

interface ComposerProps {
  disabled: boolean
  onSend: (text: string) => void
}

export function Composer({ disabled, onSend }: ComposerProps) {
  const [value, setValue] = useState('')

  const submit = (event?: FormEvent) => {
    event?.preventDefault()
    const text = value.trim()
    if (!text || disabled) return
    onSend(text)
    setValue('')
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form className="composer" onSubmit={submit}>
      <label className="sr-only" htmlFor="composer-input">
        输入消息
      </label>
      <textarea
        id="composer-input"
        className="composer__input"
        placeholder="输入消息，Enter 发送，Shift+Enter 换行"
        rows={2}
        value={value}
        disabled={disabled}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={onKeyDown}
        maxLength={8000}
      />
      <button className="composer__send" type="submit" disabled={disabled || !value.trim()}>
        发送
      </button>
    </form>
  )
}
