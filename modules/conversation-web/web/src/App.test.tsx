import { render, screen } from '@testing-library/react'
import App from './App'

describe('conversation app', () => {
  it('renders the conversation shell', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: '对话' })).toBeInTheDocument()
    expect(screen.getByLabelText('消息列表')).toBeInTheDocument()
    expect(screen.getByLabelText('输入消息')).toBeInTheDocument()
  })

  it('hides menu entries the identity cannot use', () => {
    render(<App permissions={[]} />)
    expect(screen.queryByRole('link', { name: '对话' })).not.toBeInTheDocument()
  })

  it('explains that identity changes are proposal-only', () => {
    render(<App />)
    expect(screen.getByText(/身份层变更只会生成提案/)).toBeInTheDocument()
  })
})
