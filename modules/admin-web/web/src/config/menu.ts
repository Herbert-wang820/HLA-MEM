export interface MenuItem {
  id: string
  name: string
  route: string
  icon: string
  order: number
  permission: string
  requiredCapability?: string
  children?: MenuItem[]
}

/** Mirrors contracts/menu.yaml; keep both in sync. */
export const MENU: MenuItem[] = [
  {
    id: 'admin-persona',
    name: '人格',
    icon: 'persona',
    order: 200,
    route: '/admin/persona',
    requiredCapability: 'persona-state.identity.read.v1',
    permission: 'admin-web.persona.view',
    children: [
      {
        id: 'admin-persona-identity',
        name: '身份层',
        route: '/admin/persona/identity',
        icon: 'id',
        order: 201,
        permission: 'admin-web.persona.view',
      },
      {
        id: 'admin-persona-adaptation',
        name: '适应层',
        route: '/admin/persona/adaptation',
        icon: 'sliders',
        order: 202,
        permission: 'admin-web.persona.view',
      },
    ],
  },
  {
    id: 'admin-memory',
    name: '记忆图',
    icon: 'graph',
    order: 210,
    route: '/admin/memory',
    requiredCapability: 'memory-graph.graph.read.v1',
    permission: 'admin-web.memory.view',
  },
  {
    id: 'admin-audit',
    name: '检索审计',
    icon: 'audit',
    order: 220,
    route: '/admin/audit',
    requiredCapability: 'reasoning-orchestrator.audit.read.v1',
    permission: 'admin-web.audit.view',
  },
  {
    id: 'admin-consolidation',
    name: '巩固监控',
    icon: 'queue',
    order: 230,
    route: '/admin/consolidation',
    requiredCapability: 'async-consolidator.backlog.read.v1',
    permission: 'admin-web.consolidation.view',
  },
  {
    id: 'admin-proposals',
    name: '提案审批',
    icon: 'review',
    order: 240,
    route: '/admin/proposals',
    requiredCapability: 'persona-state.proposal.review.v1',
    permission: 'admin-web.proposal.review',
  },
  {
    id: 'admin-llm',
    name: '模型设置',
    icon: 'settings',
    order: 250,
    route: '/admin/llm',
    requiredCapability: 'reasoning-orchestrator.llm.configure.v1',
    permission: 'admin-web.llm.manage',
  },
]

export const DEV_PERMISSIONS = [
  'admin-web.persona.view',
  'admin-web.persona.edit',
  'admin-web.memory.view',
  'admin-web.audit.view',
  'admin-web.consolidation.view',
  'admin-web.proposal.review',
  'admin-web.llm.manage',
]

export function visibleMenu(items: MenuItem[], permissions: readonly string[]): MenuItem[] {
  const granted = new Set(permissions)
  return items
    .filter((item) => granted.has(item.permission))
    .map((item) => ({
      ...item,
      children: item.children ? visibleMenu(item.children, permissions) : undefined,
    }))
    .sort((left, right) => left.order - right.order)
}
