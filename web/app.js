/* CS 201 Course Assistant: browser side.

   Plain JavaScript, no build step. The server owns all state that matters
   (conversation, approvals, files); this file draws it and sends what the user
   does. Sections:
     1. helpers and icons      4. file tree and viewer     7. approval cards
     2. markdown               5. chat transcript          8. composer
     3. settings and state     6. streaming a turn         9. startup
*/
'use strict';

/* 1. helpers and icons ------------------------------------------------------ */
const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'html') el.innerHTML = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) el.append(kid);
  return el;
}
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
  sget(k, d) { try { const v = sessionStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } },
  sset(k, v) { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
};

const ICONS = {
  folder: '<path d="M3 7.5A1.5 1.5 0 0 1 4.5 6H9l2 2h8.5A1.5 1.5 0 0 1 21 9.5v8a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5z"/>',
  folderOpen: '<path d="M3 17.5V7.5A1.5 1.5 0 0 1 4.5 6H9l2 2h7.5A1.5 1.5 0 0 1 20 9.5V11"/><path d="M3 17.5l2.4-5.6A1.5 1.5 0 0 1 6.8 11H21l-2.6 7.1a1.5 1.5 0 0 1-1.4.9H4.5A1.5 1.5 0 0 1 3 17.5z"/>',
  file: '<path d="M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v5h5"/>',
  lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  chevron: '<path d="M9 6l6 6-6 6"/>',
  person: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  branch: '<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="7" r="2"/><path d="M6 7v10"/><path d="M18 9c0 5-6 4-11.2 8.6"/>',
  clip: '<path d="M21 11.5l-8.6 8.6a5 5 0 0 1-7.1-7.1l9-9a3.3 3.3 0 0 1 4.7 4.7l-9 9a1.7 1.7 0 0 1-2.4-2.4l8.3-8.3"/>',
  send: '<path d="M5 12h13"/><path d="M12 5l7 7-7 7"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  ban: '<circle cx="12" cy="12" r="9"/><path d="M5.6 5.6l12.8 12.8"/>',
  panel: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
  files: '<path d="M8 4h6l4 4v10a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z"/><path d="M4 8v12a1 1 0 0 0 1 1h9"/>',
  shield: '<path d="M12 3l7 3v6c0 4.5-3 7.6-7 9-4-1.4-7-4.5-7-9V6z"/><path d="M9 12l2 2 4-4"/>',
};
const icon = (name, cls = '') => `<svg class="ic ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name]}</svg>`;
const iconEl = (name, cls) => { const t = document.createElement('template'); t.innerHTML = icon(name, cls); return t.content.firstChild; };

async function post(path, body) {
  const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `${r.status} ${r.statusText}`);
  return data;
}

