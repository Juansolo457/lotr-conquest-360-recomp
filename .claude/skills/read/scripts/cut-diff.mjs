#!/usr/bin/env node
// cut-diff.mjs: check a short version against the text a person gave you.
//
//   node cut-diff.mjs <original> <short> [--keep-file <file>] [--keep "<passage>"]...
//                     [--max-chars <n>] [--max-words <n>]
//   node cut-diff.mjs --self-test
//
// It prints:
//   - the counts, and how they stand against the person's limit;
//   - for each keep passage, whether it is still in the short version character for character,
//     and if not, the first character that differs, with its code point;
//   - every sentence of the original that is not in the short version (the cut list);
//   - every sentence of the short version that is not in the original (new wording).
// Exit code: 0 = ok, 1 = a FAIL or an error.
//
// Keep file: the passages to keep exactly, with a line that holds only --- between them.
// Characters are Unicode code points. Words are runs of non-space characters.
// CRLF is read as LF, and one line break at the very end of a file is not counted.
// No network. Reads only files inside the current working folder. Writes nothing.
// Plain Node.js 18 or newer, no dependencies.

import assert from 'node:assert/strict';
import { readFile, realpath } from 'node:fs/promises';
import { isAbsolute, relative, resolve, sep } from 'node:path';

const USAGE = `usage:
  node cut-diff.mjs <original> <short> [--keep-file <file>] [--keep "<passage>"]... [--max-chars <n>] [--max-words <n>]
  node cut-diff.mjs --self-test`;

const NAMES = new Map([
  [0x09, 'tab'],
  [0x0a, 'line break'],
  [0x20, 'space'],
  [0x22, 'straight double quote'],
  [0x27, 'apostrophe'],
  [0x2d, 'hyphen-minus'],
  [0xa0, 'no-break space'],
  [0x2009, 'thin space'],
  [0x200b, 'zero-width space'],
  [0x2010, 'hyphen'],
  [0x2011, 'non-breaking hyphen'],
  [0x2013, 'en dash'],
  [0x2014, 'em dash'],
  [0x2018, 'left single quote'],
  [0x2019, 'right single quote'],
  [0x201c, 'left double quote'],
  [0x201d, 'right double quote'],
  [0x2026, 'ellipsis'],
  [0x202f, 'narrow no-break space'],
  [0x2212, 'minus sign'],
  [0xfeff, 'zero-width no-break space'],
]);

const points = (s) => Array.from(s);
const squash = (s) => s.replace(/\s+/gu, ' ').trim();
const norm = (s) => s.replace(/^﻿/, '').replace(/\r\n?/g, '\n').replace(/\n$/, '');
const fmt = (n) => n.toLocaleString('en-US');
const plural = (n, one, many) => `${fmt(n)} ${n === 1 ? one : many}`;
const visible = (s) => s.replace(/\n/g, '⏎').replace(/\t/g, '⇥');

function describe(cp) {
  const hex = `U+${cp.toString(16).toUpperCase().padStart(4, '0')}`;
  const ch = String.fromCodePoint(cp);
  const shown = /[\s\p{C}]/u.test(ch) ? '' : `${ch} `;
  const name = NAMES.get(cp);
  return `${shown}${hex}${name ? ` ${name}` : ''}`;
}

function counts(s) {
  const t = s.trim();
  return { chars: points(s).length, utf16: s.length, words: t === '' ? 0 : t.split(/\s+/u).length };
}

