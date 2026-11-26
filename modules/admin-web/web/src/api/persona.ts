export interface TraitValue {
  trait: string
  value: string
  confidence: number
}

export interface PersonaIdentity {
  version: number
  traits: TraitValue[]
  narrative: string
  effectiveFrom: string
  createdAt: string
  createdBy: string
}

export interface Adaptation {
  version: number
  values: Record<string, number>
  updatedAt: string
  drift: number
}

export interface IdentityChangeSet {
  traits: TraitValue[]
  narrative: string
}

export interface Proposal {
  proposalId: string
  status: 'pending' | 'approved' | 'rejected'
  proposer: string
  rationale: string
  changes: IdentityChangeSet
  evidenceEpisodeIds: string[]
  createdAt: string
  reviewedAt: string | null
  reviewer: string | null
  reviewNote: string | null
}

export interface ProposalPage {
  items: Proposal[]
  nextCursor: string | null
  hasMore: boolean
}

const BASE = '/api/persona-state/v1'

export class PersonaApiError extends Error {
  readonly code: string
  readonly status: number

  constructor(code: string, message: string, status: number) {
    super(message)
    this.name = 'PersonaApiError'
    this.code = code
    this.status = status
  }
}

export function newRequestId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `admin-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let code = `PERSONA_STATE_HTTP_${response.status}`
    let message = `HTTP ${response.status}`
    try {
      const body = (await response.json()) as { code?: string; message?: string }
      code = body.code ?? code
      message = body.message ?? message
    } catch {
      // Keep the HTTP fallback.
    }
    throw new PersonaApiError(code, message, response.status)
  }
  return (await response.json()) as T
}

export async function fetchIdentity(signal?: AbortSignal): Promise<PersonaIdentity> {
  return parse<PersonaIdentity>(await fetch(`${BASE}/identity`, { signal, headers: { accept: 'application/json' } }))
}

export async function createIdentityVersion(input: {
  traits: TraitValue[]
  narrative: string
  changeReason: string
}): Promise<PersonaIdentity> {
  return parse<PersonaIdentity>(
    await fetch(`${BASE}/identity/versions`, {
      method: 'POST',
      headers: {
        accept: 'application/json',
        'content-type': 'application/json',
        'Idempotency-Key': newRequestId(),
      },
      body: JSON.stringify(input),
    }),
  )
}

export async function rollbackIdentity(input: {
  targetVersion: number
  changeReason: string
}): Promise<PersonaIdentity> {
  return parse<PersonaIdentity>(
    await fetch(`${BASE}/identity/rollback`, {
      method: 'POST',
      headers: {
        accept: 'application/json',
        'content-type': 'application/json',
        'Idempotency-Key': newRequestId(),
      },
      body: JSON.stringify(input),
    }),
  )
}

export async function fetchAdaptation(signal?: AbortSignal): Promise<Adaptation> {
  return parse<Adaptation>(await fetch(`${BASE}/adaptation`, { signal, headers: { accept: 'application/json' } }))
}

export async function updateAdaptation(input: {
  expectedVersion: number
  deltas: Record<string, number>
  reason: string
}): Promise<Adaptation> {
  return parse<Adaptation>(
    await fetch(`${BASE}/adaptation`, {
      method: 'PATCH',
      headers: { accept: 'application/json', 'content-type': 'application/json' },
      body: JSON.stringify(input),
    }),
  )
}

export async function fetchProposals(signal?: AbortSignal): Promise<ProposalPage> {
  return parse<ProposalPage>(
    await fetch(`${BASE}/proposals?limit=50`, { signal, headers: { accept: 'application/json' } }),
  )
}

export async function createProposal(input: {
  rationale: string
  changes: IdentityChangeSet
  evidenceEpisodeIds?: string[]
}): Promise<Proposal> {
  return parse<Proposal>(
    await fetch(`${BASE}/proposals`, {
      method: 'POST',
      headers: {
        accept: 'application/json',
        'content-type': 'application/json',
        'Idempotency-Key': newRequestId(),
      },
      body: JSON.stringify(input),
    }),
  )
}

export async function reviewProposal(
  proposalId: string,
  input: { decision: 'approve' | 'reject'; note?: string },
): Promise<Proposal> {
  return parse<Proposal>(
    await fetch(`${BASE}/proposals/${encodeURIComponent(proposalId)}/review`, {
      method: 'POST',
      headers: {
        accept: 'application/json',
        'content-type': 'application/json',
        'Idempotency-Key': newRequestId(),
      },
      body: JSON.stringify(input),
    }),
  )
}