/* 2. markdown (a small, safe subset: everything is escaped first) ----------- */
function inline(src) {
  const codes = [];
  let s = String(src).replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return `\u0000${codes.length - 1}\u0000`; });
  s = esc(s);
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  s = s.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^*\w])\*([^*\s][^*]*?)\*(?![*\w])/g, '$1<em>$2</em>');
  s = s.replace(/(^|[^\w])_([^_\s][^_]*?)_(?![\w])/g, '$1<em>$2</em>');
  s = s.replace(/~~([^~]+)~~/g, '<s>$1</s>');
  return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${esc(codes[+i])}</code>`);
}
const LIST_RE = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
const indentOf = (l) => l.match(/^\s*/)[0].replace(/\t/g, '    ').length;
function parseList(lines, i) {
  const base = indentOf(lines[i]);
  const ordered = /^\s*\d/.test(lines[i]);
  const start = ordered ? parseInt(lines[i].trim(), 10) : 1;
  const items = [];
  while (i < lines.length) {
    const m = lines[i].match(LIST_RE);
    if (!m) {
      if (lines[i].trim() && indentOf(lines[i]) > base && items.length) { items[items.length - 1].body += '<br>' + inline(lines[i].trim()); i++; continue; }
      break;
    }
    const ind = indentOf(lines[i]);
    if (ind < base) break;
    if (ind > base && items.length) { const r = parseList(lines, i); items[items.length - 1].body += r.html; i = r.i; continue; }
    if (/^\d/.test(m[2]) !== ordered) break;
    let text = m[3], cls = '';
    const t = text.match(/^\[([ xX])\]\s+(.*)$/);
    if (t) { cls = t[1] === ' ' ? 'task' : 'task done'; text = t[2]; }
    items.push({ cls, body: inline(text) });
    i++;
  }
  const tag = ordered ? 'ol' : 'ul';
  const lis = items.map((it) => `<li${it.cls ? ` class="${it.cls}"` : ''}>${it.body}</li>`).join('');
  return { html: `<${tag}${ordered && start !== 1 ? ` start="${start}"` : ''}>${lis}</${tag}>`, i };
}
const splitRow = (l) => l.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());
function md(src) {
  const lines = String(src || '').replace(/\r/g, '').split('\n');
  const out = [];
  let i = 0;
  const isBlockStart = (l) => /^```|^#{1,6}\s|^>\s?|^\s*([-*+]|\d+[.)])\s+|^\s*(---|\*\*\*)\s*$/.test(l) || /^\|.*\|\s*$/.test(l);
  while (i < lines.length) {
    const l = lines[i];
    if (/^```/.test(l)) {
      const lang = l.slice(3).trim();
      const buf = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]);
      i++;
      out.push(lang === 'diff' ? diffHtml(buf.join('\n')) : `<pre><code>${esc(buf.join('\n'))}</code></pre>`);
    } else if (/^#{1,6}\s/.test(l)) {
      const n = Math.min(l.match(/^#+/)[0].length + 1, 6);
      out.push(`<h${n}>${inline(l.replace(/^#+\s*/, ''))}</h${n}>`);
      i++;
    } else if (/^\s*(---|\*\*\*)\s*$/.test(l)) {
      out.push('<hr>');
      i++;
    } else if (/^\|.*\|\s*$/.test(l) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
      const head = splitRow(l);
      i += 2;
      const rows = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(splitRow(lines[i++]));
      out.push(`<table><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join('')}</tr></thead><tbody>${
        rows.map((r) => `<tr>${head.map((_, j) => `<td>${inline(r[j] ?? '')}</td>`).join('')}</tr>`).join('')}</tbody></table>`);
    } else if (/^>\s?/.test(l)) {
      const buf = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) buf.push(lines[i++].replace(/^>\s?/, ''));
      out.push(`<blockquote>${md(buf.join('\n'))}</blockquote>`);
    } else if (LIST_RE.test(l)) {
      const r = parseList(lines, i);
      out.push(r.html);
      i = r.i;
    } else if (!l.trim()) {
      i++;
    } else {
      const buf = [];
      while (i < lines.length && lines[i].trim() && !isBlockStart(lines[i])) buf.push(inline(lines[i++].trim()));
      if (!buf.length) { buf.push(inline(lines[i++])); }
      out.push(`<p>${buf.join('<br>')}</p>`);
    }
  }
  return out.join('');
}
function diffHtml(text) {
  const rows = String(text).split('\n').map((l) => {
    const cls = l.startsWith('+++') || l.startsWith('---') ? 'meta' : l.startsWith('@@') ? 'hunk' : l.startsWith('+') ? 'add' : l.startsWith('-') ? 'del' : '';
    return `<span class="${cls}">${esc(l) || ' '}</span>`;
  });
  return `<pre class="diff">${rows.join('')}</pre>`;
}
function splitFrontmatter(text) {
  if (text.startsWith('---\n')) {
    const end = text.indexOf('\n---', 4);
    if (end !== -1) return { fm: text.slice(4, end), body: text.slice(end + 4).replace(/^\n+/, '') };
  }
  return { fm: '', body: text };
}

/* 3. settings and state ---------------------------------------------------- */
const RESERVED = new Set(['professor', 'main', 'me', 'course', 'admin', 'root', 'head']);
const S = {
  config: null,
  prefs: store.get('ca.prefs', { role: 'student', username: 'alice', provider: 'Claude', models: {}, lfHost: '', lfCustom: '', enforce: true }),
  keys: store.sget('ca.keys', {}),                 // API keys: this tab only, never written to disk by the page
  layout: store.get('ca.layout', { sidebar: true, files: true }),
  open: new Set(store.get('ca.open', ['memory/course', 'memory/course/assignments', 'memory/me', 'submission'])),
  closedRoots: new Set(store.get('ca.closedRoots', [])),
  state: null,
  loadError: '',
  running: false,
  attachments: [],
  demoBase: null,
  demoAt: 0,
  seq: 0,
  drawerPath: null,
};
const savePrefs = () => store.set('ca.prefs', S.prefs);

function usernameError(name) {
  if (!/^[a-z0-9][a-z0-9-]{1,19}$/.test(name || '')) return 'Use 2 to 20 lowercase letters, digits or hyphens, starting with a letter or digit.';
  if (RESERVED.has(name)) return `“${name}” is reserved.`;
  return '';
}
function settings() {
  const p = S.prefs;
  const host = p.lfHost === 'custom' ? p.lfCustom : p.lfHost;
  return {
    role: p.role, username: p.role === 'professor' ? 'professor' : p.username, provider: p.provider,
    model: p.models[p.provider] || '', api_key: S.keys[p.provider] || '',
    lf_public: S.keys.lf_public || '', lf_secret: S.keys.lf_secret || '', lf_host: host || '', enforce: p.enforce,
  };
}
const identityOk = () => S.prefs.role === 'professor' || !usernameError(S.prefs.username);

async function loadState() {
  const seq = ++S.seq;
  if (!identityOk()) { S.state = null; renderAll(); return; }
  try {
    const st = await post('/api/state', { settings: settings() });
    if (seq !== S.seq) return;              // a newer request is on its way
    S.state = st;
    S.loadError = '';
    S.demoBase = new Date(st.demo_now);
    S.demoAt = Date.now();
  } catch (err) {
    if (seq !== S.seq) return;
    S.state = null;
    S.loadError = err.message;
  }
  renderAll();
}
let debounceTimer = 0;
const loadSoon = () => { clearTimeout(debounceTimer); debounceTimer = setTimeout(loadState, 450); };

function renderAll() {
  renderSidebar();
  renderHeader();
  renderTree();
  renderChat();
  renderComposer();
  if (S.drawerPath) refreshDrawer();
}

function initSidebar() {
  const cfg = S.config;
  const prov = $('#provider');
  for (const p of cfg.providers) prov.append(h('option', { value: p.label }, p.label));
  const host = $('#lf-host');
  for (const x of cfg.langfuse.hosts) host.append(h('option', { value: x.url }, x.label));
  host.append(h('option', { value: 'custom' }, 'Custom URL'));
  if (!S.prefs.lfHost) S.prefs.lfHost = cfg.langfuse.env_host && !cfg.langfuse.hosts.some((x) => x.url === cfg.langfuse.env_host) ? 'custom' : (cfg.langfuse.env_host || cfg.langfuse.hosts[0].url);
  if (S.prefs.lfHost === 'custom' && !S.prefs.lfCustom) S.prefs.lfCustom = cfg.langfuse.env_host;
  const preset = $('#preset');
  for (const p of cfg.presets) preset.append(h('option', { value: p.id }, p.label));

  // Open the sections that still need something.
  $('#sec-identity').open = !identityOk();
  const prov0 = cfg.providers.find((p) => p.label === S.prefs.provider);
  $('#sec-model').open = !(S.keys[S.prefs.provider] || prov0?.env_key_set);

  document.querySelectorAll('[data-role]').forEach((b) => b.addEventListener('click', () => {
    S.prefs.role = b.dataset.role; savePrefs(); loadState();
  }));
  $('#username').value = S.prefs.username;
  $('#username').addEventListener('input', (e) => {
    S.prefs.username = e.target.value.trim().toLowerCase(); savePrefs(); renderSidebar(); loadSoon();
  });
  prov.addEventListener('change', () => { S.prefs.provider = prov.value; savePrefs(); fillModelFields(); loadState(); });
  $('#model').addEventListener('input', (e) => { S.prefs.models[S.prefs.provider] = e.target.value.trim(); savePrefs(); loadSoon(); });
  $('#api-key').addEventListener('input', (e) => { S.keys[S.prefs.provider] = e.target.value.trim(); store.sset('ca.keys', S.keys); loadSoon(); });
  $('#lf-public').addEventListener('input', (e) => { S.keys.lf_public = e.target.value.trim(); store.sset('ca.keys', S.keys); loadSoon(); });
  $('#lf-secret').addEventListener('input', (e) => { S.keys.lf_secret = e.target.value.trim(); store.sset('ca.keys', S.keys); loadSoon(); });
  host.addEventListener('change', () => { S.prefs.lfHost = host.value; savePrefs(); renderSidebar(); loadState(); });
  $('#lf-custom').addEventListener('input', (e) => { S.prefs.lfCustom = e.target.value.trim(); savePrefs(); loadSoon(); });
  document.querySelectorAll('[data-enforce]').forEach((b) => b.addEventListener('click', () => {
    S.prefs.enforce = b.dataset.enforce === '1'; savePrefs(); loadState();
  }));
  $('#new-conversation').addEventListener('click', async () => {
    if (S.running) return;
    await post('/api/new', { settings: settings() }).catch((e) => alertBanner(e.message));
    loadState();
  });
  $('#reset-open').addEventListener('click', () => { $('#reset-box').hidden = false; $('#reset-open').hidden = true; });
  $('#reset-cancel').addEventListener('click', () => { $('#reset-box').hidden = true; $('#reset-open').hidden = false; });
  $('#reset-go').addEventListener('click', async () => {
    try {
      await post('/api/reset', { preset: $('#preset').value });
      $('#reset-box').hidden = true; $('#reset-open').hidden = false;
      closeDrawer();
      await loadState();
    } catch (e) { alertBanner(e.message); }
  });
  fillModelFields();
  $('#lf-public').value = S.keys.lf_public || '';
  $('#lf-secret').value = S.keys.lf_secret || '';
  $('#lf-custom').value = S.prefs.lfCustom || '';
  if (cfg.langfuse.env_set) {
    $('#lf-public').placeholder = 'Using LANGFUSE_PUBLIC_KEY from .env';
    $('#lf-secret').placeholder = 'Using LANGFUSE_SECRET_KEY from .env';
  } else {
    $('#lf-public').placeholder = 'pk-lf-…';
    $('#lf-secret').placeholder = 'sk-lf-…';
  }
}
function fillModelFields() {
  const p = S.config.providers.find((x) => x.label === S.prefs.provider);
  $('#provider').value = p.label;
  $('#model').value = S.prefs.models[p.label] || '';
  $('#model').placeholder = p.default_model || 'Model id, e.g. from the provider docs';
  $('#api-key').value = S.keys[p.label] || '';
  $('#api-key').placeholder = p.env_key_set ? `Using ${p.env_key_name} from .env` : 'Paste an API key';
  $('#key-hint').textContent = 'Keys stay in this browser tab and go only to your local server.';
}
function renderSidebar() {
  const p = S.prefs;
  document.querySelectorAll('[data-role]').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.role === p.role)));
  $('#username-field').hidden = p.role !== 'student';
  const uerr = p.role === 'student' ? usernameError(p.username) : '';
  $('#username-err').textContent = uerr;
  const sumId = $('#sum-identity');
  sumId.textContent = p.role === 'professor' ? 'Professor' : (uerr ? 'Pick a username' : `Student ${p.username}`);
  sumId.classList.toggle('warn', !!uerr);

  const prov = S.config.providers.find((x) => x.label === p.provider);
  const model = p.models[p.provider] || prov.default_model;
  const hasKey = !!(S.keys[p.provider] || prov.env_key_set);
  const sumModel = $('#sum-model');
  sumModel.textContent = !model ? `${p.provider}, no model` : hasKey ? `${p.provider} ${model}` : `${p.provider}, no key`;
  sumModel.classList.toggle('warn', !model || !hasKey);

  $('#lf-host').value = p.lfHost;
  $('#lf-custom-field').hidden = p.lfHost !== 'custom';
  const tr = S.state?.tracing;
  $('#sum-tracing').textContent = tr ? (tr.on ? 'On' : 'Off') : '';
  $('#tracing-status').innerHTML = tr ? `<span class="status-dot ${tr.on ? 'on' : ''}"></span>${esc(tr.message)}` : '';

  document.querySelectorAll('[data-enforce]').forEach((b) => b.setAttribute('aria-checked', String((b.dataset.enforce === '1') === p.enforce)));
  renderClock();
}
function renderClock() {
  if (!S.demoBase) return;
  const now = new Date(S.demoBase.getTime() + (Date.now() - S.demoAt));
  $('#demo-time-label').textContent = S.state?.clock_mode === 'pinned' ? 'Demo time (pinned by DEMO_NOW)' : 'Now';
  $('#demo-time').textContent = now.toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' });
}
function renderHeader() {
  const p = S.prefs;
  $('#who').textContent = p.role === 'professor' ? 'Professor' : (identityOk() ? p.username : 'Student');
  const prov = S.config.providers.find((x) => x.label === p.provider);
  const model = p.models[p.provider] || prov.default_model || 'no model';
  $('#who-sub').textContent = `${p.role === 'professor' ? 'Professor view' : 'Student view'}, ${p.provider} ${model}${p.enforce ? '' : ', prompt-only guardrails'}`;
  $('#toggle-sidebar').setAttribute('aria-pressed', String(S.layout.sidebar));
  $('#toggle-files').setAttribute('aria-pressed', String(S.layout.files));
  $('#app').classList.toggle('no-sidebar', !S.layout.sidebar);
  $('#app').classList.toggle('no-files', !S.layout.files);
}

