#!/usr/bin/env node
/*
 * Loads the generated page in a simulated DOM and checks that it renders the whole document.
 * Usage: node check_page.cjs <page.html> [jsdom path]
 *   jsdom: the explicit path if given (relative to the current folder); otherwise whatever
 *   `require("jsdom")` resolves from the current folder. If none is found, install it somewhere
 *   disposable: npm install --prefix <tmp dir> jsdom, and pass <tmp dir>/node_modules/jsdom.
 * Exits 1 on a runtime error or if a section, row, diagram or piece of the document is missing; 2 on bad usage.
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
        'check_page: jsdom not found from ' + process.cwd() + '.\n' +
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
const load = (opts = {}) => {
  const errs = []
  const dom = new jsdom.JSDOM('<!doctype html><html><body>' + html + '</body></html>', {
    runScripts: 'dangerously',
    virtualConsole: new jsdom.VirtualConsole().on('jsdomError', (e) => errs.push(e.message)),
    ...opts,
  })
  return { dom, w: dom.window, d: dom.window.document, errs }
}
const tick = () => new Promise((r) => setTimeout(r, 20))
const first = load()
const d = first.d
const data = first.w.__DOC_PAGE__
const fail = []
if (!data) fail.push('the page did not expose window.__DOC_PAGE__ (did the script break earlier?)')
const q = (s, doc = d) => doc.querySelectorAll(s).length
const expected = {}
const allBlocks = (list) => (list || []).flatMap((b) => [b, ...(b.type === 'quote' ? allBlocks(b.blocks) : [])])

if (data) {
  const D = data.DOC
  const want = { sections: D.sections.length }
  const got = { sections: q('section.sec') }
  for (const k of Object.keys(want)) if (want[k] !== got[k]) fail.push(`${k}: expected ${want[k]}, the page shows ${got[k]}`)
  expected.sections = D.sections.length
  // Every image the document shows is an image on the page, loaded from beside it.
  const imgs = new Set([...d.querySelectorAll('img')].map((i) => i.getAttribute('src')))
  const noImg = (D.images || []).filter((src) => !imgs.has(src))
  if (noImg.length) fail.push('images the document shows that are not images on the page: ' + noImg.join(', '))
  if ((D.images || []).length) expected.images = D.images.length
  // Every mermaid block is a drawing with its source.
  const mermaidSrc = D.sections.flatMap((s) => allBlocks(s.blocks)).filter((b) => b.type === 'code' && b.lang === 'mermaid').map((b) => b.text)
  const figSrc = [...d.querySelectorAll('figure.mmd pre.mermaid')].map((x) => x.textContent)
  const noFig = mermaidSrc.filter((t) => !figSrc.includes(t))
  if (noFig.length) fail.push(`${noFig.length} mermaid block(s) of the document are not a drawing on the page`)
  if (q('pre.mermaid') !== q('figure.mmd pre.mermaid')) fail.push('a mermaid source on the page is outside a drawing')
  if (mermaidSrc.length) expected.diagrams = `${mermaidSrc.length} in the document, ${q('figure.mmd')} on the page`
  // Table rows reviewed one by one: each has its number (a button that copies "Section #N") and exactly one anchor.
  const rowList = Object.entries(D.rows || {}).flatMap(([sid, rs]) => rs.map((x) => ({ sid, ...x })))
  const refs = new Set([...d.querySelectorAll('.rn')].map((b) => b.getAttribute('data-ref')))
  const names = Object.fromEntries(D.sections.map((s) => [s.id, s.name]))
  for (const x of rowList) {
    if (!refs.has(`${names[x.sid]} #${x.n}`)) fail.push(`row ${x.key}: no "#${x.n}" number on the page`)
    if (d.querySelectorAll(`[id="row-${x.sid}-${x.n}"]`).length !== 1) fail.push(`row ${x.key}: expected one #row-${x.sid}-${x.n} anchor`)
  }
  if (refs.size !== rowList.length) fail.push(`row numbers: expected ${rowList.length}, the page shows ${refs.size}`)
  if (rowList.length) expected.reviewRows = rowList.length
  // Every internal link has a target on the page.
  const broken = [...d.querySelectorAll('a[href^="#"]')].map((a) => a.getAttribute('href')).filter((h) => h.length > 1 && !d.getElementById(h.slice(1)))
  if (broken.length) fail.push('internal links without a target: ' + [...new Set(broken)].join(', '))
  // Unique ids: two sections or subheadings with the same anchor break the jumps.
  const ids = [...d.querySelectorAll('[id]')].map((e) => e.id)
  const dup = ids.filter((x, i) => ids.indexOf(x) !== i)
  if (dup.length) fail.push('repeated ids on the page: ' + [...new Set(dup)].slice(0, 5).join(', '))
  // Nothing the document says is turned into markup it did not ask for: no script, no handler attributes.
  if ([...d.querySelectorAll('main *')].some((e) => [...e.attributes].some((a) => /^on/i.test(a.name)))) fail.push('an element in the document carries an on* handler')
  if (q('main script')) fail.push('a <script> ended up inside the document body')
  // Coverage, end 2: every piece of the document appears in the page text, inside its section and in order.
  const visible = (d.querySelector('.page') || d.body).textContent
  const flat = (el) => (el ? el.textContent.replace(/\s+/g, ' ') : '')
  const containerText = (sec) => (sec === 'header' ? flat(d.querySelector('header.head')) : (d.getElementById('s-' + sec) ? flat(d.getElementById('s-' + sec)) : null))
  const cov = D.coverage || []
  if (!cov.length) fail.push('the page has no coverage list (generated by an old build?)')
  const cursor = {}, texts = {}, problems = []
  let shown = 0
  for (const [line, sec, kind, piece] of cov) {
    if (!(sec in texts)) texts[sec] = containerText(sec)
    const t = texts[sec]
    if (t == null) {
      problems.push(`line ${line}: section ${sec} does not exist on the page`)
      continue
    }
    if (kind === 'th') {
      if (t.includes(piece)) shown++
      else problems.push(`line ${line} does not appear in section ${sec}: ${JSON.stringify(piece.slice(0, 80))}`)
      continue
    }
    const at = t.indexOf(piece, cursor[sec] || 0)
    if (at === -1) {
      problems.push(t.includes(piece)
        ? `line ${line} appears out of document order in section ${sec}: ${JSON.stringify(piece.slice(0, 80))}`
        : `line ${line} does not appear in section ${sec}: ${JSON.stringify(piece.slice(0, 80))}`)
      continue
    }
    cursor[sec] = at + piece.length
    shown++
  }
  for (const p of problems.slice(0, 10)) fail.push('coverage: ' + p)
  if (problems.length > 10) fail.push(`coverage: ${problems.length - 10} more problems`)
  expected.docCoverage = `${shown}/${cov.length} (in the right section and in order)`
  if (!D.hash) fail.push('the page does not carry the document hash')
  // A "$1" the document does not have is a replace() with the wrong group.
  let rest = visible.replace(/\s+/g, ' ')
  for (const c of cov) rest = rest.split(c[3]).join('')
  if (/\$\d/.test(rest)) fail.push('a literal $N is left in the text (replace with the wrong group)')
  for (const e of first.errs) fail.push('runtime error: ' + e)
}

// Validation from the page: runs again with a fake window.claude (db + user) and exercises the flow.
async function checkReviewFlow() {
  const store = {}, writes = []
  const toReview = data.DOC.sections.filter((s) => !s.empty)
  const [key, other] = toReview.map((s) => s.id)
  if (!key) return { out: [], errs: [], writes: 0 }
  if (key) store[key] = { state: 'pending', fp: null, at: '2026-01-01T00:00:00Z' }
  const rsid = Object.keys(data.DOC.rows || {})[0]
  if (rsid) store[rsid] = { state: 'pending', fp: null, at: '2026-01-01T00:00:00Z' }
  let listener = null
  const snap = () => ({ docs: Object.keys(store).map((id) => ({ id, exists: true, data: () => store[id] })) })
  const fakeDb = {
    collection: () => ({ onSnapshot: (next) => { listener = next; setTimeout(() => next(snap()), 0); return () => {} } }),
    doc: (p) => ({ set: (v) => { writes.push({ path: p, data: v }); store[p.split('/')[1]] = v; if (listener) listener(snap()); return Promise.resolve() } }),
  }
  const fakeUser = { canEdit: async () => true, id: async () => 'u_test' }
  const { d: d2, w: w2, errs } = load({ beforeParse(win) { win.claude = { use: async (n) => (n === 'db' ? fakeDb : n === 'user' ? fakeUser : null) } } })
  await tick(); await tick()
  const D2 = w2.__DOC_PAGE__.DOC
  const out = []
  const slots = q('[data-rk]', d2)
  if (slots !== toReview.length) out.push(`review: ${slots} review badges, expected ${toReview.length} (sections with content)`)
  const rowKeys = Object.values(D2.rows || {}).flatMap((rs) => rs.map((x) => x.key))
  const rowSlots = new Set([...d2.querySelectorAll('[data-rk-row]')].map((e) => e.getAttribute('data-rk-row')))
  if (rowSlots.size !== rowKeys.length || rowKeys.some((k) => !rowSlots.has(k))) out.push(`review: ${rowSlots.size} row reviews, expected ${rowKeys.length}`)
  for (const s of D2.sections.filter((x) => x.empty)) {
    if (d2.querySelector(`[data-rk="${s.id}"]`)) out.push(`review: the empty section ${s.id} has a validate button`)
    if (!d2.querySelector(`section#s-${s.id} .badge.na`)) out.push(`review: the empty section ${s.id} does not say it has nothing to validate`)
  }
  const badgeOf = (k) => d2.querySelector(`[data-rk="${k}"] .badge`).className.split(' ')[1]
  const btn = d2.querySelector(`.rv-btn[data-rk-btn="${key}"]`)
  if (!btn || btn.hidden) {
    out.push('review: the validate button does not show for an editor')
    return { out, errs }
  }
  const before = writes.length
  btn.click(); await tick()
  // Validate writes the section and then each of its rows: find the section's own write.
  const wr = writes.slice(before).find((x) => x.path === `review/${key}`)
  if (!wr || wr.path !== `review/${key}` || wr.data.state !== 'validated') out.push(`review: clicking Validate did not write review/${key} as validated`)
  else if (wr.data.fp !== D2.fingerprints[key]) out.push('review: the stored fingerprint is not the one of the current text')
  if (badgeOf(key) !== 'ok') out.push(`review: after validating, the badge is "${badgeOf(key)}"`)
  d2.querySelector(`.rv-btn[data-rk-btn="${key}"]`).click(); await tick()
  if (writes[writes.length - 1].data.state !== 'pending') out.push('review: Undo did not write pending')
  if (badgeOf(key) !== 'pend') out.push(`review: after undoing, the badge is "${badgeOf(key)}"`)
  // A validation made on an old text: the fingerprint differs from the current one.
  const old = other || key
  store[old] = { state: 'validated', fp: 'old-fingerprint', at: '2026-01-01T00:00:00Z' }
  listener(snap()); await tick()
  if (badgeOf(old) !== 'stale') out.push(`review: a validation of an old text shows as "${badgeOf(old)}"`)
  if (!other) { store[old] = { state: 'pending', fp: null }; listener(snap()); await tick() }
  // Rows: Confirm, Reject, Reject again (undo), then the section's Validate confirms them all and Undo clears them.
  if (rsid) {
    // Start the rows from pending (the section too): a row already marked in the review state would make Confirm undo it.
    store[rsid] = { state: 'pending', fp: null, at: '2026-01-01T00:00:00Z' }
    for (const r of data.DOC.rows[rsid]) store[r.key] = { state: 'pending', fp: null, at: '2026-01-01T00:00:00Z' }
    listener(snap()); await tick()
    const keys = D2.rows[rsid].map((x) => x.key), rk = keys[0]
    const rowState = (k) => d2.querySelector(`[data-rk-row="${k}"]`).closest('tr').getAttribute('data-rs')
    const press = async (k, act) => { d2.querySelector(`.rv-mini.${act}[data-rk-row-btn="${k}"]`).click(); await tick() }
    const last = () => writes[writes.length - 1] || {}
    await press(rk, 'yes')
    if (last().path !== `review/${rk}` || last().data.state !== 'validated') out.push(`review: Confirm did not write review/${rk} as validated`)
    else if (last().data.fp !== D2.fingerprints[rk]) out.push(`review: the fingerprint stored for ${rk} is not the one of the current row`)
    if (rowState(rk) !== 'ok') out.push(`review: after Confirm, the row is "${rowState(rk)}"`)
    await press(rk, 'no')
    if (last().data.state !== 'rejected') out.push('review: Reject did not write rejected')
    if (rowState(rk) !== 'rej') out.push(`review: after Reject, the row is "${rowState(rk)}"`)
    if (badgeOf(rsid) !== 'rej') out.push(`review: a section with a rejected row is "${badgeOf(rsid)}"`)
    if (!d2.querySelector('#rail-rej a')) out.push('review: the rejected row is not listed in the panel')
    await press(rk, 'no')
    if (last().data.state !== 'pending' || rowState(rk) !== 'pend') out.push('review: pressing Reject again did not undo it')
    await press(rk, 'no')
    const before = writes.length
    d2.querySelector(`.rv-btn[data-rk-btn="${rsid}"]`).click(); await tick()
    const wrote = writes.slice(before)
    const missed = [rsid, ...keys].filter((k) => !wrote.some((x) => x.path === `review/${k}` && x.data.state === 'validated'))
    if (missed.length) out.push(`review: the section's Validate did not confirm ${missed.slice(0, 5).join(', ')}`)
    if (badgeOf(rsid) !== 'ok') out.push(`review: after validating the section, it is "${badgeOf(rsid)}"`)
    if (keys.some((k) => rowState(k) !== 'ok')) out.push('review: after validating the section, some rows are not confirmed')
    d2.querySelector(`.rv-btn[data-rk-btn="${rsid}"]`).click(); await tick()
    if (badgeOf(rsid) !== 'pend' || keys.some((k) => rowState(k) !== 'pend')) out.push("review: the section's Undo did not take it and its rows back to pending")
  }
  return { out, errs, writes: writes.length }
}

// Drawings: runs again with a fake Mermaid. Every figure gets its SVG and closes its source; a diagram
// that does not parse keeps the source open with a note; a theme change draws again with the dark theme.
// The fake SVG carries two numbered messages and one `autonumber` message with their arrows, so the steps,
// step by step and zoom are exercised.
async function checkDiagrams() {
  const out = []
  if (!data || !d.querySelector('figure.mmd')) return { out }
  const fakeSvg = (id) =>
    `<svg id="${id}" viewBox="0 0 400 200" style="max-width: 400px;"><g><text class="messageText">1. enters</text><line class="messageLine0"></line>` +
    '<text class="messageText">2. goes on</text><line class="messageLine0"></line><text class="messageText">no number here</text>' +
    // `autonumber`: the number is its own text, after the message's text and arrow.
    '<text class="messageText">third hop</text><line class="messageLine0"></line><line></line><text class="sequenceNumber">3</text></g></svg>'
  const inits = [], renders = []
  const { d: d3, w: w3, errs } = load({
    beforeParse(win) {
      win.mermaid = {
        initialize: (c) => inits.push(c),
        render: async (id) => {
          renders.push(id)
          if (renders.length === 1) throw new Error('Parse error on line 1')
          return { svg: fakeSvg(id) }
        },
      }
    },
  })
  await tick()
  const figs = [...d3.querySelectorAll('figure.mmd')]
  if (renders.length !== figs.length) out.push(`drawings: Mermaid drew ${renders.length} of ${figs.length} diagrams`)
  const [bad, ...good] = figs
  if (!bad.classList.contains('failed') || !bad.querySelector('.mmd-src').open || bad.querySelector('.mmd-note').hidden)
    out.push('drawings: a diagram that does not parse does not keep its source open with a note')
  const notDrawn = good.filter((f) => !f.querySelector('.mmd-draw svg') || f.querySelector('.mmd-draw').hidden || f.querySelector('.mmd-src').open)
  if (notDrawn.length) out.push(`drawings: ${notDrawn.length} diagram(s) without their SVG, or with the source still open`)
  if (inits[0] && inits[0].securityLevel !== 'strict') out.push('drawings: Mermaid does not run with securityLevel strict')
  if (inits[0] && !(inits[0].flowchart && inits[0].flowchart.useMaxWidth === false)) out.push('drawings: a flowchart is shrunk to the column (useMaxWidth)')
  const fig = good[0]
  const click = (el) => el && el.dispatchEvent(new w3.MouseEvent('click', { bubbles: true }))
  if (fig) {
    const detail = () => fig.querySelector('.mmd-detail')
    const hot = fig.querySelector('[data-mmd-key="step:1"]')
    if (!hot) out.push('drawings: the numbered step "1." is not clickable')
    else {
      if (!hot.querySelector(':scope > title')) out.push('drawings: a step carries no tooltip of what the click does')
      click(hot)
      if (detail().hidden || !/enters/.test(detail().textContent)) out.push('drawings: clicking step 1 does not show it under the drawing')
      if (!fig.querySelector('line.mmd-sel')) out.push('drawings: clicking step 1 does not light its arrow')
      click(fig.querySelector('[data-mmd-key="step:1"]'))
      if (!detail().hidden) out.push('drawings: clicking step 1 again does not close it')
    }
    if (q('[data-mmd-key]', fig) !== 3) out.push(`drawings: ${q('[data-mmd-key]', fig)} clickable labels, expected 3 (a label without a number stays plain)`)
    const auto = fig.querySelector('[data-mmd-key="step:3"]')
    if (!auto || !/third hop/.test(auto.textContent)) out.push('drawings: an autonumber message is not step 3')
    else {
      click(auto)
      if (!/third hop/.test(fig.querySelector('.mmd-detail').textContent) || !fig.querySelector('text.sequenceNumber.mmd-sel') || q('line.mmd-sel', fig) !== 1)
        out.push('drawings: clicking an autonumber step does not show it, or does not light its number and arrow')
      click(auto)
    }
    const steps = fig.querySelector('.mmd-bar .mmd-steps')
    if (!steps || steps.hidden) out.push('drawings: a drawing with steps 1 and 2 has no step by step')
    else {
      const sel = () => (fig.querySelector('.mmd-step[aria-pressed="true"]') || {}).textContent
      click(steps.querySelector('[data-step="next"]'))
      if (sel() !== '1' || detail().hidden) out.push('drawings: Next does not open step 1')
      if (!steps.querySelector('[data-step="prev"]').disabled) out.push('drawings: Previous is not disabled on the first step')
      click(steps.querySelector('[data-step="next"]'))
      if (sel() !== '2' || !fig.querySelector('[data-mmd-key="step:2"].mmd-sel')) out.push('drawings: Next does not move to step 2')
      if (!fig.querySelector('.mmd-draw svg.mmd-stepping')) out.push('drawings: the other steps do not fade while a step is on')
      click(steps.querySelector('[data-step="prev"]'))
      if (sel() !== '1') out.push('drawings: Previous does not go back to step 1')
      click(steps.querySelector('[data-step="3"]'))
      if (sel() !== '3' || !steps.querySelector('[data-step="next"]').disabled) out.push('drawings: the last step button does not open it, or Next is not disabled there')
      click(fig.querySelector('.mmd-x'))
      if (sel() || fig.querySelector('.mmd-draw svg.mmd-stepping')) out.push('drawings: closing the detail leaves a step on')
    }
    // Full screen: the expand icon sits in the drawing's box; the SVG moves into the dialog, zoom moves it, Close brings it back.
    const exp = fig.querySelector('.mmd-frame > .mmd-expand')
    if (!exp) out.push('drawings: the Expand icon is not inside the drawing box')
    else {
      click(exp)
      const dlg = d3.querySelector('dialog.mmd-zoom')
      if (!dlg || !dlg.hasAttribute('open') || !dlg.querySelector('.mmd-stage svg')) out.push('drawings: Expand does not open the diagram full screen')
      else {
        if (!d3.documentElement.classList.contains('mmd-locked')) out.push('drawings: the page behind the full-screen drawing still scrolls')
        const before = dlg.querySelector('.mmd-stage').style.transform
        click(dlg.querySelector('[data-z="in"]'))
        if (dlg.querySelector('.mmd-stage').style.transform === before) out.push('drawings: zoom in does not change the full-screen view')
        const zsteps = dlg.querySelector('.mmd-steps')
        if (!zsteps || zsteps.hidden) out.push('drawings: full screen has no step by step')
        else {
          click(zsteps.querySelector('[data-step="next"]'))
          if ((zsteps.querySelector('.mmd-step[aria-pressed="true"]') || {}).textContent !== '1' || dlg.querySelector('.mmd-detail').hidden)
            out.push('drawings: Next full screen does not open step 1 there')
          dlg.dispatchEvent(new w3.KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }))
          if ((zsteps.querySelector('.mmd-step[aria-pressed="true"]') || {}).textContent !== '2') out.push('drawings: the right arrow full screen does not move to step 2')
          click(dlg.querySelector('.mmd-x'))
        }
        click(dlg.querySelector('[data-z="close"]'))
        if (dlg.hasAttribute('open') || !fig.querySelector('.mmd-draw svg') || !fig.querySelector('.mmd-detail')) out.push('drawings: Close does not bring the diagram back to the page')
        if (d3.documentElement.classList.contains('mmd-locked')) out.push('drawings: the page stays locked after Close')
      }
    }
    if (!fig.querySelector('.mmd-copy[data-copy]')) out.push('drawings: no Copy source button')
  }
  d3.documentElement.setAttribute('data-theme', 'dark')
  await tick()
  if (!inits.some((c) => c.theme === 'dark')) out.push('drawings: switching to the dark theme did not draw again in dark')
  for (const e of errs) out.push('runtime error (with fake Mermaid): ' + e)
  return { out, drawn: good.length }
}

;(async () => {
  if (data) {
    const dg = await checkDiagrams()
    for (const m of dg.out) fail.push(m)
    if (dg.drawn != null) expected.drawingFlow = dg.out.length ? 'failed' : `ok (fake Mermaid: ${dg.drawn} drawn, 1 parse error shown with its source; steps, step by step and zoom exercised)`
    const r = await checkReviewFlow()
    for (const m of r.out) fail.push(m)
    for (const e of r.errs) fail.push('runtime error (with fake db): ' + e)
    expected.reviewFlow = r.out.length ? 'failed' : `ok (${r.writes} simulated writes)`
  }
  console.log(JSON.stringify({ ok: fail.length === 0, expected, fail }, null, 2))
  process.exit(fail.length ? 1 : 0)
})()
