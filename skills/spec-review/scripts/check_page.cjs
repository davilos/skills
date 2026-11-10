#!/usr/bin/env node
/* Checks a built review page in jsdom: picks the checker of the engine that built it.
 *
 * Usage: node check_page.cjs <page.html> [jsdom path]
 *
 * A tlc-spec-lean page (window.__PLAN_PAGE__) goes to lean_check.cjs; a generic or tlc-spec-driven
 * page (window.__DOC_PAGE__) to doc_check.cjs. Both print {"ok": true | false, "expected", "fail"}.
 */
const fs = require('fs')
const path = require('path')

const file = process.argv[2]
if (!file) {
  console.error('usage: node check_page.cjs <page.html> [jsdom path]')
  process.exit(2)
}
const html = fs.readFileSync(file, 'utf8')
const engine = html.includes('window.__PLAN_PAGE__') ? 'lean_check.cjs' : 'doc_check.cjs'
require(path.join(__dirname, engine))