/* 4. file tree and viewer -------------------------------------------------- */
function changedSet() { return new Set(S.state?.changed || []); }
function renderTree() {
  const tree = $('#tree');
  tree.innerHTML = '';
  if (!S.state) {
    tree.append(h('div', { class: 'tree-empty' }, identityOk() ? 'Loading…' : 'Pick a username to see your files.'));
    return;
  }
  const changed = changedSet();
  for (const root of S.state.tree) {
    const closed = S.closedRoots.has(root.vpath);
    const head = h('button', {
      class: 'root-head', type: 'button', 'aria-expanded': String(!closed),
      onclick: () => { closed ? S.closedRoots.delete(root.vpath) : S.closedRoots.add(root.vpath); store.set('ca.closedRoots', [...S.closedRoots]); renderTree(); },
    });
    head.innerHTML = `${icon('chevron', 'chev' + (closed ? '' : ' open'))}<span>${esc(root.label || root.name)}</span>`
      + (root.readonly ? '<span class="pill">read-only</span>' : '');
    head.querySelector('.chev').style.cssText = 'width:12px;height:12px;transition:transform .12s;' + (closed ? '' : 'transform:rotate(90deg)');
    const box = h('div', { class: 'root' }, head);
    if (!closed) {
      const kids = h('div', { class: 'children', style: '--d:0' });
      if (!root.children.length) kids.append(h('div', { class: 'tree-empty', style: '--d:0' }, 'Empty'));
      for (const c of root.children) kids.append(...treeRow(c, 0, changed));
      box.append(kids);
    }
    tree.append(box);
  }
}
function treeRow(node, depth, changed) {
  const open = S.open.has(node.vpath);
  const touched = node.is_dir ? [...changed].some((c) => c.startsWith(node.vpath + '/')) : changed.has(node.vpath);
  const row = h('button', {
    type: 'button',
    class: `row${node.locked ? ' locked' : ''}${touched && !node.is_dir ? ' changed' : ''}${S.drawerPath === node.vpath ? ' active' : ''}`,
    style: `--d:${depth}`,
    title: node.locked ? 'Hidden from students' : (touched && !node.is_dir ? 'Changed in the last reply' : null),
    disabled: node.opaque || null,
    'aria-expanded': node.is_dir && !node.opaque ? String(open) : null,
  });
  const kind = node.opaque ? 'person' : node.is_dir ? (open ? 'folderOpen' : 'folder') : 'file';
  row.innerHTML = (node.is_dir && !node.opaque ? icon('chevron', 'chev' + (open ? ' open' : '')) : '<span class="spacer"></span>')
    + icon(node.vpath.match(/^submissions\/[^/]+$/) ? 'branch' : kind)
    + `<span class="name">${esc(node.name)}</span>`
    + (node.locked ? icon('lock', 'lock') : '')
    + (node.meta ? `<span class="meta">${esc(node.meta)}</span>` : '')
    + (touched && (node.is_dir ? !open : true) ? '<span class="dot" aria-label="changed"></span>' : '');
  row.addEventListener('click', () => {
    if (node.is_dir) {
      open ? S.open.delete(node.vpath) : S.open.add(node.vpath);
      store.set('ca.open', [...S.open]);
      renderTree();
    } else {
      openDrawer(node.vpath);
    }
  });
  const out = [row];
  if (node.is_dir && open && !node.opaque) {
    const kids = h('div', { class: 'children', style: `--d:${depth + 1}` });
    if (!node.children.length) kids.append(h('div', { class: 'tree-empty', style: `--d:${depth + 1}` }, 'Empty'));
    for (const c of node.children) kids.append(...treeRow(c, depth + 1, changed));
    out.push(kids);
  }
  return out;
}
function openAncestors(paths) {
  for (const p of paths) {
    const parts = p.split('/');
    for (let i = 1; i < parts.length; i++) S.open.add(parts.slice(0, i).join('/'));
  }
  store.set('ca.open', [...S.open]);
}

