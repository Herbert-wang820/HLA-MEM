import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'
import App from './App'

const UPSTREAMS = {
  upstreams: [
    { module: 'memory-graph', url: 'http://127.0.0.1:8082', healthy: true, latencyMs: 12, detail: null },
    { module: 'persona-state', url: 'http://127.0.0.1:8083', healthy: false, latencyMs: null, detail: 'timeout' },
  ],
}

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => UPSTREAMS,
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('admin app', () => {
  it('renders the admin shell', async () => {
    render(<App />)
    expect(await screen.findByText('memory-graph')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'HLA-MEM 管理端' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: '管理导航' })).toBeInTheDocument()
  })

  it('shows upstream health from the sidecar probe', async () => {
    render(<App />)
    expect(await screen.findByText('memory-graph')).toBeInTheDocument()
    expect(await screen.findByText('persona-state')).toBeInTheDocument()
    expect(await screen.findByText('正常')).toBeInTheDocument()
    expect(await screen.findByText('不可达')).toBeInTheDocument()
  })

  it('hides menu entries without permission', async () => {
    render(<App permissions={[]} />)
    expect(await screen.findByText('memory-graph')).toBeInTheDocument()
    expect(screen.getByText('当前身份没有可用菜单。')).toBeInTheDocument()
    expect(screen.getByText('没有可展示的模块。')).toBeInTheDocument()
  })

  it('selects the first permitted menu entry', async () => {
    render(<App permissions={['admin-web.memory.view']} />)
    expect(await screen.findByText('memory-graph')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /记忆图/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /人格/ })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '记忆图' })).toBeInTheDocument()
  })
})


  it('saves the LLM configuration without echoing the secret', async () => {
    const config = {
      enabled: false,
      baseUrl: 'https://api.openai.com/v1',
      model: 'gpt-4o-mini',
      apiKeySet: false,
      temperature: 0.7,
      maxTokens: 512,
      updatedAt: null,
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/internal/upstreams')) {
        return { ok: true, json: async () => UPSTREAMS }
      }
      if (url.includes('/internal/orchestrator/llm/config')) {
        if (init?.method === 'PUT') {
          return {
            ok: true,
            json: async () => ({
              ...config,
              enabled: true,
              baseUrl: 'http://127.0.0.1:9999/v1',
              apiKeySet: true,
            }),
          }
        }
        return { ok: true, json: async () => config }
      }
      return { ok: false, status: 404, json: async () => ({ code: 'NOT_FOUND' }) }
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App permissions={['admin-web.llm.manage']} />)
    expect(await screen.findByLabelText('Base URL')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Base URL'), {
      target: { value: 'http://127.0.0.1:9999/v1' },
    })
    fireEvent.change(screen.getByLabelText('API Key'), { target: { value: 'sk-demo-secret' } })
    fireEvent.click(screen.getByRole('button', { name: '保存' }))

    expect(await screen.findByText('已保存')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/internal/orchestrator/llm/config',
      expect.objectContaining({ method: 'PUT' }),
    )
  })

  it('edits the identity layer and shows the new version', async () => {
    const identity = {
      version: 2,
      traits: [{ trait: 'tone', value: '温和', confidence: 0.8 }],
      narrative: '你是一位耐心的对话伙伴。',
      effectiveFrom: '2026-11-10T00:00:00Z',
      createdAt: '2026-11-10T00:00:00Z',
      createdBy: 'dev-user',
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/internal/upstreams')) return { ok: true, json: async () => UPSTREAMS }
      if (url.endsWith('/identity/versions') && init?.method === 'POST') {
        return { ok: true, json: async () => ({ ...identity, version: 3, narrative: '更直接' }) }
      }
      if (url.endsWith('/identity')) return { ok: true, json: async () => identity }
      return { ok: false, status: 404, json: async () => ({ code: 'NOT_FOUND' }) }
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('confirm', vi.fn(() => true))

    render(<App permissions={['admin-web.persona.view', 'admin-web.persona.edit']} />)
    fireEvent.click(await screen.findByRole('button', { name: '身份层' }))
    expect(await screen.findByRole('form', { name: '身份层编辑器' })).toBeInTheDocument()
    expect(await screen.findByText(/当前 v2/)).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('变更原因'), { target: { value: '用户偏好变化' } })
    fireEvent.click(screen.getByRole('button', { name: '保存为新版本' }))
    expect(await screen.findByText('已创建身份版本 v3')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/persona-state/v1/identity/versions',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('edits the adaptation layer within the bounded step', async () => {
    const adaptation = {
      version: 4,
      values: { warmth: 0.6 },
      updatedAt: '2026-11-10T00:00:00Z',
      drift: 0.1,
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/internal/upstreams')) return { ok: true, json: async () => UPSTREAMS }
      if (url.endsWith('/adaptation') && init?.method === 'PATCH') {
        return { ok: true, json: async () => ({ ...adaptation, version: 5, values: { warmth: 0.7 } }) }
      }
      if (url.endsWith('/adaptation')) return { ok: true, json: async () => adaptation }
      return { ok: false, status: 404, json: async () => ({ code: 'NOT_FOUND' }) }
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App permissions={['admin-web.persona.view', 'admin-web.persona.edit']} />)
    fireEvent.click(await screen.findByRole('button', { name: '适应层' }))
    expect(await screen.findByRole('form', { name: '适应层编辑器' })).toBeInTheDocument()

    fireEvent.change(await screen.findByLabelText('维度 warmth 取值'), { target: { value: '0.7' } })
    fireEvent.change(screen.getByLabelText('调整原因', { exact: false }), { target: { value: '更温暖' } })
    fireEvent.click(screen.getByRole('button', { name: '提交调整' }))

    expect(await screen.findByText('已更新适应层 v5')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/persona-state/v1/adaptation',
      expect.objectContaining({ method: 'PATCH' }),
    )
  })

  it('disables persona editing without the edit permission', async () => {
    const identity = {
      version: 1,
      traits: [{ trait: 'tone', value: '温和', confidence: 0.8 }],
      narrative: '耐心、务实',
      effectiveFrom: '2026-11-10T00:00:00Z',
      createdAt: '2026-11-10T00:00:00Z',
      createdBy: 'dev-user',
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/internal/upstreams')) return { ok: true, json: async () => UPSTREAMS }
      if (url.endsWith('/identity')) return { ok: true, json: async () => identity }
      return { ok: false, status: 404, json: async () => ({ code: 'NOT_FOUND' }) }
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App permissions={['admin-web.persona.view']} />)
    fireEvent.click(await screen.findByRole('button', { name: '身份层' }))
    expect(await screen.findByRole('button', { name: '保存为新版本' })).toBeDisabled()
    expect(screen.getByText(/缺少 admin-web.persona.edit/)).toBeInTheDocument()
  })

  it('reviews a pending proposal with an explicit confirmation', async () => {
    const changes = {
      traits: [{ trait: 'directness', value: '直接', confidence: 0.9 }],
      narrative: '直接、务实',
    }
    const proposal = {
      proposalId: '11111111-1111-4111-8111-111111111111',
      status: 'pending',
      proposer: 'model',
      rationale: '用户多次希望更直接',
      changes,
      evidenceEpisodeIds: [],
      createdAt: '2026-11-10T00:00:00Z',
      reviewedAt: null,
      reviewer: null,
      reviewNote: null,
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/internal/upstreams')) return { ok: true, json: async () => UPSTREAMS }
      if (url.includes('/proposals?limit=')) {
        return { ok: true, json: async () => ({ items: [proposal], nextCursor: null, hasMore: false }) }
      }
      if (url.endsWith('/review') && init?.method === 'POST') {
        return { ok: true, json: async () => ({ ...proposal, status: 'approved', reviewer: 'dev-user' }) }
      }
      return { ok: false, status: 404, json: async () => ({ code: 'NOT_FOUND' }) }
    })
    vi.stubGlobal('fetch', fetchMock)
    const confirm = vi.fn(() => true)
    vi.stubGlobal('confirm', confirm)

    render(<App permissions={['admin-web.proposal.review']} />)
    expect(await screen.findByLabelText('提案审批')).toBeInTheDocument()
    expect(await screen.findByText('用户多次希望更直接')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '批准' }))
    expect(confirm).toHaveBeenCalled()
    expect(await screen.findByText('已批准 11111111-1111-4111-8111-111111111111')).toBeInTheDocument()
  })
