#!/usr/bin/env node
/**
 * Single web server for the HLA-MEM demo.
 *
 *   /conversation/  -> modules/conversation-web/web/dist
 *   /admin/         -> modules/admin-web/web/dist
 *   /api/*          -> reasoning-orchestrator (SSE preserved)
 *   /internal/orchestrator/llm/config -> orchestrator LLM config
 *
 * One origin means no CORS and no second frontend port.
 */
import { createServer } from 'node:http'
import { readFile, stat } from 'node:fs/promises'
import { extname, join, normalize, resolve, sep } from 'node:path'
import { Readable } from 'node:stream'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(fileURLToPath(new URL('.', import.meta.url)), '..')
const VERSION = '0.1.0'
const PORT = Number(process.env.PORT ?? process.env.HLA_WEB_PORT ?? 4173)
const ORCHESTRATOR_URL = process.env.ORCHESTRATOR_URL ?? 'http://127.0.0.1:8081'
const PERSONA_URL = process.env.PERSONA_URL ?? 'http://127.0.0.1:8083'

const APPS = {
  '/conversation/': {
    module: 'conversation-web',
    root: join(ROOT, 'modules/conversation-web/web/dist'),
    ready: false,
  },
  '/admin/': {
    module: 'admin-web',
    root: join(ROOT, 'modules/admin-web/web/dist'),
    ready: false,
  },
}

const DEFAULT_UPSTREAMS = [
  { module: 'reasoning-orchestrator', url: 'http://127.0.0.1:8081' },
  { module: 'memory-graph', url: 'http://127.0.0.1:8082' },
  { module: 'persona-state', url: 'http://127.0.0.1:8083' },
  { module: 'async-consolidator', url: 'http://127.0.0.1:8084' },
]

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.webp': 'image/webp',
  '.woff2': 'font/woff2',
  '.map': 'application/json; charset=utf-8',
}

let requestCount = 0

function loadUpstreams() {
  const raw = process.env.UPSTREAMS
  if (!raw) return DEFAULT_UPSTREAMS
  try {
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return DEFAULT_UPSTREAMS
    const safe = parsed
      .filter((item) => item && typeof item.module === 'string' && typeof item.url === 'string')
      .map((item) => {
        const url = new URL(item.url)
        if (url.protocol !== 'http:' && url.protocol !== 'https:') {
          throw new Error('unsupported upstream protocol')
        }
        return { module: item.module, url: url.origin }
      })
    return safe.length > 0 ? safe : DEFAULT_UPSTREAMS
  } catch {
    return DEFAULT_UPSTREAMS
  }
}

const UPSTREAMS = loadUpstreams()

async function fileExists(path) {
  try {
    return (await stat(path)).isFile()
  } catch {
    return false
  }
}

function sendJson(res, status, body) {
  const payload = JSON.stringify(body)
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(payload),
    'cache-control': 'no-store',
    'x-content-type-options': 'nosniff',
    'referrer-policy': 'same-origin',
  })
  res.end(payload)
}

function sendText(res, status, body, contentType = 'text/plain; charset=utf-8') {
  res.writeHead(status, {
    'content-type': contentType,
    'content-length': Buffer.byteLength(body),
    'cache-control': 'no-store',
    'x-content-type-options': 'nosniff',
  })
  res.end(body)
}

function redirect(res, location) {
  res.writeHead(308, { location })
  res.end()
}

function appHealth(app) {
  return {
    status: 'ok',
    module: app.module,
    version: VERSION,
    time: new Date().toISOString(),
  }
}

function appReady(app) {
  return {
    status: app.ready ? 'ready' : 'not_ready',
    module: app.module,
    checks: [
      {
        name: 'build',
        ready: app.ready,
        detail: app.ready ? null : 'dist/index.html is missing; run make web-build',
      },
    ],
    time: new Date().toISOString(),
  }
}

function metricsFor(modules) {
  const ready = modules.every((app) => app.ready)
  const lines = [
    '# TYPE frontend_ready gauge',
    ...modules.map((app) => `frontend_ready{module="${app.module}"} ${app.ready ? 1 : 0}`),
    '# TYPE frontend_ready_all gauge',
    `frontend_ready_all{module="web"} ${ready ? 1 : 0}`,
    '# TYPE frontend_requests_total counter',
    `frontend_requests_total{module="web"} ${requestCount}`,
    '# TYPE frontend_build_info gauge',
    ...modules.map((app) => `frontend_build_info{module="${app.module}",version="${VERSION}"} 1`),
    '',
  ]
  return lines.join('\n')
}