async function openDrawer(vpath) {
  S.drawerPath = vpath;
  $('#drawer').hidden = false;
  renderTree();
  await refreshDrawer();
}
function closeDrawer() {
  S.drawerPath = null;
  $('#drawer').hidden = true;
  renderTree();
}
async function refreshDrawer() {
  const vpath = S.drawerPath;
  if (!vpath) return;
  $('#drawer-path').textContent = vpath;
  let f;
  try {
    f = await post('/api/file', { settings: settings(), path: vpath });
  } catch (err) {
    if (S.drawerPath !== vpath) return;
    $('#drawer-meta').innerHTML = '';
    $('#drawer-body').innerHTML = `<div class="callout error">${esc(err.message)}</div>`;
    return;
  }
  if (S.drawerPath !== vpath) return;
  const meta = $('#drawer-meta');
  meta.innerHTML = '';
  if (f.changed) meta.append(h('span', { class: 'tag hl' }, 'Changed in the last reply'));
  if (S.prefs.role === 'student' && f.readonly) meta.append(h('span', { class: 'tag' }, 'Read-only'));
  if (f.can_toggle) meta.append(accessControl(f));
  else if (f.hidden) meta.append(h('span', { class: 'tag', html: `${icon('lock')} Hidden from students` }));
  const body = $('#drawer-body');
  body.innerHTML = '';
  if (/\.md$/i.test(vpath)) {
    const { fm, body: text } = splitFrontmatter(f.text);
    if (fm) body.append(h('details', { class: 'fm' }, h('summary', {}, 'Header'), h('pre', { class: 'plain', html: esc(fm) })));
    body.append(h('div', { class: 'md', html: md(text) }));
  } else {
    body.append(h('pre', { class: 'plain', html: esc(f.text) }));
  }
}
function accessControl(f) {
  const wrap = h('div', { class: 'access' });
  const visible = !f.hidden;
  const sw = h('button', { type: 'button', class: 'switch', role: 'switch', 'aria-checked': String(visible), 'aria-label': 'Students can see this file' });
  const label = h('span', { html: visible ? 'Students can see this file' : `${icon('lock')} Hidden from students` });
  label.style.cssText = 'display:inline-flex;gap:5px;align-items:center';
  sw.addEventListener('click', () => {
    if (wrap.querySelector('.confirm')) return;
    const confirm = h('div', { class: 'confirm' },
      h('button', { type: 'button', class: 'go', onclick: async () => {
        try {
          await post('/api/access', { settings: settings(), path: f.path, access: visible ? 'hidden' : 'read' });
          await loadState();
        } catch (e) { alertBanner(e.message); }
      } }, visible ? 'Hide from students' : 'Show to students'),
      h('button', { type: 'button', onclick: () => confirm.remove() }, 'Cancel'));
    wrap.append(confirm);
  });
  wrap.append(sw, label);
  return wrap;
}

