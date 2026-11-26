import type { TurnDone, TurnRequest } from '../types'

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly requestId?: string

  constructor(code: string, message: string, status: number, requestId?: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.requestId = requestId
  }
}

export function newId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const TURNS_PATH = '/api/reasoning-orchestrator/v1/turns'

export async function createTurn(request: TurnRequest, signal?: AbortSignal): Promise<Response> {
  const response = await fetch(TURNS_PATH, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      accept: 'text/event-stream',
      'Idempotency-Key': newId(),
    },
    body: JSON.stringify(request),
    signal,
  })
  if (!response.ok) {
    let code = `HTTP_${response.status}`
    let message = response.statusText || '请求失败'
    let requestId: string | undefined
    try {
      const body = (await response.json()) as { code?: string; message?: string; requestId?: string }
      code = body.code ?? code
      message = body.message ?? message
      requestId = body.requestId
    } catch {
      // Non-JSON error body: keep the HTTP fallback.
    }
    throw new ApiError(code, message, response.status, requestId)
  }
  return response
}

export interface SseHandlers {
  onToken: (text: string) => void
  onDone: (result: TurnDone) => void
  onError: (error: ApiError) => void
}

/** Minimal SSE reader for `event:`/`data:` frames from the turn endpoint. */
export async function readTurnStream(response: Response, handlers: SseHandlers): Promise<void> {
  if (!response.body) {
    handlers.onError(new ApiError('EMPTY_STREAM', '响应没有可读流', response.status))
    return
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let eventName = 'message'
  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const parsed = parseFrame(frame, eventName)
        eventName = parsed.event
        if (parsed.data) {
          dispatch(parsed.event, parsed.data, handlers, response.status)
        }
        boundary = buffer.indexOf('\n\n')
      }
    }
  } finally {
    reader.releaseLock()
  }
}

function parseFrame(frame: string, currentEvent: string): { event: string; data: string } {
  let event = currentEvent
  const dataLines: string[] = []
  for (const rawLine of frame.split('\n')) {
    const line = rawLine.replace(/\r$/, '')
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart())
    }
  }
  return { event, data: dataLines.join('\n') }
}

function dispatch(event: string, data: string, handlers: SseHandlers, status: number): void {
  let payload: unknown
  try {
    payload = JSON.parse(data)
  } catch {
    return
  }
  if (event === 'token' && isRecord(payload) && typeof payload.text === 'string') {
    handlers.onToken(payload.text)
  } else if (event === 'done' && isRecord(payload)) {
    const persona = isRecord(payload.persona) ? payload.persona : {}
    handlers.onDone({
      turnId: String(payload.turnId ?? ''),
      degraded: Boolean(payload.degraded),
      reasons: Array.isArray(payload.reasons) ? payload.reasons.map(String) : [],
      usedEpisodeIds: Array.isArray(payload.usedEpisodeIds) ? payload.usedEpisodeIds.map(String) : [],
      memories: Array.isArray(payload.memories)
        ? payload.memories
            .filter(isRecord)
            .map((memory) => ({
              episodeId: String(memory.episodeId ?? ''),
              score: Number(memory.score ?? 0),
              excerpt: typeof memory.excerpt === 'string' ? memory.excerpt : null,
            }))
            .filter((memory) => memory.episodeId)
        : [],
      persona: {
        identityVersion: typeof persona.identityVersion === 'number' ? persona.identityVersion : null,
        adaptationVersion: typeof persona.adaptationVersion === 'number' ? persona.adaptationVersion : null,
        updated: Boolean(persona.updated),
        degraded: Boolean(persona.degraded),
        identityProposalId: typeof persona.identityProposalId === 'string' ? persona.identityProposalId : null,
      },
    })
  } else if (event === 'error' && isRecord(payload)) {
    handlers.onError(
      new ApiError(
        String(payload.code ?? 'STREAM_ERROR'),
        String(payload.message ?? '流式响应失败'),
        status,
        typeof payload.requestId === 'string' ? payload.requestId : undefined,
      ),
    )
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
