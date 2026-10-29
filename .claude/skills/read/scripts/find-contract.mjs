#!/usr/bin/env node
// find-contract.mjs: list the contracts a page declares, before you send it a body.
//
//   node find-contract.mjs <url | saved-page.html> [--base <url>] [--open]
//   node find-contract.mjs --self-test
//
// It lists:
//   - <link> elements and HTTP Link header entries with rel service-desc (a description for
//     machines, such as OpenAPI or JSON Schema), describedby, or service-doc (docs for people);
//   - every rel="alternate" whose type, or file name when there is no type, is JSON or YAML;
//   - each <form>: where it sends, how, and every named field with its limits.
// It also says when the response is itself a contract (JSON Schema, OpenAPI, AsyncAPI).
// --base <url>  resolves relative links in a saved page.
// --open        prints each listed contract as the server sends it. A contract on a local or private
//               address is skipped unless the page itself is on that host.
// Exit code: 0 = something is declared, 2 = nothing is declared, 1 = an error.
//
// Network: one GET to the URL, and with --open one GET per listed contract. No body, no cookies, no keys.
// Files: reads only files inside the current working folder. Writes nothing.
// Plain Node.js 18 or newer, no dependencies.

import assert from 'node:assert/strict';
import { readFile, realpath } from 'node:fs/promises';
import { isAbsolute, relative, resolve, sep } from 'node:path';

const USAGE = `usage:
  node find-contract.mjs <url | saved-page.html> [--base <url>] [--open]
  node find-contract.mjs --self-test`;