/* 5. chat transcript -------------------------------------------------------- */
const messages = () => $('#messages');
const nearBottom = (el) => el.scrollHeight - el.scrollTop - el.clientHeight < 140;
const toBottom = () => { const m = messages(); m.scrollTop = m.scrollHeight; };

function renderChat(force = false) {
  const box = messages();
  const stick = force || nearBottom(box);
  box.innerHTML = '';
  if (!S.state) {
    if (S.loadError) box.append(h('div', { class: 'error-box' }, S.loadError));
    return;
  }
  const st = S.state;
  if (!st.transcript.length && !st.pending.length) box.append(welcome());
  st.transcript.forEach((e, i) => box.append(entryEl(e, i === st.transcript.length - 1)));
  if (st.pending.length) box.append(approvalEl(st.pending[0], st.pending.length - 1));
  if (stick) toBottom();
}
function welcome() {
  const role = S.prefs.role;
  const intro = role === 'student'
    ? 'Ask about assignments and deadlines, plan your week, file your notes, or get a review or a hint.'
    : 'Publish assignments, update lectures, add hints, release solutions, or check who has submitted.';
  return h('div', { class: 'welcome' },
    h('h1', {}, role === 'student' ? `Hi ${S.prefs.username}` : 'Hi Professor'),
    h('p', {}, intro, ' Attach files with the paperclip or drop them here.'),
    h('div', { class: 'suggest' }, (S.state?.suggestions || []).map((t) => h('button', {
      type: 'button', onclick: () => { const inp = $('#input'); inp.value = t; autosize(); inp.focus(); renderComposer(); },
    }, t))));
}
function entryEl(e, isLast) {
  if (e.role === 'user') {
    return h('div', { class: 'msg user' },
      e.text ? h('div', { class: 'bubble' }, e.text) : null,
      e.files?.length ? h('div', { class: 'files-sent' }, e.files.map((f) => h('span', { class: 'chip', html: `${icon('clip')}<span>${esc(f)}</span>` }))) : null);
  }
  if (e.role === 'assistant') {
    return h('div', { class: 'msg assistant' },
      h('div', { class: 'md', html: md(e.text) }),
      e.trace_url ? h('div', { class: 'trace' }, h('a', { href: e.trace_url, target: '_blank', rel: 'noopener' }, 'View trace in Langfuse')) : null);
  }
  if (e.role === 'card') {
    return h('div', { class: `record ${e.ok ? 'ok' : 'no'}`, html: `${icon(e.ok ? 'check' : 'ban')}<span>${esc(e.text)}</span>` });
  }
  if (e.role === 'error') {
    const box = h('div', { class: 'error-box' }, h('div', {}, e.text));
    if (isLast && S.state?.can_retry) box.append(h('button', { type: 'button', class: 'btn', onclick: retry }, 'Retry'));
    return h('div', { class: 'msg' }, box);
  }
  return h('div');
}

