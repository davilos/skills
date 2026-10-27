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
    acs: q('.acs > li'),
    slices: q('.slice'),
    changes: q('.row-btn'),
    impactCards: q('.imp'),
    paths: q('.paths > .path'),
    symptoms: q('.sym'),
  }
  for (const k of Object.keys(expected)) {
    if (expected[k] !== got[k]) fail.push(`${k}: expected ${expected[k]}, the page shows ${got[k]}`)
  }
  // Every capture the plan shows (`![name](captures/x.png)`) is an image on the page, loaded from beside it.
  const imgs = new Set([...d.querySelectorAll('img')].map((i) => i.getAttribute('src')))
  const noImg = (P.images || []).filter((src) => !imgs.has(src))
  if (noImg.length) fail.push('captures the plan shows that are not images on the page: ' + noImg.join(', '))
  if ((P.images || []).length) expected.captures = P.images.length
  // Every mermaid block of the plan is a drawing with its source (the drawing itself needs the CDN; see checkDiagrams).
  const blocksOf = (s) => (s.blocks || []).concat(s.criteria ? [s.criteria.intro, ...s.criteria.slices.flatMap((x) => [x.desc, x.extra])].flat() : [])
  const mermaidSrc = P.sections.flatMap(blocksOf).filter((b) => b.type === 'code' && b.lang === 'mermaid').map((b) => b.text)
  const figSrc = [...d.querySelectorAll('figure.mmd pre.mermaid')].map((x) => x.textContent)
  const noFig = mermaidSrc.filter((t) => !figSrc.includes(t))
  if (noFig.length) fail.push(`${noFig.length} mermaid block(s) of the plan are not a drawing on the page`)
  if (q('pre.mermaid') !== q('figure.mmd pre.mermaid')) fail.push('a mermaid source on the page is outside a drawing')
  if (mermaidSrc.length) expected.diagrams = `${mermaidSrc.length} in the plan, ${q('figure.mmd')} on the page`
  // Landing in plain language: one explanation per door, and the "Confirm" button lives there (not in the plan table).
  if (G.landing_visual) {
    const nDoors = G.landing_visual.doors.length
    if (q('.door-v') !== nDoors)
      fail.push(`Landing visual: expected ${nDoors} explained doors, the page shows ${q('.door-v')}`)
    if (q('#landing .view[data-v="text"] [id^="door-"]'))
      fail.push('Landing: the plan table repeats the door-N id of the Visual tab')
    expected.doorsExplained = nDoors
  }
  // Table rows reviewed one by one: each has its number (a button that copies "Section #N") and exactly one anchor.
  const rowList = Object.entries(P.rows || {}).flatMap(([sid, rs]) => rs.map((x) => ({ sid, ...x })))
  const plainRows = rowList.filter((x) => x.key.startsWith('row:'))
  const refs = new Set([...d.querySelectorAll('.rn')].map((b) => b.getAttribute('data-ref')))
  const names = Object.fromEntries(P.sections.map((s) => [s.id, s.name]))
  for (const x of plainRows) {
    if (!refs.has(`${names[x.sid]} #${x.n}`)) fail.push(`row ${x.key}: no "#${x.n}" number on the page`)
    if (d.querySelectorAll(`[id="row-${x.sid}-${x.n}"]`).length !== 1) fail.push(`row ${x.key}: expected one #row-${x.sid}-${x.n} anchor`)
  }
  if (refs.size !== plainRows.length) fail.push(`row numbers: expected ${plainRows.length}, the page shows ${refs.size}`)
  if (rowList.length) expected.reviewRows = rowList.length
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
  // An empty section (no content, or only `None - <why>`) has nothing to validate: no button, a "nothing to validate" badge.
  const toReview = data.PLAN.sections.filter((s) => !s.empty)
  // Exercise one section with content (starting as pending on the page, whatever review-page.json says) and another for "changed since".
  const [key, other] = toReview.map((s) => s.id)
  if (key) store[key] = { state: 'pending', fp: null, at: '2026-01-01T00:00:00Z' }
  // A section with table rows, also starting as pending (a row with no state of its own takes its section's).
  const rsid = Object.keys(data.PLAN.rows || {}).find((sid) => data.PLAN.rows[sid].some((x) => x.key.startsWith('row:')))
  if (rsid) store[rsid] = { state: 'pending', fp: null, at: '2026-01-01T00:00:00Z' }
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
  const want = toReview.length + (P2.sections.find((s) => s.id === 'criteria')?.criteria.slices.length || 0)
  if (slots !== want) out.push(`review: ${slots} review badges, expected ${want} (sections with content + slices)`)
  // Every table row and door has its Confirm / Reject (Impact rows: in the Plan text table).
  const rowKeys = Object.values(P2.rows || {}).flatMap((rs) => rs.map((x) => x.key))
  const rowSlots = new Set([...d2.querySelectorAll('[data-rk-row]')].map((e) => e.getAttribute('data-rk-row')))
  const noSlot = rowKeys.filter((k) => !rowSlots.has(k))
  if (noSlot.length) out.push(`review: rows without Confirm / Reject: ${noSlot.slice(0, 5).join(', ')}`)
  if (rowSlots.size !== rowKeys.length) out.push(`review: ${rowSlots.size} row reviews, expected ${rowKeys.length}`)
  for (const s of P2.sections.filter((x) => x.empty)) {
    if (d2.querySelector(`[data-rk="${s.id}"]`)) out.push(`review: the empty section ${s.id} has a validate button`)
    if (!d2.querySelector(`section#${s.id} .badge.na`)) out.push(`review: the empty section ${s.id} does not say "nothing to validate"`)
  }
  const badgeOf = (k) => d2.querySelector(`[data-rk="${k}"] .badge`).textContent
  if (!other) {
    out.push('review: the plan needs two sections with content to exercise the buttons')
    return { out, errs }
  }
  const btn = d2.querySelector(`.rv-btn[data-rk-btn="${key}"]`)
  if (!btn || btn.hidden) {
    out.push('review: the validate button does not show for an editor')
    return { out, errs }
  }
  btn.click()
  await tick()
  const w = writes[writes.length - 1]
  if (!w || w.path !== `review/${key}` || w.data.state !== 'validated')
    out.push(`review: clicking Validate did not write review/${key} as validated`)
  else if (w.data.fp !== P2.fingerprints[key])
    out.push('review: the stored fingerprint is not the one of the current text')
  if (badgeOf(key) !== 'validated')
    out.push(`review: after validating, the badge says "${badgeOf(key)}"`)
  d2.querySelector(`.rv-btn[data-rk-btn="${key}"]`).click()
  await tick()
  if (writes[writes.length - 1].data.state !== 'pending') out.push('review: Undo did not write pending')
  if (badgeOf(key) !== 'not reviewed')
    out.push(`review: after undoing, the badge says "${badgeOf(key)}"`)
  // A validation made on an old text: fingerprint differs from the current one.
  store[other] = { state: 'validated', fp: 'old-fingerprint', at: '2026-01-01T00:00:00Z' }
  listener(snap())
  await tick()
  if (!/changed since/.test(badgeOf(other)))
    out.push(`review: a validation of an old text shows as "${badgeOf(other)}"`)
  // Rows: Confirm, Reject, Reject again (undo), then the section's Validate confirms them all and Undo clears them.
  if (rsid) {
    const keys = P2.rows[rsid].map((x) => x.key)
    const rk = keys.find((k) => k.startsWith('row:'))
    const rowBadge = (k) => d2.querySelector(`[data-rk-row="${k}"] .badge`).textContent
    const press = async (k, act) => {
      d2.querySelector(`.rv-mini.${act}[data-rk-row-btn="${k}"]`).click()
      await tick()
    }
    const last = () => writes[writes.length - 1] || {}
    await press(rk, 'yes')
    if (last().path !== `review/${rk}` || last().data.state !== 'validated') out.push(`review: Confirm did not write review/${rk} as validated`)
    else if (last().data.fp !== P2.fingerprints[rk]) out.push(`review: the fingerprint stored for ${rk} is not the one of the current row`)
    if (rowBadge(rk) !== 'confirmed') out.push(`review: after Confirm, the row says "${rowBadge(rk)}"`)
    await press(rk, 'no')
    if (last().data.state !== 'rejected') out.push('review: Reject did not write rejected')
    if (rowBadge(rk) !== 'rejected') out.push(`review: after Reject, the row says "${rowBadge(rk)}"`)
    if (!/rejected/.test(badgeOf(rsid))) out.push(`review: a section with a rejected row says "${badgeOf(rsid)}"`)
    if (!d2.querySelector('#rail-rej a')) out.push('review: the rejected row is not listed in the panel')
    const tr = d2.querySelector(`[data-rk-row="${rk}"]`).closest('tr')
    if (tr && tr.getAttribute('data-rs') !== 'rej') out.push('review: the rejected row is not marked in the table')
    await press(rk, 'no')
    if (last().data.state !== 'pending' || rowBadge(rk) !== 'not confirmed') out.push('review: pressing Reject again did not undo it')
    await press(rk, 'no')
    const before = writes.length
    d2.querySelector(`.rv-btn[data-rk-btn="${rsid}"]`).click()
    await tick()
    const wrote = writes.slice(before)
    const missed = [rsid, ...keys].filter((k) => !wrote.some((w) => w.path === `review/${k}` && w.data.state === 'validated'))
    if (missed.length) out.push(`review: the section's Validate did not confirm ${missed.slice(0, 5).join(', ')}`)
    if (badgeOf(rsid) !== 'validated') out.push(`review: after validating the section, it says "${badgeOf(rsid)}"`)
    const notOk = keys.filter((k) => rowBadge(k) !== 'confirmed')
    if (notOk.length) out.push(`review: after validating the section, rows not confirmed: ${notOk.slice(0, 5).join(', ')}`)
    d2.querySelector(`.rv-btn[data-rk-btn="${rsid}"]`).click()
    await tick()
    if (badgeOf(rsid) !== 'not reviewed' || keys.some((k) => rowBadge(k) !== 'not confirmed'))
      out.push(`review: the section's Undo left "${badgeOf(rsid)}" and rows ${keys.map(rowBadge).join(' / ')}`)
  }
  // A door is a Landing row: Confirm writes door:N as validated.
  const door = rowKeys.find((k) => k.startsWith('door:'))
  if (door) {
    const b = d2.querySelector(`.rv-mini.yes[data-rk-row-btn="${door}"]`)
    const was = b.getAttribute('aria-pressed') === 'true'
    b.click()
    await tick()
    const w = writes[writes.length - 1] || {}
    if (w.path !== `review/${door}` || w.data.state !== (was ? 'pending' : 'validated')) out.push(`review: Confirm on ${door} did not write it`)
  }
  return { out, errs, writes: writes.length }
}

