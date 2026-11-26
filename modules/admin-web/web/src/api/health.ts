export interface UpstreamStatus {
  module: string
  url: string
  healthy: boolean
  latencyMs: number | null
  detail: string | null
}

interface UpstreamsResponse {
  upstreams: UpstreamStatus[]
}

export async function fetchUpstreams(signal?: AbortSignal): Promise<UpstreamStatus[]> {
  const response = await fetch('/internal/upstreams', { signal, headers: { accept: 'application/json' } })
  if (!response.ok) {
    throw new Error(`upstream probe failed with HTTP ${response.status}`)
  }
  const body = (await response.json()) as UpstreamsResponse
  return Array.isArray(body.upstreams) ? body.upstreams : []
}
