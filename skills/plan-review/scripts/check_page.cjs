#!/usr/bin/env node
/*
 * Loads the generated page in a simulated DOM and checks that it renders the whole plan.
 * Usage: node check_page.cjs <page.html> [jsdom path]
 *   jsdom: the explicit path if given (relative to the current folder); otherwise whatever
 *   `require("jsdom")` resolves from the current folder. If none is found, install it somewhere
 *   disposable: npm install --prefix <tmp dir> jsdom, and pass <tmp dir>/node_modules/jsdom.
 * Exits 1 on a runtime error or if a section, criterion or change is missing; 2 on bad usage.
 */
const fs = require('fs')
const path = require('path')
const [htmlPath, jsdomPath] = process.argv.slice(2)
if (!htmlPath) {
  console.error('usage: node check_page.cjs <page.html> [jsdom path]')
  process.exit(2)
}
function loadJsdom() {
  // A relative path is resolved from the current folder; without that, require would treat it as a package name.
  if (jsdomPath) return require(path.resolve(process.cwd(), jsdomPath))
  try {
    return require(require.resolve('jsdom', { paths: [process.cwd()] }))
  } catch (_e) {
    try {
      return require('jsdom')
    } catch (_e2) {
      console.error(
        'check_page: jsdom not found from ' +
          process.cwd() +
          '.\n' +
          'Install it somewhere disposable and pass its path:\n' +
          '  npm install --prefix <tmp dir> jsdom\n' +
          '  node check_page.cjs <page.html> <tmp dir>/node_modules/jsdom',
      )
      process.exit(2)
    }
  }
}
const jsdom = loadJsdom()
const html = fs.readFileSync(htmlPath, 'utf8')
const errors = []
const vc = new jsdom.VirtualConsole().on('jsdomError', (e) => errors.push(e.message))
const dom = new jsdom.JSDOM('<!doctype html><html><body>' + html + '</body></html>', {
  runScripts: 'dangerously',
  virtualConsole: vc,
})
const w = dom.window,
  d = w.document