/* 6. streaming a turn ------------------------------------------------------- */
function liveReply() {
  const body = h('div', { class: 'md' });
  const label = h('span', {}, 'Thinking');
  const status = h('div', { class: 'status' }, h('span', { class: 'dots', html: '<i></i><i></i><i></i>' }), label);
  const el = h('div', { class: 'msg assistant' }, body, status);
  messages().append(el);
  toBottom();
  let text = '';
  let frame = 0;
  return {
    text(t) {
      text += t;
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const stick = nearBottom(messages());
        body.innerHTML = md(text);
        status.hidden = true;
        if (stick) toBottom();
      });
    },
    status(t) { label.textContent = t; status.hidden = false; if (nearBottom(messages())) toBottom(); },
    error(m) { status.hidden = true; el.append(h('div', { class: 'error-box' }, m)); toBottom(); },
  };
}
async function runStream(path, init) {
  S.running = true;
  document.body.dataset.running = '1';
  renderComposer();
  const live = liveReply();
  try {
    const r = await fetch(path, init);
    if (!r.ok) {
      const data = await r.json().catch(() => ({}));
      throw new Error(data.error || `${r.status} ${r.statusText}`);
    }
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    const handle = (line) => {
      if (!line.trim()) return;
      const ev = JSON.parse(line);
      if (ev.type === 'text') live.text(ev.text);
      else if (ev.type === 'status') live.status(ev.text);
      else if (ev.type === 'error') live.error(ev.message);
    };
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf('\n')) >= 0) { handle(buf.slice(0, nl)); buf = buf.slice(nl + 1); }
    }
    handle(buf);
  } catch (err) {
    live.error(err.message);
  } finally {
    S.running = false;
    const before = new Set(S.state?.changed || []);
    await loadState();
    const fresh = (S.state?.changed || []).filter((c) => !before.has(c));
    if (fresh.length) {
      openAncestors(fresh);
      renderTree();
      document.querySelector('.row.changed')?.scrollIntoView({ block: 'nearest' });
    }
    renderChat(true);
    document.body.dataset.running = '0';
    $('#input').focus();
  }
}
function send() {
  if (S.running || !S.state?.ready || S.state.pending.length) return;
  const input = $('#input');
  const text = input.value.trim();
  const files = S.attachments.slice();
  if (!text && !files.length) return;
  S.state.transcript.push({ role: 'user', text, files: files.map((f) => f.name) });
  S.state.changed = [];
  renderChat(true);
  renderTree();
  input.value = '';
  S.attachments = [];
  autosize();
  renderChips();
  const fd = new FormData();
  fd.append('settings', JSON.stringify(settings()));
  fd.append('text', text);
  for (const f of files) fd.append('files', f, f.name);
  runStream('/api/chat', { method: 'POST', body: fd });
}
function decide(item, decision, record, ok) {
  if (S.running) return;
  S.state.pending = S.state.pending.filter((p) => p.id !== item.id);
  S.state.transcript.push({ role: 'card', text: record, ok });
  renderChat(true);
  runStream('/api/decide', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ settings: settings(), interrupt_id: item.id, decision }) });
}
function retry() {
  if (S.running) return;
  const t = S.state.transcript;
  if (t.length && t[t.length - 1].role === 'error') t.pop();
  renderChat(true);
  runStream('/api/retry', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ settings: settings() }) });
}

