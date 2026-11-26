export type Role = 'user' | 'assistant' | 'system'

export interface ChatMessage {
  id: string
  role: Role
  text: string
}

export interface TurnRequest {
  sessionId: string
  message: string
  stream: boolean
}

export interface MemoryRef {
  episodeId: string
  score: number
  excerpt: string | null
}

export interface PersonaTurnState {
  identityVersion: number | null
  adaptationVersion: number | null
  updated: boolean
  degraded: boolean
  identityProposalId: string | null
}

export interface TurnDone {
  turnId: string
  degraded: boolean
  reasons: string[]
  usedEpisodeIds: string[]
  memories: MemoryRef[]
  persona: PersonaTurnState
}