async function probeUpstream(upstream) {
  const started = performance.now()
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 1500)
  try {
    const response = await fetch(`${upstream.url}/internal/health`, {
      signal: controller.signal,
      headers: { accept: 'application/json' },
    })
    const body = await response.json().catch(() => ({}))
    return {
      module: upstream.module,
      url: upstream.url,
      healthy: response.ok && body.status === 'ok',
      latencyMs: Math.round(performance.now() - started),
      detail: response.ok ? null : `HTTP ${response.status}`,
    }
  } catch (error) {
    return {
      module: upstream.module,
      url: upstream.url,
      healthy: false,
      latencyMs: null,
      detail: error?.name === 'AbortError' ? 'timeout' : String(error?.message ?? 'unreachable').slice(0, 120),
    }
  } finally {
    clearTimeout(timer)
  }
}

async function readBody(req) {
  const chunks = []
  for await (const chunk of req) chunks.push(chunk)
  return chunks.length > 0 ? Buffer.concat(chunks) : undefined
}

async function proxyApi(req, res) {
  // persona-state admin calls are same-origin too, so /api/persona-state/* is
  // routed to its own backend while everything else goes to the orchestrator.
  if (req.url?.startsWith('/api/persona-state/')) {
    await proxyJson(req, res, PERSONA_URL, 10000, 'persona-state')
    return
  }
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 125000)
  try {
    const upstream = await fetch(`${ORCHESTRATOR_URL}${req.url}`, {
      method: req.method,
      headers: {
        accept: req.headers.accept ?? 'text/event-stream',
        'content-type': req.headers['content-type'] ?? 'application/json',
        'idempotency-key': req.headers['idempotency-key'] ?? '',
        'x-request-id': req.headers['x-request-id'] ?? '',
      },
      body: await readBody(req),
      signal: controller.signal,
    })
    res.writeHead(upstream.status, {
      'content-type': upstream.headers.get('content-type') ?? 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      'x-accel-buffering': 'no',
    })
    if (upstream.body) {
      Readable.fromWeb(upstream.body).pipe(res)
    } else {
      res.end()
    }
  } catch (error) {
    sendJson(res, 502, {
      code: 'WEB_UPSTREAM_UNAVAILABLE',
      message: error?.name === 'AbortError' ? 'orchestrator timeout' : 'orchestrator unreachable',
    })
  } finally {
    clearTimeout(timer)
  }
}

async function proxyJson(req, res, baseUrl, timeoutMs, label) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const upstream = await fetch(`${baseUrl}${req.url}`, {
      method: req.method,
      headers: {
        accept: 'application/json',
        'content-type': req.headers['content-type'] ?? 'application/json',
        'idempotency-key': req.headers['idempotency-key'] ?? '',
        'x-request-id': req.headers['x-request-id'] ?? '',
      },
      body: req.method === 'GET' || req.method === 'HEAD' ? undefined : await readBody(req),
      signal: controller.signal,
    })
    const text = await upstream.text()
    res.writeHead(upstream.status, {
      'content-type': upstream.headers.get('content-type') ?? 'application/json; charset=utf-8',
      'content-length': Buffer.byteLength(text),
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff',
    })
    res.end(text)
  } catch (error) {
    sendJson(res, 502, {
      code: 'WEB_UPSTREAM_UNAVAILABLE',
      message: `${label} ${error?.name === 'AbortError' ? 'timeout' : 'unreachable'}`,
    })
  } finally {
    clearTimeout(timer)
  }
}

async function proxyLlmConfig(req, res) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 5000)
  try {
    const upstream = await fetch(`${ORCHESTRATOR_URL}/internal/v1/llm/config`, {
      method: req.method,
      headers: {
        accept: 'application/json',
        'content-type': req.headers['content-type'] ?? 'application/json',
      },
      body: req.method === 'PUT' ? await readBody(req) : undefined,
      signal: controller.signal,
    })
    const text = await upstream.text()
    res.writeHead(upstream.status, {
      'content-type': upstream.headers.get('content-type') ?? 'application/json; charset=utf-8',
      'content-length': Buffer.byteLength(text),
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff',
    })
    res.end(text)
  } catch {
    sendJson(res, 502, {
      code: 'WEB_UPSTREAM_UNAVAILABLE',
      message: 'orchestrator unreachable',
    })
  } finally {
    clearTimeout(timer)
  }
}

function matchApp(path) {
  for (const [base, app] of Object.entries(APPS)) {
    if (path === base.slice(0, -1)) return { app, redirect: base }
    if (path.startsWith(base)) return { app }
  }
  return null
}

function safePath(app, base, path) {
  try {
    const relative = path.slice(base.length)
    const target = normalize(join(app.root, decodeURIComponent(relative)))
    if (target !== app.root && !target.startsWith(app.root + sep)) return null
    return target
  } catch {
    return null
  }
}