const CONTRACT_RELS = ['service-desc', 'describedby', 'service-doc'];
const DATA_TYPE = /(^|[\/+.-])(json|yaml|yml)($|[;+\s])/i;
const DATA_FILE = /\.(json|ya?ml)([?#]|$)/i;
const FIELD_TAGS = new Set(['input', 'select', 'textarea', 'button']);
const LIMITS = ['maxlength', 'minlength', 'pattern', 'min', 'max', 'step', 'accept'];
const SIGN_IN_PATH = /(^|[\/_-])(log-?in|sign-?in|auth|sso)([\/_.?-]|$)/i;
const TIMEOUT_MS = 15000;
const TAG = /<(\/?)([a-zA-Z][\w:-]*)((?:\s+[^\s"'>\/=]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+))?)*)\s*\/?>/g;
const ATTR = /([^\s"'>\/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
const ENTITIES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };

function decode(s) {
  return s.replace(/&(#x[0-9a-f]+|#[0-9]+|[a-z]+);/gi, (m, e) => {
    if (e[0] !== '#') return ENTITIES[e.toLowerCase()] ?? m;
    const n = e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
    return n > 0 && n <= 0x10ffff ? String.fromCodePoint(n) : m;
  });
}

function attrs(src) {
  const out = Object.create(null);
  for (const m of src.matchAll(ATTR)) {
    const name = m[1].toLowerCase();
    if (!(name in out)) out[name] = decode(m[2] ?? m[3] ?? m[4] ?? '');
  }
  return out;
}

function absolute(href, base) {
  try {
    return new URL(href, base ?? undefined).href;
  } catch {
    return null;
  }
}

function pathOf(url) {
  try {
    return new URL(url).pathname;
  } catch {
    return '';
  }
}

// Hosts on your own machine or network. --open prints a contract there only when the page itself is on
// that host, so a page cannot point this script at your network and have it print what it finds.
const LOCAL_HOST =
  /^(localhost|.+\.localhost|.+\.local|.+\.internal|0\.0\.0\.0|127\.\d+\.\d+\.\d+|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|169\.254\.\d+\.\d+|\[::1?\]|\[::ffff:[^\]]*\]|\[f[cd][0-9a-f]{0,2}:[^\]]*\]|\[fe[89ab][0-9a-f]:[^\]]*\])$/i;

function hostOf(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return '';
  }
}

const isLocal = (url) => LOCAL_HOST.test(hostOf(url));

// Which of the contract rels a link carries.
function picked(relValue, type, href) {
  const rels = relValue.toLowerCase().split(/\s+/).filter(Boolean);
  const out = rels.filter((r) => CONTRACT_RELS.includes(r));
  if (rels.includes('alternate') && (type ? DATA_TYPE.test(type) : DATA_FILE.test(href))) out.push('alternate');
  return out;
}

function scan(html, pageUrl) {
  const text = html
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1\s*>/gi, ' ');
  const tags = [...text.matchAll(TAG)].map((m) => ({
    close: m[1] === '/',
    name: m[2].toLowerCase(),
    a: attrs(m[3] ?? ''),
    end: m.index + m[0].length,
  }));
  const baseTag = tags.find((t) => !t.close && t.name === 'base' && t.a.href !== undefined);
  const base = (baseTag && absolute(baseTag.a.href, pageUrl)) || pageUrl;
  const links = [];
  const forms = [];
  let form = null;
  let select = null;
  let password = false;

  for (const t of tags) {
    const a = t.a;
    if (t.close) {
      if (t.name === 'form') form = null;
      if (t.name === 'select') select = null;
      continue;
    }
    if (t.name === 'input' && (a.type ?? '').toLowerCase() === 'password') password = true;
    if (t.name === 'link' && a.rel && a.href !== undefined) {
      for (const rel of picked(a.rel, a.type, a.href)) {
        links.push({ rel, href: a.href, url: absolute(a.href, base), type: a.type ?? '', from: '<link>' });
      }
    } else if (t.name === 'form') {
      form = {
        method: (a.method || 'get').toUpperCase(),
        action: a.action ?? '',
        url: a.action ? absolute(a.action, base) : pageUrl ?? null,
        enctype: a.enctype || 'application/x-www-form-urlencoded',
        fields: [],
      };
      forms.push(form);
    } else if (form && FIELD_TAGS.has(t.name)) {
      let type = t.name;
      if (t.name === 'input') type = (a.type || 'text').toLowerCase();
      if (t.name === 'button') type = `button (${(a.type || 'submit').toLowerCase()})`;
      if (a.name === undefined || a.name === '') continue; // a field without a name is not sent
      const field = {
        name: a.name,
        type,
        required: 'required' in a,
        limits: LIMITS.filter((k) => a[k] !== undefined).map((k) => `${k}=${a[k]}`),
        options: [],
        value: type === 'hidden' ? a.value ?? '' : undefined,
      };
      form.fields.push(field);
      if (t.name === 'select') select = field;
    } else if (t.name === 'option' && select) {
      if (a.value !== undefined) select.options.push(a.value);
      else {
        const stop = text.indexOf('<', t.end);
        select.options.push(decode(text.slice(t.end, stop === -1 ? undefined : stop)).trim());
      }
    }
  }
  return { links, forms, password };
}

function linkHeader(value, pageUrl) {
  const out = [];
  for (const m of (value ?? '').matchAll(/<([^>]*)>((?:\s*;\s*[^;,]+)*)/g)) {
    const params = Object.create(null);
    for (const p of m[2].matchAll(/;\s*([^\s=;,]+)\s*(?:=\s*(?:"([^"]*)"|([^\s;,]+)))?/g)) {
      params[p[1].toLowerCase()] = p[2] ?? p[3] ?? '';
    }
    if (!params.rel) continue;
    for (const rel of picked(params.rel, params.type, m[1])) {
      out.push({ rel, href: m[1], url: absolute(m[1], pageUrl), type: params.type ?? '', from: 'Link header' });
    }
  }
  return out;
}

// Is the response itself a contract?
function selfContract(body, type) {
  const head = body.trimStart().slice(0, 2000);
  if (/json/i.test(type) || head.startsWith('{')) {
    try {
      const j = JSON.parse(body);
      if (j && typeof j === 'object' && !Array.isArray(j)) {
        if (typeof j.openapi === 'string' || typeof j.swagger === 'string') return 'an OpenAPI document';
        if (typeof j.asyncapi === 'string') return 'an AsyncAPI document';
        if (typeof j.$schema === 'string') return 'a JSON Schema';
      }
    } catch {
      // not JSON
    }
  }
  if (/^(openapi|swagger|asyncapi)\s*:\s*['"]?\d/m.test(head)) return 'an API description in YAML';
  return null;
}

const isHtml = (body, type) => /html|xml/i.test(type) || (!type && /<(!doctype|html|head|body|link|form)\b/i.test(body));

function report(page) {
  const lines = [`page: ${page.where}${page.status === null ? '' : ` (${page.status}${page.type ? `, ${page.type}` : ''})`}`];
  const own = selfContract(page.body, page.type);
  const html = isHtml(page.body, page.type) ? scan(page.body, page.base) : { links: [], forms: [], password: false };
  const links = [...html.links, ...linkHeader(page.header, page.base)];
  const signIn =
    page.status === 401 ||
    page.status === 403 ||
    html.password ||
    (page.redirected && SIGN_IN_PATH.test(pathOf(page.where)));
  if (signIn) {
    lines.push(
      'sign-in: this may be a sign-in page, not the page you meant. Ask your human to save the signed-in page ' +
        'into the working folder, then run: node find-contract.mjs <saved-file> --base <its URL>',
    );
  }
  if (own) lines.push(`itself: this response is ${own}.`);

  lines.push(links.length ? 'declared contracts:' : 'declared contracts: none on this page');
  links.forEach((l, i) => {
    const where = l.url ?? `${l.href} (relative: run again with --base <page URL>)`;
    lines.push(`  ${i + 1}. ${l.rel.padEnd(12)} ${where}${l.type ? `  type ${l.type}` : ''}  from ${l.from}`);
  });

  lines.push(html.forms.length ? 'forms:' : 'forms: none in this HTML');
  html.forms.forEach((f, i) => {
    const target = f.url ?? `${f.action || "this page's own URL"} (relative: run again with --base <page URL>)`;
    lines.push(`  ${i + 1}. ${f.method} ${target}  ${f.enctype}`);
    if (f.fields.length === 0) lines.push('     no named fields in this HTML');
    for (const x of f.fields) {
      const parts = [x.name, x.type];
      if (x.required) parts.push('required');
      parts.push(...x.limits);
      if (x.options.length) parts.push(`options: ${x.options.map((o) => JSON.stringify(o)).join(', ')}`);
      if (x.value !== undefined) parts.push(`value ${JSON.stringify(x.value)}`);
      lines.push(`     - ${parts.join('  ')}`);
    }
  });

  const found = Boolean(own) || links.length > 0 || html.forms.length > 0;
  const rules = 'the required fields, their types and limits, and whether extra keys are allowed';
  if (links.length) {
    lines.push(`next: open each contract above (--open prints them) and quote what your body must follow: ${rules}. Build the body from that quote.`);
  } else if (own) {
    lines.push(`next: quote what your body must follow from this response: ${rules}. Build the body from that quote.`);
  } else if (found) {
    lines.push("next: quote the form's fields and limits, then build the body from them.");
  } else {
    lines.push('next: nothing is declared here. Ask your human where the contract is. Do not guess a shape.');
  }
  return { lines, links, found };
}

const why = (e) =>
  `${e.name === 'TimeoutError' ? `no answer within ${TIMEOUT_MS / 1000} seconds` : e.message}` +
  (e.cause ? `: ${e.cause.code ?? e.cause.message}` : '');

async function get(url) {
  const res = await fetch(url, {
    redirect: 'follow',
    headers: { accept: 'text/html,application/xhtml+xml,application/json,application/yaml;q=0.9,*/*;q=0.8' },
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  return {
    url: res.url || url,
    status: res.status,
    type: res.headers.get('content-type') ?? '',
    link: res.headers.get('link') ?? '',
    body: await res.text(),
  };
}

async function openAll(links, pageUrl) {
  const urls = [...new Set(links.map((l) => l.url).filter((u) => u && /^https?:/i.test(u)))];
  if (urls.length === 0) {
    console.log('open: no absolute http or https contract URL to open');
    return;
  }
  const pageHost = hostOf(pageUrl);
  const allowed = (u) => !isLocal(u) || hostOf(u) === pageHost;
  const skip = "a local or private address that is not the page's own host. Ask your human before you open it.";
  for (const [i, u] of urls.entries()) {
    if (!allowed(u)) {
      console.log(`\n--- contract ${i + 1}: ${u} not opened: ${skip} ---`);
      continue;
    }
    try {
      const r = await get(u);
      if (!allowed(r.url)) {
        console.log(`\n--- contract ${i + 1}: ${u} moved to ${r.url}, not printed: ${skip} ---`);
        continue;
      }
      console.log(`\n--- contract ${i + 1}: ${r.url} (${r.status}${r.type ? `, ${r.type}` : ''}) ---`);
      console.log(r.body);
      console.log(`--- end of contract ${i + 1} ---`);
    } catch (e) {
      console.log(`\n--- contract ${i + 1}: ${u} could not be fetched: ${why(e)} ---`);
    }
  }
}

async function readInside(path) {
  const cwd = await realpath(process.cwd());
  let real;
  try {
    real = await realpath(resolve(cwd, path));
  } catch {
    throw new Error(`cannot read ${path}: no such file`);
  }
  const rel = relative(cwd, real);
  if (rel === '..' || rel.startsWith(`..${sep}`) || isAbsolute(rel)) {
    throw new Error(
      `${path} is outside the working folder (${cwd}). Ask your human before reading it; if they agree, copy it into the working folder and run this again.`,
    );
  }
  return readFile(real, 'utf8');
}

function selfTest() {
  const html = `<!doctype html>
<html><head>
<base href="https://api.example.test/v2/">
<link rel="stylesheet" href="site.css">
<link rel="service-desc" type="application/openapi+json" href="openapi.json">
<link rel="alternate" type="application/rss+xml" href="feed.xml">
<link rel="alternate" type="application/schema+json" href="note.schema.json">
<!-- <link rel="describedby" href="old.json"> -->
<script>const s = '<link rel="describedby" href="fake.json">';</script>
</head><body>
<form action="notes" method="post">
<input name="title" required maxlength="80">
<textarea name="body" required></textarea>
<select name="kind"><option value="note">Note</option><option>Task</option></select>
<input type="hidden" name="form_id" value="n&amp;1">
<input type="submit" value="Save">
</form>
</body></html>`;
  const r = scan(html, 'https://example.test/notes/new');
  assert.deepEqual(
    r.links.map((l) => [l.rel, l.url]),
    [
      ['service-desc', 'https://api.example.test/v2/openapi.json'],
      ['alternate', 'https://api.example.test/v2/note.schema.json'],
    ],
  );
  assert.equal(r.forms.length, 1);
  const [f] = r.forms;
  assert.equal(f.method, 'POST');
  assert.equal(f.url, 'https://api.example.test/v2/notes');
  assert.deepEqual(f.fields.map((x) => x.name), ['title', 'body', 'kind', 'form_id']);
  assert.deepEqual(f.fields[0].limits, ['maxlength=80']);
  assert.equal(f.fields[0].required, true);
  assert.equal(f.fields[1].type, 'textarea');
  assert.deepEqual(f.fields[2].options, ['note', 'Task']);
  assert.equal(f.fields[3].value, 'n&1');
  assert.equal(r.password, false);

  const h = linkHeader(
    '<https://api.example.test/docs>; rel="service-doc", <note.json>; rel=describedby; type="application/schema+json", <https://x.test/a>; rel=next',
    'https://api.example.test/v2/x',
  );
  assert.deepEqual(
    h.map((l) => [l.rel, l.url]),
    [
      ['service-doc', 'https://api.example.test/docs'],
      ['describedby', 'https://api.example.test/v2/note.json'],
    ],
  );

  assert.equal(selfContract('{"$schema":"https://json-schema.org/draft-07/schema#","type":"object"}', 'application/json'), 'a JSON Schema');
  assert.equal(selfContract('openapi: "3.1.0"\ninfo:\n  title: Notes\n', 'application/yaml'), 'an API description in YAML');
  assert.equal(report({ where: 'x.html', status: null, type: '', header: '', body: '<p>hi</p>', base: null, redirected: false }).found, false);

  assert.equal(isLocal('http://169.254.169.254/latest/meta-data/'), true);
  assert.equal(isLocal('http://[::1]:8080/openapi.json'), true);
  assert.equal(isLocal('http://192.168.1.20/schema.json'), true);
  assert.equal(isLocal('https://api.example.test/v2/openapi.json'), false);
  assert.equal(isLocal('not a url'), false);
  console.log('self-test ok');
  return 0;
}

async function main(argv) {
  if (argv.includes('--self-test')) return selfTest();
  let target;
  let base;
  let open = false;
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === '--open') open = true;
    else if (a === '--base') {
      i += 1;
      base = argv[i];
      if (base === undefined || !/^https?:\/\//i.test(base)) throw new Error('--base takes an http or https URL');
    } else if (a === '--help' || a === '-h') {
      console.log(USAGE);
      return 0;
    } else if (a.startsWith('--')) throw new Error(`unknown option ${a}\n${USAGE}`);
    else if (target === undefined) target = a;
    else throw new Error(`one page at a time\n${USAGE}`);
  }
  if (target === undefined) throw new Error(USAGE);

  let page;
  if (/^https?:\/\//i.test(target)) {
    let r;
    try {
      r = await get(target);
    } catch (e) {
      throw new Error(`could not fetch ${target}: ${why(e)}`);
    }
    page = { where: r.url, status: r.status, type: r.type, header: r.link, body: r.body, base: base ?? r.url, redirected: r.url !== target };
  } else if (/^[a-z][a-z0-9+.-]*:\/\//i.test(target)) {
    throw new Error('give an http or https URL, or a file in the working folder');
  } else {
    page = { where: target, status: null, type: '', header: '', body: await readInside(target), base: base ?? null, redirected: false };
  }

  const { lines, links, found } = report(page);
  console.log(lines.join('\n'));
  if (open) await openAll(links, page.base);
  return found ? 0 : 2;
}

try {
  process.exitCode = await main(process.argv.slice(2));
} catch (error) {
  console.error(`find-contract: ${error.message}`);
  process.exitCode = 1;
}
