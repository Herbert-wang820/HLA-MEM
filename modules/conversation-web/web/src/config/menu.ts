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
    id: 'conversation',
    name: '对话',
    icon: 'chat',
    order: 100,
    route: '/conversation',
    requiredCapability: 'reasoning-orchestrator.turn.process.v1',
    permission: 'conversation-web.chat.use',
    children: [
      {
        id: 'conversation-sessions',
        name: '会话',
        route: '/conversation/sessions',
        icon: 'list',
        order: 110,
        permission: 'conversation-web.session.read',
      },
    ],
  },
]

export const DEV_PERMISSIONS = ['conversation-web.chat.use', 'conversation-web.session.read']

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