/* 7. approval cards ---------------------------------------------------------- */
const EDIT_FIELDS = {
  publish_assignment: [['title', 'Title'], ['due', 'Deadline (YYYY-MM-DDTHH:MM)'], ['professor_notes', 'Professor notes', true], ['overview', 'Overview', true], ['review_checklist', 'Review checklist', true]],
  update_assignment: [['due', 'New deadline (YYYY-MM-DDTHH:MM)'], ['note', 'Note', true]],
  write_file: [['content', 'Content', true]],
  append_to_file: [['text', 'Text to add', true]],
  remember: [['text', 'Text', true]],
  commit_changes: [['message', 'Commit message']],
  add_event: [['title', 'Title'], ['start', 'Start (YYYY-MM-DDTHH:MM)'], ['end', 'End (YYYY-MM-DDTHH:MM)']],
  save_hints: 'levels',
};
function summaryOf(item) {
  const a = item.args || {};
  const t = item.title.toLowerCase();
  if (a.path) return `${t} ${a.path}`;
  if (a.assignment_id) return `${t} ${String(a.assignment_id).toUpperCase()}`;
  if (item.name === 'commit_changes') return `commit “${a.message || ''}”`;
  if (item.name === 'add_event') return `event “${a.title || ''}”`;
  return t;
}
function approvalEl(item, more) {
  const card = h('div', { class: 'approval', role: 'group', 'aria-label': `Approval needed: ${item.title}` });
  card.append(h('div', { class: 'approval-head', html: `${icon('shield')}<strong>${esc(item.title)}</strong><span>needs your approval</span>` }));
  const body = h('div');
  body.append(previewEl(item.preview));
  card.append(body);

  let edited = null;
  const spec = EDIT_FIELDS[item.name];
  const approveBtn = h('button', { type: 'button', class: 'primary' }, 'Approve');
  let editBox = null;
  const readEdits = () => {
    const args = JSON.parse(JSON.stringify(item.args || {}));
    if (spec === 'levels') {
      args.levels = [...editBox.querySelectorAll('[data-level]')].map((t) => t.value);
    } else {
      for (const el of editBox.querySelectorAll('[data-key]')) args[el.dataset.key] = el.value;
      const roles = [...editBox.querySelectorAll('[data-file]')];
      if (roles.length) args.files = roles.map((s) => ({ upload: s.dataset.file, kind: s.value }));
    }
    return JSON.stringify(args) === JSON.stringify(item.args) ? null : args;
  };
  const onEdit = () => { edited = readEdits(); approveBtn.textContent = edited ? 'Approve with edits' : 'Approve'; };
  const actions = h('div', { class: 'actions' }, approveBtn);
  if (spec) {
    const editBtn = h('button', { type: 'button', class: 'secondary' }, 'Edit');
    editBtn.addEventListener('click', () => {
      if (editBox) { editBox.hidden = !editBox.hidden; return; }
      editBox = h('div', { class: 'edit-box' });
      if (spec === 'levels') {
        const lv = item.args.levels || ['', '', ''];
        ['Level 1 (nudge)', 'Level 2 (approach)', 'Level 3 (near-pseudocode)'].forEach((l, i) =>
          editBox.append(h('label', {}, l, h('textarea', { 'data-level': i, oninput: onEdit }, lv[i] || ''))));
      } else {
        for (const [key, label, multi] of spec) {
          const v = item.args[key] ?? '';
          editBox.append(h('label', {}, label, multi
            ? h('textarea', { 'data-key': key, oninput: onEdit }, String(v))
            : h('input', { 'data-key': key, value: String(v), oninput: onEdit })));
        }
        for (const f of item.args.files || []) {
          const sel = h('select', { 'data-file': f.upload, onchange: onEdit },
            ['handout', 'starter', 'solution'].map((k) => h('option', { value: k, selected: k === f.kind || null }, k)));
          editBox.append(h('label', {}, `Role of ${f.upload}`, sel));
        }
      }
      editBox.append(h('button', { type: 'button', class: 'secondary', onclick: async () => {
        const args = readEdits() || item.args;
        try {
          const p = await post('/api/preview', { settings: settings(), name: item.name, args });
          body.innerHTML = '';
          body.append(previewEl(p));
        } catch (e) { alertBanner(e.message); }
      } }, 'Update preview'));
      card.insertBefore(editBox, actions);
    });
    actions.append(editBtn);
  }
  const reason = h('input', { placeholder: 'Reason, if rejecting (optional)', 'aria-label': 'Reason for rejecting' });
  const rejectBtn = h('button', { type: 'button', class: 'secondary reject' }, 'Reject');
  approveBtn.addEventListener('click', () => {
    if (edited) decide(item, { type: 'edit', edited_action: { name: item.name, args: edited } }, `Approved with edits: ${summaryOf(item)}`, true);
    else decide(item, { type: 'approve' }, `Approved: ${summaryOf(item)}`, true);
  });
  rejectBtn.addEventListener('click', () => decide(item, { type: 'reject', message: reason.value.trim() }, `Rejected: ${summaryOf(item)}`, false));
  actions.append(rejectBtn, reason);
  card.append(actions);
  if (more > 0) card.append(h('div', { class: 'more' }, `${more} more waiting after this one.`));
  return card;
}
function previewEl(p) {
  const wrap = h('div');
  const section = (label, ...kids) => h('div', { class: 'ap-section' }, label ? h('div', { class: 'ap-label' }, label) : null, ...kids);
  switch (p.kind) {
    case 'error':
      wrap.append(h('div', { class: 'callout error' }, p.error),
        h('p', { class: 'hint' }, 'Approving will fail. Reject with a reason so the assistant can fix it.'));
      break;
    case 'publish': {
      wrap.append(section(null, h('strong', { style: 'font-size:16px' }, `${p.assignment.toUpperCase()}: ${p.title}`)));
      wrap.append(section('Deadline', h('div', { class: 'deadline', html: `<strong>${esc(p.due)}</strong><span class="quote">from “${esc(p.due_quote)}”</span>` })));
      const rows = p.files.map((f) => `<tr><td>${esc(f.original)}</td><td>${esc(f.role)}</td><td><code>${esc(f.stored_as)}</code></td><td>${
        f.students === 'hidden' ? `<span class="vis hidden">${icon('lock')}Hidden</span>` : `<span class="vis">${icon('eye')}Visible</span>`}</td></tr>`).join('');
      wrap.append(section('Files', h('table', { class: 'ap-files', html:
        `<thead><tr><th>Uploaded as</th><th>Role</th><th>Stored as</th><th>Students</th></tr></thead><tbody>${rows || '<tr><td colspan="4">No files</td></tr>'}</tbody>` })));
      wrap.append(section(null, tabs([
        ['guidelines.md', () => h('div', { class: 'md', html: md(splitFrontmatter(p.guidelines).body) })],
        ['Review checklist', () => h('div', { class: 'md', html: md(splitFrontmatter(p.checklist).body) })],
      ])));
      break;
    }
    case 'update':
      wrap.append(section(null, h('strong', {}, p.assignment.toUpperCase())));
      if (p.new_due) wrap.append(section('Deadline', h('div', { class: 'deadline', html: `<s>${esc(p.old_due)}</s><strong>${esc(p.new_due)}</strong>${p.due_quote ? `<span class="quote">from “${esc(p.due_quote)}”</span>` : ''}` })));
      if (p.note) wrap.append(section('Note', h('div', {}, p.note)));
      break;
    case 'file_change':
      wrap.append(section(null, h('span', { class: 'path' }, p.path), h('span', { class: 'tag' }, p.is_new ? 'New file' : 'Changes')));
      if (p.note) wrap.append(h('p', { class: 'hint', style: 'margin:-6px 0 10px' }, p.note));
      wrap.append(p.is_new ? h('pre', { class: 'plain', html: esc(p.after) }) : h('div', { html: diffHtml(p.diff || '(no change)') }));
      break;
    case 'access': {
      const showing = p.access === 'read';
      wrap.append(section(null, h('span', { class: 'path' }, p.path), h('span', { class: 'tag', html: showing ? `${icon('eye')} Visible to students` : `${icon('lock')} Hidden from students` })));
      if (p.deadline_info) wrap.append(h('div', { class: `callout ${/still submit/.test(p.deadline_info) ? 'warn' : 'info'}` }, p.deadline_info));
      break;
    }
    case 'commit':
      wrap.append(section(null, h('span', { html: `${icon('branch')} ` }), h('strong', {}, p.branch), h('span', {}, ` “${p.message}”`)));
      if (!p.files.length) wrap.append(h('div', { class: 'callout info' }, 'Nothing to commit.'));
      else wrap.append(section('Files', h('div', {}, p.files.map((f) => h('div', { class: 'path' }, `${f.status === '??' ? 'new' : f.status}  ${f.path}`)))));
      if (p.diff) wrap.append(h('div', { html: diffHtml(p.diff) }));
      for (const [path, text] of Object.entries(p.new_files || {})) {
        wrap.append(h('details', { class: 'newfile' }, h('summary', {}, `New file: ${path}`), h('pre', { class: 'plain', html: esc(text) })));
      }
      break;
    case 'event':
      wrap.append(section(null, h('strong', {}, p.title), h('div', {}, `${p.start} to ${p.end}`)));
      if (p.overlaps.length) wrap.append(h('div', { class: 'callout warn' }, `Overlaps: ${p.overlaps.join('; ')}`));
      break;
    default:
      wrap.append(h('pre', { class: 'plain', html: esc(JSON.stringify(p.args || p, null, 2)) }));
  }
  return wrap;
}
function tabs(defs) {
  const bar = h('div', { class: 'tabs', role: 'tablist' });
  const panel = h('div', { class: 'tab-panel', role: 'tabpanel' });
  const show = (i) => {
    [...bar.children].forEach((b, j) => b.setAttribute('aria-selected', String(i === j)));
    panel.innerHTML = '';
    panel.append(defs[i][1]());
  };
  defs.forEach(([label], i) => bar.append(h('button', { type: 'button', role: 'tab', onclick: () => show(i) }, label)));
  show(0);
  return h('div', {}, bar, panel);
}

