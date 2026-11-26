import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchUpstreams, type UpstreamStatus } from './api/health'
import { AdaptationEditor } from './components/AdaptationEditor'
import { IdentityEditor } from './components/IdentityEditor'
import { LLMSettings } from './components/LLMSettings'
import { ProposalReview } from './components/ProposalReview'
import { DEV_PERMISSIONS, MENU, visibleMenu, type MenuItem } from './config/menu'

const SECTION_NOTES: Record<string, string> = {
  'admin-persona': '查看身份层版本、适应层漂移与提案历史；写操作需额外审批权限。',
  'admin-persona-identity': '身份层是低频、需留痕的长期人格；保存会创建新版本，历史版本不可修改。',
  'admin-persona-adaptation': '适应层是短期状态；有界更新，单维步长与窗口漂移由 persona-state 服务端强制。',
  'admin-memory': '按节点类型、过滤条件、深度与上限做结构化只读图查询；不支持原始 Cypher。',
  'admin-audit': '按回合查看门控分数、候选数量、实际使用的记忆 ID 与降级原因。',
  'admin-consolidation': '查看巩固积压、运行中作业、死信与重放记录。',
  'admin-proposals': '审阅身份变更提案；批准后生成新的身份版本并留下审计记录。',
  'admin-llm': '配置 OpenAI 兼容端点、模型与 API Key；保存后下一回合立即生效。',
}

const IMPLEMENTED_PANELS = new Set(['admin-llm', 'admin-persona-identity', 'admin-persona-adaptation', 'admin-proposals'])

export default function App({ permissions = DEV_PERMISSIONS }: { permissions?: readonly string[] }) {
  const menu = useMemo(() => visibleMenu(MENU, permissions), [permissions])
  const canEditPersona = permissions.includes('admin-web.persona.edit')
  const [selected, setSelected] = useState<MenuItem | null>(menu[0] ?? null)
  const [upstreams, setUpstreams] = useState<UpstreamStatus[]>([])
  const [probeError, setProbeError] = useState<string | null>(null)
  const [probing, setProbing] = useState(false)

  const probe = useCallback(async (signal?: AbortSignal) => {
    setProbing(true)
    setProbeError(null)
    try {
      setUpstreams(await fetchUpstreams(signal))
    } catch (error) {
      if ((error as Error).name !== 'AbortError') {
        setProbeError('无法读取上游健康状态：请通过 npm start 运行管理端静态服务。')
      }
    } finally {
      setProbing(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void probe(controller.signal)
    return () => controller.abort()
  }, [probe])

  useEffect(() => {
    const available = new Set(menu.flatMap((item) => [item.id, ...(item.children?.map((child) => child.id) ?? [])]))
    if (selected && !available.has(selected.id)) {
      setSelected(menu[0] ?? null)
    }
  }, [menu, selected])

  const healthy = upstreams.filter((item) => item.healthy).length

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand__mark" aria-hidden="true">
            H
          </span>
          <div>
            <strong>HLA-MEM</strong>
            <span className="brand__sub">管理端</span>
          </div>
        </div>

        <nav aria-label="管理导航">
          {menu.length === 0 ? <p className="empty">当前身份没有可用菜单。</p> : null}
          {menu.map((item) => (
            <div key={item.id} className="nav-group">
              <button
                type="button"
                className={`nav-item ${selected?.id === item.id ? 'nav-item--active' : ''}`}
                onClick={() => setSelected(item)}
              >
                <span>{item.name}</span>
                <em>{item.order}</em>
              </button>
              {item.children?.map((child) => (
                <button
                  key={child.id}
                  type="button"
                  className={`nav-item nav-item--child ${selected?.id === child.id ? 'nav-item--active' : ''}`}
                  onClick={() => setSelected(child)}
                >
                  {child.name}
                </button>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar__footer">
          <span className={`dot ${healthy > 0 ? 'dot--ok' : 'dot--idle'}`} aria-hidden="true" />
          {healthy}/{upstreams.length || 4} 上游可用
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>HLA-MEM 管理端</h1>
            <p className="topbar__sub">模块健康、记忆图、人格与巩固运维</p>
          </div>
          <span className="badge">阶段 0 · 只读骨架</span>
        </header>

        <section className="cards" aria-label="模块健康">
          {upstreams.map((item) => (
            <article key={item.module} className="card">
              <div className="card__head">
                <h2>{item.module}</h2>
                <span className={`pill ${item.healthy ? 'pill--ok' : 'pill--bad'}`}>
                  {item.healthy ? '正常' : '不可达'}
                </span>
              </div>
              <p className="card__meta">{item.url}</p>
              <p className="card__meta">
                {item.latencyMs === null ? '延迟未知' : `${item.latencyMs} ms`}
                {item.detail ? ` · ${item.detail}` : ''}
              </p>
            </article>
          ))}
          {upstreams.length === 0 && !probeError ? <p className="empty">正在探测上游…</p> : null}
          {probeError ? <p className="empty empty--warn">{probeError}</p> : null}
        </section>

        <div className="toolbar">
          <button type="button" className="button" onClick={() => void probe()} disabled={probing}>
            {probing ? '探测中…' : '刷新健康'}
          </button>
          <span className="toolbar__hint">仅探测 /internal/health；不读取业务数据。</span>
        </div>

        <section className="panel" aria-label="当前模块">
          {selected ? (
            <>
              <div className="panel__head">
                <h2>{selected.name}</h2>
                <span className="badge badge--soft">
                  {IMPLEMENTED_PANELS.has(selected.id) ? '已接入 persona-state' : '阶段 0 仅声明'}
                </span>
              </div>
              <p className="panel__note">{SECTION_NOTES[selected.id] ?? '该模块尚未实现业务能力。'}</p>
              {selected.id === 'admin-llm' ? (
                <LLMSettings />
              ) : selected.id === 'admin-persona-identity' ? (
                <IdentityEditor canEdit={canEditPersona} />
              ) : selected.id === 'admin-persona-adaptation' ? (
                <AdaptationEditor canEdit={canEditPersona} />
              ) : selected.id === 'admin-proposals' ? (
                <ProposalReview />
              ) : (
                <>
                  <dl className="facts">
                    <div>
                      <dt>路由</dt>
                      <dd>{selected.route}</dd>
                    </div>
                    <div>
                      <dt>所需能力</dt>
                      <dd>{selected.requiredCapability ?? '无（前端菜单）'}</dd>
                    </div>
                    <div>
                      <dt>菜单权限</dt>
                      <dd>{selected.permission}</dd>
                    </div>
                  </dl>
                  <p className="panel__boundary">
                    前端菜单权限只控制可见性；最终授权由目标模块在服务端校验。当前没有真实数据可展示。
                  </p>
                </>
              )}
            </>
          ) : (
            <p className="empty">没有可展示的模块。</p>
          )}
        </section>
      </main>
    </div>
  )
}