async function serveStatic(req, res, app, base, path) {
  if (path === base) {
    // Serve index.html below.
  }
  let target = safePath(app, base, path)
  if (target === null) {
    sendJson(res, 404, { code: 'WEB_ROUTE_NOT_FOUND', message: 'not found' })
    return
  }
  if (!(await fileExists(target))) {
    if (!extname(target)) target = join(app.root, 'index.html')
    if (!(await fileExists(target))) {
      sendJson(res, 404, { code: 'WEB_ROUTE_NOT_FOUND', message: 'not found' })
      return
    }
  }
  try {
    const body = await readFile(target)
    res.writeHead(200, {
      'content-type': MIME[extname(target)] ?? 'application/octet-stream',
      'content-length': body.byteLength,
      'cache-control': target.endsWith('index.html') ? 'no-store' : 'public, max-age=31536000, immutable',
      'x-content-type-options': 'nosniff',
      'referrer-policy': 'same-origin',
      'content-security-policy':
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'",
    })
    res.end(req.method === 'HEAD' ? undefined : body)
  } catch {
    sendJson(res, 500, { code: 'WEB_INTERNAL_ERROR', message: 'unable to read asset' })
  }
}

const server = createServer(async (req, res) => {
  requestCount += 1
  const url = new URL(req.url ?? '/', `http://${req.headers.host ?? 'localhost'}`)
  const path = url.pathname

  // Combined operational endpoints.
  if (req.method === 'GET' && path === '/internal/health') {
    sendJson(res, 200, {
      status: 'ok',
      module: 'web',
      modules: Object.values(APPS).map((app) => app.module),
      version: VERSION,
      time: new Date().toISOString(),
    })
    return
  }
  if (req.method === 'GET' && path === '/internal/ready') {
    const allReady = Object.values(APPS).every((app) => app.ready)
    sendJson(res, allReady ? 200 : 503, {
      status: allReady ? 'ready' : 'not_ready',
      module: 'web',
      checks: Object.values(APPS).map((app) => ({
        name: `${app.module}-build`,
        ready: app.ready,
        detail: app.ready ? null : 'dist/index.html is missing; run make web-build',
      })),
      time: new Date().toISOString(),
    })
    return
  }
  if (req.method === 'GET' && path === '/internal/metrics') {
    const upstreams = await Promise.all(UPSTREAMS.map(probeUpstream))
    const healthy = upstreams.filter((item) => item.healthy).length
    const body = `${metricsFor(Object.values(APPS))}# TYPE frontend_upstreams_healthy gauge
frontend_upstreams_healthy{module="web"} ${healthy}
`
    sendText(res, 200, body, 'text/plain; version=0.0.4; charset=utf-8')
    return
  }
  if (req.method === 'GET' && path === '/internal/upstreams') {
    sendJson(res, 200, { upstreams: await Promise.all(UPSTREAMS.map(probeUpstream)) })
    return
  }
  if (path === '/internal/orchestrator/llm/config' && (req.method === 'GET' || req.method === 'PUT')) {
    await proxyLlmConfig(req, res)
    return
  }
  if (path.startsWith('/api/')) {
    await proxyApi(req, res)
    return
  }

  // Per-app operational endpoints: /conversation/internal/health etc.
  for (const [base, app] of Object.entries(APPS)) {
    const prefix = `${base}internal/`
    if (path === `${prefix}health` && req.method === 'GET') {
      sendJson(res, 200, appHealth(app))
      return
    }
    if (path === `${prefix}ready` && req.method === 'GET') {
      sendJson(res, app.ready ? 200 : 503, appReady(app))
      return
    }
    if (path === `${prefix}metrics` && req.method === 'GET') {
      sendText(res, 200, metricsFor([app]), 'text/plain; version=0.0.4; charset=utf-8')
      return
    }
  }

  const match = matchApp(path)
  if (!match) {
    if (path === '/') {
      redirect(res, '/conversation/')
      return
    }
    sendJson(res, 404, { code: 'WEB_ROUTE_NOT_FOUND', message: 'not found' })
    return
  }
  if (match.redirect) {
    redirect(res, match.redirect)
    return
  }
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    sendJson(res, 405, { code: 'WEB_ROUTE_METHOD_NOT_ALLOWED', message: 'method not allowed' })
    return
  }
  const base = Object.keys(APPS).find((candidate) => path.startsWith(candidate))
  if (!base) {
    sendJson(res, 404, { code: 'WEB_ROUTE_NOT_FOUND', message: 'not found' })
    return
  }
  await serveStatic(req, res, match.app, base, path)
})

for (const app of Object.values(APPS)) {
  app.ready = await fileExists(join(app.root, 'index.html'))
}
const allReady = Object.values(APPS).every((app) => app.ready)
server.listen(PORT, '127.0.0.1', () => {
  console.log(
    JSON.stringify({
      level: 'INFO',
      module: 'web',
      message: 'web listening',
      url: `http://127.0.0.1:${PORT}/`,
      conversation: `http://127.0.0.1:${PORT}/conversation/`,
      admin: `http://127.0.0.1:${PORT}/admin/`,
      ready: allReady,
    }),
  )
})

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    server.close(() => process.exit(0))
  })
}
