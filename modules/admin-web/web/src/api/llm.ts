export interface LLMConfigView {
  enabled: boolean
  baseUrl: string
  model: string
  apiKeySet: boolean
  temperature: number
  maxTokens: number
  updatedAt: string | null
}

export interface LLMConfigInput {
  enabled: boolean
  baseUrl: string
  model: string
  apiKey?: string
  temperature: number
  maxTokens: number
}

const PATH = '/internal/orchestrator/llm/config'

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `HTTP ${response.status}`
    let code = 'ADMIN_WEB_LLM_CONFIG_FAILED'
    try {
      const body = (await response.json()) as { code?: string; message?: string }
      code = body.code ?? code
      message = body.message ?? message
    } catch {
      // Keep the HTTP fallback.
    }
    throw new Error(`${code}: ${message}`)
  }
  return (await response.json()) as T
}

export async function fetchLLMConfig(): Promise<LLMConfigView> {
  return parse<LLMConfigView>(await fetch(PATH, { headers: { accept: 'application/json' } }))
}

export async function saveLLMConfig(input: LLMConfigInput): Promise<LLMConfigView> {
  return parse<LLMConfigView>(
    await fetch(PATH, {
      method: 'PUT',
      headers: { accept: 'application/json', 'content-type': 'application/json' },
      body: JSON.stringify(input),
    }),
  )
}