// Drawings: runs again with a fake Mermaid. Every figure gets its SVG and closes its source; a diagram
// that does not parse keeps the source open with a note; a theme change draws again with the dark theme.
// The fake SVG carries what a real one does: a numbered message with its arrow, a module the path names
// and a door, so the clicks, the link with The path and the full-screen zoom are exercised too.
async function checkDiagrams() {
  const out = []
  if (!data || !d.querySelector('figure.mmd')) return { out }
  const G = data.PAGE_DATA || {}
  const xml = (t) => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;')
  const paths = (G.flow_visual && G.flow_visual.paths) || []
  const node = paths.flatMap((p) => p.nodes).find((x) => x.change != null && !x.tbd) || paths.flatMap((p) => p.nodes).find((x) => !x.tbd)
  const hasDoor = !!d.getElementById('door-1')
  const fakeSvg = (id) =>
    `<svg id="${id}" viewBox="0 0 400 200" style="max-width: 400px;"><g><text class="messageText">1. enters</text><line class="messageLine0"></line>` +
    (node ? `<g><rect class="actor actor-top"></rect><text class="actor actor-box">${xml(node.n)}</text></g>` +
      `<g><rect class="actor actor-bottom"></rect><text class="actor actor-box">${xml(node.n)}</text></g>` : '') +
    (hasDoor ? '<text>unique, door 1</text>' : '') + '</g></svg>'
  const inits = [],
    renders = []
  const errs3 = []
  const dom3 = new jsdom.JSDOM('<!doctype html><html><body>' + html + '</body></html>', {
    runScripts: 'dangerously',
    virtualConsole: new jsdom.VirtualConsole().on('jsdomError', (e) => errs3.push(e.message)),
    beforeParse(win) {
      win.mermaid = {
        initialize: (c) => inits.push(c),
        render: async (id, text) => {
          renders.push(id)
          if (renders.length === 1) throw new Error('Parse error on line 1')
          return { svg: fakeSvg(id) }
        },
      }
    },
  })
  const d3 = dom3.window.document
  const tick = () => new Promise((r) => setTimeout(r, 20))
  await tick()
  const figs = [...d3.querySelectorAll('figure.mmd')]
  if (renders.length !== figs.length) out.push(`drawings: Mermaid drew ${renders.length} of ${figs.length} diagrams`)
  const [bad, ...good] = figs
  if (!bad.classList.contains('failed') || !bad.querySelector('.mmd-src').open || bad.querySelector('.mmd-note').hidden)
    out.push('drawings: a diagram that does not parse does not keep its source open with a note')
  const notDrawn = good.filter((f) => !f.querySelector('.mmd-draw svg') || f.querySelector('.mmd-draw').hidden || f.querySelector('.mmd-src').open)
  if (notDrawn.length) out.push(`drawings: ${notDrawn.length} diagram(s) without their SVG, or with the source still open`)
  if (inits[0] && inits[0].securityLevel !== 'strict') out.push('drawings: Mermaid does not run with securityLevel strict')
  // Interaction, on the first drawn figure.
  const P3 = dom3.window.__PLAN_PAGE__.PLAN
  const pathSec = P3.sections.find((s) => s.id === 'shape' || s.id === 'flow')
  const hop1 = pathSec && (pathSec.blocks || []).filter((b) => b.type === 'ol').flatMap((b) => b.items).find((it) => it.n === 1)
  const fig = good[0]
  const click = (el) => el.dispatchEvent(new dom3.window.MouseEvent('click', { bubbles: true }))
  const detail = () => fig.querySelector('.mmd-detail')
  if (fig && hop1) {
    const hot = fig.querySelector('[data-mmd-key="hop:1"]')
    if (!hot) out.push('drawings: the numbered step "1." is not clickable')
    else {
      click(hot)
      const want = hop1.text.replace(/\*\*|`/g, '').replace(/\s+/g, ' ').trim().slice(0, 40)
      if (detail().hidden || !detail().textContent.replace(/\s+/g, ' ').includes(want)) out.push('drawings: clicking step 1 does not show hop 1 of the plan')
      if (!fig.querySelector('line.mmd-sel')) out.push("drawings: clicking step 1 does not light its arrow")
      click(hot)
      if (!detail().hidden) out.push('drawings: clicking step 1 again does not close its detail')
    }
    // The cards of The path live in the drawing's panel now: step 1 shows each path of hop 1, and a
    // changed node there opens its Where / Why / Proof. The list itself hides once the path is drawn.
    const hop1Paths = paths.filter((p) => p.hop === 1).length
    click(hot)
    if (detail().querySelectorAll('.mmd-path').length !== hop1Paths)
      out.push(`drawings: step 1 shows ${detail().querySelectorAll('.mmd-path').length} card(s) of The path, expected ${hop1Paths}`)
    const pick = detail().querySelector('[data-node-pick]')
    if (pick) {
      click(pick)
      if (!detail().querySelector('.mmd-path dl')) out.push('drawings: a changed node in the panel does not open its Where / Why / Proof')
    }
    click(fig.querySelector('[data-mmd-key="hop:1"]'))
    const list = d3.querySelector('.part-path')
    if (list && fig.classList.contains('path-drawing') && !list.hidden) out.push('drawings: The path list still shows although the path is drawn')
  }
  if (fig && node) {
    const nm = String(node.n).replace(/[`"*]/g, '').trim()
    const hot = fig.querySelector(`[data-mmd-key="name:${nm}"]`)
    if (!hot) out.push(`drawings: the module ${nm} is not clickable`)
    else {
      click(hot)
      if (detail().hidden || !detail().textContent.includes(nm)) out.push(`drawings: clicking ${nm} does not show it`)
      if (node.change != null && !detail().querySelector('dl')) out.push(`drawings: clicking ${nm} does not show its Where / Why / Proof`)
      if ((node.o || node.note) && !hot.classList.contains('mmd-chg')) out.push(`drawings: ${nm} changes in the plan but is not green in the drawing`)
      // Mermaid repeats a participant at the bottom: one block is clickable, the copy only lights with it.
      if (fig.querySelectorAll(`[data-mmd-key="name:${nm}"]`).length !== 1) out.push(`drawings: ${nm} has ${fig.querySelectorAll(`[data-mmd-key="name:${nm}"]`).length} clickable blocks, expected 1`)
      const twin = fig.querySelector(`[data-mmd-twin="name:${nm}"]`)
      if (!twin) out.push(`drawings: the bottom copy of ${nm} is not kept as a copy`)
      else if (twin.hasAttribute('tabindex') || !twin.classList.contains('mmd-sel')) out.push(`drawings: the bottom copy of ${nm} is clickable, or does not light with the selection`)
      click(hot)
    }
  }
  if (fig && hasDoor && !fig.querySelector('[data-mmd-key="door:1"]')) out.push('drawings: "door 1" in a drawing is not clickable')
  // Every clickable block says so: a tooltip of what the click opens (the CSS underlines it); the copy does not.
  const noTip = good.flatMap((f) => [...f.querySelectorAll('[data-mmd-key]')]).filter((x) => !x.querySelector(':scope > title'))
  if (noTip.length) out.push(`drawings: ${noTip.length} clickable block(s) without a tooltip of what the click opens`)
  if (good.some((f) => [...f.querySelectorAll('[data-mmd-twin]')].some((x) => x.querySelector(':scope > title'))))
    out.push('drawings: the bottom copy of a participant carries a click tooltip')
  // Full screen: the SVG moves into the dialog, the zoom buttons move it, Close brings it back.
  const exp = fig && fig.querySelector('.mmd-expand')
  if (exp) {
    click(exp)
    const dlg = d3.querySelector('dialog.mmd-zoom')
    if (!dlg || !dlg.hasAttribute('open') || !dlg.querySelector('.mmd-stage svg')) out.push('drawings: Expand does not open the diagram full screen')
    else {
      if (!d3.documentElement.classList.contains('mmd-locked')) out.push('drawings: the page behind the full-screen drawing still scrolls')
      const before = dlg.querySelector('.mmd-stage').style.transform
      click(dlg.querySelector('[data-z="in"]'))
      if (dlg.querySelector('.mmd-stage').style.transform === before) out.push('drawings: zoom in does not change the full-screen view')
      const inZoom = dlg.querySelector('.mmd-stage [data-mmd-key]')
      if (inZoom) {
        click(inZoom)
        const det = dlg.querySelector('.mmd-detail')
        if (!det || det.hidden) out.push('drawings: clicking a step or a name full screen does not show its detail there')
      }
      click(dlg.querySelector('[data-z="close"]'))
      if (dlg.hasAttribute('open') || !fig.querySelector('.mmd-draw svg') || !fig.querySelector('.mmd-detail')) out.push('drawings: Close does not bring the diagram back to the page')
      if (d3.documentElement.classList.contains('mmd-locked')) out.push('drawings: the page stays locked after Close')
    }
  }
  if (fig && !fig.querySelector('.mmd-copy[data-copy]')) out.push('drawings: no Copy source button')
  d3.documentElement.setAttribute('data-theme', 'dark')
  await tick()
  if (!inits.some((c) => c.theme === 'dark')) out.push('drawings: switching to the dark theme did not draw again in dark')
  for (const e of errs3) out.push('runtime error (with fake Mermaid): ' + e)
  return { out, drawn: good.length }
}

;(async () => {
  if (data) {
    const dg = await checkDiagrams()
    for (const m of dg.out) fail.push(m)
    if (dg.drawn != null) expected.drawingFlow = dg.out.length ? 'failed' : `ok (fake Mermaid: ${dg.drawn} drawn, 1 parse error shown with its source; steps, names, The path link and zoom exercised)`
    const r = await checkReviewFlow()
    for (const m of r.out) fail.push(m)
    for (const e of r.errs) fail.push('runtime error (with fake db): ' + e)
    expected.reviewFlow = r.out.length ? 'failed' : `ok (${r.writes} simulated writes)`
  }
  for (const e of errors) fail.push('runtime error: ' + e)
  console.log(JSON.stringify({ ok: fail.length === 0, expected, fail }, null, 2))
  process.exit(fail.length ? 1 : 0)
})()