/* 8. composer ---------------------------------------------------------------- */
function autosize() {
  const t = $('#input');
  t.style.height = 'auto';
  t.style.height = Math.min(t.scrollHeight, 200) + 'px';
}
function renderChips() {
  const chips = $('#chips');
  chips.innerHTML = '';
  S.attachments.forEach((f, i) => {
    const chip = h('span', { class: 'chip', html: `${icon('clip')}<span>${esc(f.name)}</span>` });
    chip.append(h('button', { type: 'button', 'aria-label': `Remove ${f.name}`, html: icon('x'), onclick: () => { S.attachments.splice(i, 1); renderChips(); renderComposer(); } }));
    chips.append(chip);
  });
}
function addFiles(list) {
  for (const f of list) if (!S.attachments.some((a) => a.name === f.name && a.size === f.size)) S.attachments.push(f);
  renderChips();
  renderComposer();
}
let bannerMsg = '';
function alertBanner(msg) { bannerMsg = msg; renderComposer(); setTimeout(() => { if (bannerMsg === msg) { bannerMsg = ''; renderComposer(); } }, 6000); }
function renderComposer() {
  const st = S.state;
  const banner = $('#banner');
  let note = null;
  if (bannerMsg) note = ['warn', bannerMsg];
  else if (!identityOk()) note = ['info', 'Pick a username in Identity to start.', 'Open settings', 'sec-identity'];
  else if (st && !st.ready) note = ['info', 'Add an API key and model in Model to start chatting.', 'Open settings', 'sec-model'];
  else if (st?.warning) note = ['warn', st.warning];
  else if (st && !S.prefs.enforce) note = ['warn', 'Prompt-only guardrails: permission checks are off. The rules live only in the prompt.'];
  banner.hidden = !note;
  if (note) {
    banner.className = `banner ${note[0]}`;
    banner.innerHTML = '';
    banner.append(h('span', {}, note[1]));
    if (note[2]) banner.append(h('button', { type: 'button', onclick: () => {
      S.layout.sidebar = true; store.set('ca.layout', S.layout); renderHeader();
      const sec = document.getElementById(note[3]); sec.open = true; sec.querySelector('input, select')?.focus();
    } }, note[2]));
  }
  const waiting = !!st?.pending?.length;
  const blocked = !st || !st.ready || waiting || S.running;
  const input = $('#input');
  input.disabled = !st || !st.ready || waiting;
  input.placeholder = waiting ? 'Decide on the approval card above first' : S.running ? 'Working…' : 'Message the course assistant';
  $('#attach').disabled = input.disabled;
  $('#send').disabled = blocked || (!input.value.trim() && !S.attachments.length);
  $('#composer').classList.toggle('disabled', input.disabled);
}

/* 9. startup ----------------------------------------------------------------- */
function wire() {
  $('#toggle-sidebar').innerHTML = icon('panel');
  $('#toggle-files').innerHTML = icon('files');
  $('#attach').innerHTML = icon('clip');
  $('#send').innerHTML = icon('send');
  $('#drawer-close').innerHTML = icon('x');
  $('#toggle-sidebar').addEventListener('click', () => { S.layout.sidebar = !S.layout.sidebar; store.set('ca.layout', S.layout); renderHeader(); });
  $('#toggle-files').addEventListener('click', () => { S.layout.files = !S.layout.files; store.set('ca.layout', S.layout); renderHeader(); });
  $('#drawer-close').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && S.drawerPath) closeDrawer(); });

  const input = $('#input');
  input.addEventListener('input', () => { autosize(); renderComposer(); });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); }
  });
  $('#composer').addEventListener('submit', (e) => { e.preventDefault(); send(); });
  $('#attach').addEventListener('click', () => $('#file-input').click());
  $('#file-input').addEventListener('change', (e) => { addFiles(e.target.files); e.target.value = ''; });

  const chat = $('#chat');
  let depth = 0;
  chat.addEventListener('dragenter', (e) => { if ([...e.dataTransfer.types].includes('Files')) { depth++; $('#drop').hidden = false; } });
  chat.addEventListener('dragleave', () => { depth = Math.max(0, depth - 1); if (!depth) $('#drop').hidden = true; });
  chat.addEventListener('dragover', (e) => e.preventDefault());
  chat.addEventListener('drop', (e) => {
    e.preventDefault(); depth = 0; $('#drop').hidden = true;
    if (!input.disabled && e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  });
  if (window.matchMedia('(max-width: 860px)').matches) { S.layout = { sidebar: false, files: false }; }
  setInterval(renderClock, 15000);
}

(async function start() {
  wire();
  try {
    S.config = await fetch('/api/config').then((r) => r.json());
  } catch (err) {
    document.body.innerHTML = `<p style="padding:24px">Couldn't reach the course assistant server: ${esc(err.message)}</p>`;
    return;
  }
  initSidebar();
  renderSidebar();
  renderHeader();
  await loadState();
  $('#input').focus();
})();