// Sentences, one paragraph and one line at a time. p = paragraph number, from 1.
function sentences(text) {
  const out = [];
  text.split(/\n(?:[ \t]*\n)+/).forEach((para, i) => {
    for (const line of para.split('\n')) {
      for (const piece of line.split(/(?<=[.!?…]["'”’)\]]*)\s+/u)) {
        const t = piece.trim();
        if (t) out.push({ p: i + 1, text: t });
      }
    }
  });
  return out;
}

// The longest start (or end) of the passage, in code points, that occurs in hay.
function longestMatch(P, hay, fromEnd) {
  const piece = (n) => (fromEnd ? P.slice(P.length - n) : P.slice(0, n)).join('');
  let lo = 0;
  let hi = P.length;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    if (hay.includes(piece(mid))) lo = mid;
    else hi = mid - 1;
  }
  return { n: lo, text: piece(lo) };
}

function around(arr, i) {
  const a = Math.max(0, i - 15);
  const b = Math.min(arr.length, i + 16);
  return `${a > 0 ? '…' : ''}${visible(arr.slice(a, b).join(''))}${b < arr.length ? '…' : ''}`;
}

// Where the passage stops matching hay. null = it matches whole.
function firstDifference(passage, hay) {
  const P = points(passage);
  const head = longestMatch(P, hay, false);
  if (head.n === P.length) return null;
  const tail = longestMatch(P, hay, true);
  if (Math.max(head.n, tail.n) < 8) return { missing: true };
  const H = points(hay);
  if (head.n >= tail.n) {
    const at = points(hay.slice(0, hay.indexOf(head.text))).length + head.n;
    return {
      fromEnd: false,
      index: head.n,
      expected: P[head.n].codePointAt(0),
      found: H[at]?.codePointAt(0),
      keep: around(P, head.n),
      hay: around(H, at),
    };
  }
  const index = P.length - tail.n - 1;
  const at = points(hay.slice(0, hay.indexOf(tail.text))).length - 1;
  return {
    fromEnd: true,
    index,
    expected: P[index].codePointAt(0),
    found: at >= 0 ? H[at].codePointAt(0) : undefined,
    keep: around(P, index),
    hay: around(H, Math.max(at, 0)),
  };
}

function explain(diff, len, where, pad) {
  if (diff === null) return [];
  if (diff.missing) return [`${pad}not found in the ${where} text: it was cut or rewritten`];
  const edge = diff.fromEnd ? 'start' : 'end';
  return [
    `${pad}${diff.fromEnd ? 'last' : 'first'} difference at character ${fmt(diff.index + 1)} of ${fmt(len)}${diff.fromEnd ? ' (the end matches)' : ''}`,
    `${pad}keep      ${diff.keep}`,
    `${pad}${where.padEnd(10)}${diff.hay}`,
    `${pad}expected ${describe(diff.expected)}, found ${diff.found === undefined ? `the ${edge} of the text` : describe(diff.found)}`,
  ];
}

function preview(s) {
  const P = points(s);
  return `"${visible(P.slice(0, 40).join(''))}${P.length > 40 ? '…' : ''}"`;
}

function check({ original, short, keeps = [], maxChars, maxWords }) {
  const lines = [];
  const problems = [];
  const o = counts(original);
  const s = counts(short);
  const removed = o.chars - s.chars;
  const share = o.chars === 0 ? 0 : Math.round((removed * 1000) / o.chars) / 10;

  lines.push('counts');
  lines.push(`  original  ${plural(o.chars, 'character', 'characters')}, ${plural(o.words, 'word', 'words')}`);
  lines.push(
    `  short     ${plural(s.chars, 'character', 'characters')}, ${plural(s.words, 'word', 'words')}` +
      (s.utf16 === s.chars ? '' : ` (UTF-16 length ${fmt(s.utf16)})`),
  );
  lines.push(
    removed >= 0
      ? `  removed   ${plural(removed, 'character', 'characters')} (${share}% of the original)`
      : `  removed   none: the short version is ${plural(-removed, 'character', 'characters')} longer`,
  );
  if (maxChars !== undefined) {
    const left = maxChars - s.chars;
    lines.push(`  limit     ${fmt(maxChars)} characters: ${left >= 0 ? `${fmt(left)} under` : `${fmt(-left)} over`}`);
    if (o.chars > maxChars) lines.push(`            to fit, at least ${plural(o.chars - maxChars, 'character', 'characters')} of the original must go`);
    if (left < 0) problems.push(`${plural(-left, 'character', 'characters')} over the limit`);
  }
  if (maxWords !== undefined) {
    const left = maxWords - s.words;
    lines.push(`  limit     ${fmt(maxWords)} words: ${left >= 0 ? `${fmt(left)} under` : `${fmt(-left)} over`}`);
    if (left < 0) problems.push(`${plural(-left, 'word', 'words')} over the limit`);
  }

  lines.push('keep');
  if (keeps.length === 0) {
    lines.push('  none given. If the person named a passage to keep exactly, put it in a keep file and run this again.');
  }
  keeps.forEach((keep, i) => {
    const n = i + 1;
    const head = `  ${n}  `;
    const pad = ' '.repeat(head.length + 6);
    const len = points(keep).length;
    if (!original.includes(keep)) {
      problems.push(`keep ${n} is not in the original`);
      lines.push(`${head}FAIL  not in the original exactly: copy it from the original file, do not retype it`);
      lines.push(...explain(firstDifference(keep, original), len, 'original', pad));
      return;
    }
    if (short.includes(keep)) {
      lines.push(`${head}ok    ${preview(keep)} (${plural(len, 'character', 'characters')})`);
      return;
    }
    const spacing = squash(short).includes(squash(keep));
    problems.push(`keep ${n} ${spacing ? 'has different spacing' : 'changed or cut'}`);
    lines.push(`${head}FAIL  ${spacing ? 'matches only if spaces and line breaks are ignored' : 'changed or cut'}`);
    lines.push(...explain(firstDifference(keep, short), len, 'short', pad));
  });

  const shortFlat = squash(short);
  const originalFlat = squash(original);
  const cut = sentences(original).filter((x) => !shortFlat.includes(squash(x.text)));
  const added = sentences(short).filter((x) => !originalFlat.includes(squash(x.text)));
  lines.push(
    cut.length === 0
      ? 'cut: every sentence of the original is in the short version'
      : `cut: ${plural(cut.length, 'sentence', 'sentences')} of the original ${cut.length === 1 ? 'is' : 'are'} not in the short version`,
  );
  for (const x of cut) lines.push(`  - p${x.p}  ${visible(x.text)}`);
  lines.push(
    added.length === 0
      ? 'new wording: none'
      : `new wording: ${plural(added.length, 'sentence', 'sentences')} of the short version ${added.length === 1 ? 'is' : 'are'} not in the original`,
  );
  for (const x of added) lines.push(`  + p${x.p}  ${visible(x.text)}`);

  const ok = problems.length === 0;
  lines.push(ok ? 'result: ok' : `result: FAIL (${problems.join('; ')})`);
  lines.push(
    ok
      ? 'next: show the person the counts, the keep check and the cut list before you send or save the short version.'
      : 'next: fix each FAIL (for a keep passage, change only the characters shown), then run this again.',
  );
  return { ok, lines, cut, added };
}

const parseKeepFile = (text) =>
  text
    .split(/^---[ \t]*$/m)
    .map((p) => p.replace(/^\n+|\n+$/g, ''))
    .filter((p) => p !== '');

function wholeNumber(value, flag) {
  const n = Number(value);
  if (!Number.isInteger(n) || n < 0) throw new Error(`${flag} takes a whole number`);
  return n;
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
  const original = norm(
    'Status for Tuesday.\n\nThe build is green. We moved the release to Thursday.\n\n' +
      'Deploy freeze: nothing ships after 16:00 on Friday, and we don’t merge without a review.\n\nLunch is at noon.\n',
  );
  const keep = 'Deploy freeze: nothing ships after 16:00 on Friday, and we don’t merge without a review.';
  const bad = "Release moved to Thursday.\n\nDeploy freeze: nothing ships after 16:00 on Friday, and we don't merge without a review.";
  const good = bad.replace("don't", 'don’t');

  const b = check({ original, short: bad, keeps: [keep], maxChars: 200 });
  assert.equal(b.ok, false);
  assert.ok(b.lines.some((l) => l.includes("expected ’ U+2019 right single quote, found ' U+0027 apostrophe")));
  assert.ok(b.lines.some((l) => l.includes('first difference at character 63 of 88')));

  const g = check({ original, short: good, keeps: [keep], maxChars: 200 });
  assert.equal(g.ok, true);
  assert.deepEqual(
    g.cut.map((x) => x.text),
    ['Status for Tuesday.', 'The build is green.', 'We moved the release to Thursday.', 'Lunch is at noon.'],
  );
  assert.deepEqual(g.added.map((x) => x.text), ['Release moved to Thursday.']);

  assert.equal(check({ original, short: good, keeps: [keep], maxChars: 50 }).ok, false);
  assert.equal(check({ original, short: good, keeps: [keep.replace('’', "'")] }).ok, false);

  const spaced = check({ original, short: good.replace('16:00 on', '16:00\non'), keeps: [keep] });
  assert.equal(spaced.ok, false);
  assert.ok(spaced.lines.some((l) => l.includes('expected U+0020 space, found U+000A line break')));

  assert.deepEqual(parseKeepFile('one\n---\n\ntwo\nlines\n---\n'), ['one', 'two\nlines']);
  console.log('self-test ok');
  return 0;
}

async function main(argv) {
  if (argv.includes('--self-test')) return selfTest();
  const files = [];
  const keeps = [];
  let keepFile;
  let maxChars;
  let maxWords;
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    const value = () => {
      i += 1;
      if (argv[i] === undefined) throw new Error(`${a} needs a value\n${USAGE}`);
      return argv[i];
    };
    if (a === '--keep') keeps.push(norm(value()));
    else if (a === '--keep-file') keepFile = value();
    else if (a === '--max-chars') maxChars = wholeNumber(value(), a);
    else if (a === '--max-words') maxWords = wholeNumber(value(), a);
    else if (a === '--help' || a === '-h') {
      console.log(USAGE);
      return 0;
    } else if (a.startsWith('--')) throw new Error(`unknown option ${a}\n${USAGE}`);
    else files.push(a);
  }
  if (files.length !== 2) throw new Error(`give the original and the short version\n${USAGE}`);
  const [original, short] = (await Promise.all(files.map(readInside))).map(norm);
  if (keepFile !== undefined) keeps.unshift(...parseKeepFile(norm(await readInside(keepFile))));
  const result = check({ original, short, keeps, maxChars, maxWords });
  console.log(result.lines.join('\n'));
  return result.ok ? 0 : 1;
}

try {
  process.exitCode = await main(process.argv.slice(2));
} catch (error) {
  console.error(`cut-diff: ${error.message}`);
  process.exitCode = 1;
}