const data = w.__PLAN_PAGE__
const fail = []
if (!data) fail.push('the page did not expose window.__PLAN_PAGE__ (did the script break earlier?)')
const q = (s) => d.querySelectorAll(s).length
let expected = {}
if (data) {
  const P = data.PLAN,
    G = data.PAGE_DATA || {}
  const crit = P.sections.find((s) => s.id === 'criteria')
  const slices = crit ? crit.criteria.slices : []
  expected = {
    sections: P.sections.length,
    acs: slices.reduce((n, s) => n + s.acs.length, 0),
    slices: slices.length,
    changes: (G.changes || []).length,
    impactCards: G.impact_visual ? G.impact_visual.cards.length : 0,
    paths: G.flow_visual ? G.flow_visual.paths.length : 0,
    symptoms: G.problem_visual ? (G.problem_visual.symptoms || []).length : 0,
  }
  const got = {
    sections: q('section.sec'),
    acs: q('.acs li'),
    slices: q('.slice'),
    changes: q('.row-btn'),
    impactCards: q('.imp'),
    paths: q('.path'),
    symptoms: q('.sym'),
  }
  for (const k of Object.keys(expected)) {
    if (expected[k] !== got[k]) fail.push(`${k}: expected ${expected[k]}, the page shows ${got[k]}`)
  }
  // Landing in plain language: one explanation per door, and the "Confirm" button lives there (not in the plan table).
  if (G.landing_visual) {
    const nDoors = G.landing_visual.doors.length
    if (q('.door-v') !== nDoors)
      fail.push(`Landing visual: expected ${nDoors} explained doors, the page shows ${q('.door-v')}`)
    if (q('#landing .view[data-v="text"] [id^="door-"]'))
      fail.push('Landing: the plan table repeats the door-N id of the Visual tab')
    expected.doorsExplained = nDoors
  }
  // Every name with `tbd` (Flow node, change, Impact card) shows as "not defined", and only those.
  const tbdWant =
    (G.flow_visual ? G.flow_visual.paths.reduce((c, p) => c + p.nodes.filter((x) => x.tbd).length, 0) : 0) +
    (G.changes || []).filter((x) => x.tbd).length +
    (G.impact_visual ? G.impact_visual.cards.filter((c) => c.tbd && c.after).length : 0)
  if (q('.tbd') !== tbdWant) fail.push(`"not defined": expected ${tbdWant}, the page shows ${q('.tbd')}`)
  if (tbdWant) expected.undefinedNames = tbdWant
  const pay = d.querySelector('.pay-btn')
  if (pay) {
    pay.click()
    if (!d.querySelector('.sym.hit')) fail.push('clicking a who-pays filter did not highlight any symptom')
    pay.click()
  }
  const clicks = [
    ['.sym-btn', '.sym .detail dl'],
    ['.row-btn', '.renames .detail dl'],
    ['.imp-btn', '.imp-detail dl'],
    ['.node-btn', '.path .detail dl'],
  ]
  for (const [btn, out] of clicks) {
    const b = d.querySelector(btn)
    if (!b) continue
    b.click()
    if (!d.querySelector(out)) fail.push(`clicking ${btn} did not open Where / Why / Proof`)
  }
  // With every panel open, every internal link (#ac-N, #door-N, #slice-S1...) needs a target.
  // Each click re-renders the list: the button is looked up again by its data-* before every click.
  const openAll = (sel, attr) => {
    const keys = [...d.querySelectorAll(sel)].map((b) => b.getAttribute(attr))
    for (const k of keys) {
      const b = d.querySelector(sel + '[' + attr + '="' + k + '"]')
      if (b && b.getAttribute('aria-expanded') !== 'true') b.click()
    }
    return keys.length
  }
  const broken = new Set()
  let xrefs = 0
  const scan = () =>
    d.querySelectorAll('a[href^="#"]').forEach((a) => {
      const id = a.getAttribute('href').slice(1)
      if (id && !d.getElementById(id)) broken.add(a.getAttribute('href'))
    })
  for (const [sel, attr] of [
    ['.sym-btn', 'data-i'],
    ['.row-btn', 'data-i'],
    ['.imp-btn', 'data-i'],
  ])
    openAll(sel, attr)
  scan()
  xrefs += q('a.xref')
  // In the Flow only one step is open at a time: open them one by one and check each time. With a step
  // open, the other occurrences of the same node (same `n` in the data) must light up.
  const fvPaths = G.flow_visual ? G.flow_visual.paths : []
  for (const k of [...d.querySelectorAll('.node-btn')].map((b) => b.getAttribute('data-key'))) {
    const b = d.querySelector('.node-btn[data-key="' + k + '"]')
    if (b && b.getAttribute('aria-expanded') !== 'true') b.click()
    scan()
    const [pi, ni] = k.split('-').map(Number)
    const n = fvPaths[pi].nodes[ni].n
    const want = fvPaths.reduce((c, p) => c + p.nodes.filter((x) => x.n === n && (x.o || x.note)).length, 0) - 1
    if (q('.node.same') !== want)
      fail.push(`opening step ${k} (${n}) lit ${q('.node.same')} repeat(s), expected ${want}`)
    if (!d.querySelector('.paths.picking')) fail.push(`opening step ${k} did not fade the other steps`)
  }
  if (broken.size) fail.push('internal links without a target: ' + [...broken].join(', '))
  if (!xrefs) fail.push('no Proof link (a.xref) on the page')
  expected.xrefsAllOpen = xrefs
  // Visible content only: the body's textContent includes the <script>, which has a legitimate $1 in md().
  const visible = (d.querySelector('.page') || d.body).textContent
  // Coverage, end 2: every piece of plan.md appears in the page text (including the "Plan text"
  // views, which are in the DOM even when hidden).
  // Each piece is searched INSIDE its section and in plan ORDER. A section with a
  // Visual | Plan text switch is checked in the "Plan text" view (that is the text that binds).
  const flat = (el) => (el ? el.textContent.replace(/\s+/g, ' ') : '')
  const containerText = (sec) => {
    if (sec === 'header') return flat(d.querySelector('header.head'))
    const s = d.getElementById(sec)
    if (!s) return null
    return flat(s.querySelector(':scope > .view[data-v="text"]') || s)
  }
  const cov = P.coverage || []
  if (!cov.length) fail.push('the page has no coverage list (generated by an old build?)')
  const cursor = {},
    texts = {}
  let shown = 0
  const problems = []
  for (const [line, sec, kind, piece] of cov) {
    if (!(sec in texts)) texts[sec] = containerText(sec)
    const t = texts[sec]
    if (t == null) {
      problems.push(`plan.md:${line}: section ${sec} does not exist on the page`)
      continue
    }
    if (kind === 'th') {
      // section title and table header: presence in the section is enough
      if (t.includes(piece) || (sec !== 'header' && flat(d.getElementById(sec)).includes(piece))) shown++
      else problems.push(`plan.md:${line} does not appear in section ${sec}: ${JSON.stringify(piece.slice(0, 80))}`)
      continue
    }
    const at = t.indexOf(piece, cursor[sec] || 0)
    if (at === -1) {
      problems.push(
        t.includes(piece)
          ? `plan.md:${line} appears out of plan order in section ${sec}: ${JSON.stringify(piece.slice(0, 80))}`
          : `plan.md:${line} does not appear in section ${sec}: ${JSON.stringify(piece.slice(0, 80))}`,
      )
      continue
    }
    cursor[sec] = at + piece.length
    shown++
  }
  for (const p of problems.slice(0, 10)) fail.push('coverage: ' + p)
  if (problems.length > 10) fail.push(`coverage: ${problems.length - 10} more problems`)
  expected.planCoverage = `${shown}/${cov.length} (in the right section and in order)`
  if (!P.hash) fail.push('the page does not carry the plan.md hash')
  if (/\$\d/.test(visible)) fail.push('a literal $N is left in the text (replace with the wrong group)')
}
// Validation from the page: runs again with a fake window.claude (db + user) and exercises the flow.
async function checkReviewFlow() {
  const store = {},
    writes = []
  let listener = null
  const snap = () => ({ docs: Object.keys(store).map((id) => ({ id, exists: true, data: () => store[id] })) })
  const fakeDb = {
    collection: (_path) => ({
      onSnapshot: (next) => {
        listener = next
        setTimeout(() => next(snap()), 0)
        return () => {}
      },
    }),
    doc: (path) => ({
      set: (data) => {
        writes.push({ path, data })
        store[path.split('/')[1]] = data
        if (listener) listener(snap())
        return Promise.resolve()
      },
    }),
  }
  const fakeUser = { canEdit: async () => true, id: async () => 'u_test' }
  const errs = []
  const vc2 = new jsdom.VirtualConsole().on('jsdomError', (e) => errs.push(e.message))
  const dom2 = new jsdom.JSDOM('<!doctype html><html><body>' + html + '</body></html>', {
    runScripts: 'dangerously',
    virtualConsole: vc2,
    beforeParse(win) {
      win.claude = { use: async (n) => (n === 'db' ? fakeDb : n === 'user' ? fakeUser : null) }
    },
  })
  const d2 = dom2.window.document,
    P2 = dom2.window.__PLAN_PAGE__.PLAN
  const tick = () => new Promise((r) => setTimeout(r, 20))
  await tick()
  await tick()
  const out = []
  const slots = d2.querySelectorAll('[data-rk]').length
  const want =
    P2.sections.length +
    (P2.sections.find((s) => s.id === 'criteria')?.criteria.slices.length || 0) +
    Object.keys(P2.fingerprints || {}).filter((k) => k.startsWith('door:')).length
  if (slots !== want) out.push(`review: ${slots} review badges, expected ${want} (sections + slices + doors)`)
  const btn = d2.querySelector('.rv-btn[data-rk-btn="relations"]')
  if (!btn || btn.hidden) {
    out.push('review: the validate button does not show for an editor')
    return { out, errs }
  }
  const badgeOf = (k) => d2.querySelector(`[data-rk="${k}"] .badge`).textContent
  btn.click()
  await tick()
  const w = writes[writes.length - 1]
  if (!w || w.path !== 'review/relations' || w.data.state !== 'validated')
    out.push('review: clicking Validate did not write review/relations as validated')
  else if (w.data.fp !== P2.fingerprints.relations)
    out.push('review: the stored fingerprint is not the one of the current text')
  if (badgeOf('relations') !== 'validated')
    out.push(`review: after validating, the badge says "${badgeOf('relations')}"`)
  d2.querySelector('.rv-btn[data-rk-btn="relations"]').click()
  await tick()
  if (writes[writes.length - 1].data.state !== 'pending') out.push('review: Undo did not write pending')
  if (badgeOf('relations') !== 'not reviewed')
    out.push(`review: after undoing, the badge says "${badgeOf('relations')}"`)
  // A validation made on an old text: fingerprint differs from the current one.
  store.surface = { state: 'validated', fp: 'old-fingerprint', at: '2026-01-01T00:00:00Z' }
  listener(snap())
  await tick()
  if (!/changed since/.test(badgeOf('surface')))
    out.push(`review: a validation of an old text shows as "${badgeOf('surface')}"`)
  return { out, errs, writes: writes.length }
}

;(async () => {
  if (data) {
    const r = await checkReviewFlow()
    for (const m of r.out) fail.push(m)
    for (const e of r.errs) fail.push('runtime error (with fake db): ' + e)
    expected.reviewFlow = r.out.length ? 'failed' : `ok (${r.writes} simulated writes)`
  }
  for (const e of errors) fail.push('runtime error: ' + e)
  console.log(JSON.stringify({ ok: fail.length === 0, expected, fail }, null, 2))
  process.exit(fail.length ? 1 : 0)
})()
