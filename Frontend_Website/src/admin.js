// Waitlist admin dashboard: reads /vanika/admin/* with the X-Admin-Key header.
import { API_BASE, ApiError, adminRequest } from './lib/api.js';

const KEY_STORAGE = 'vanika_admin_key';
const PAGE_SIZE = 50;
const TYPE_LABELS = { work: 'Work', education: 'School / university', personal: 'Personal' };
const SOURCE_LABELS = {
  hero: 'Hero form (top of page)',
  final_cta: 'Request access form (bottom)',
  unknown: 'Unknown / before tracking',
};

const $ = (id) => document.getElementById(id);
const state = { key: '', offset: 0, search: '', total: 0 };

// ─── session key (sessionStorage can be unavailable; the page still works) ───
function loadKey() {
  try { return sessionStorage.getItem(KEY_STORAGE) || ''; } catch { return ''; }
}
function saveKey(key) {
  try { key ? sessionStorage.setItem(KEY_STORAGE, key) : sessionStorage.removeItem(KEY_STORAGE); } catch { /* ignore */ }
}

// ─── helpers ───
const numberFmt = new Intl.NumberFormat();
const dateFmt = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
const dateTimeFmt = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' });
const shortDayFmt = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', timeZone: 'UTC' });

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(props).forEach(([k, v]) => {
    if (k === 'class') node.className = v;
    else if (k === 'text') node.textContent = v;
    else if (k === 'style') Object.assign(node.style, v);
    else node.setAttribute(k, v);
  });
  children.forEach((c) => node.append(c));
  return node;
}

function relativeTime(iso) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} d ago`;
  return dateFmt.format(new Date(iso));
}

function sourceLabel(source) {
  return SOURCE_LABELS[source] || source;
}

function niceMax(value) {
  if (value <= 4) return 4;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 5, 10].find((s) => s * magnitude * 4 >= value) * magnitude;
  return step * 4;
}

// ─── views ───
function showLogin(message = '') {
  $('dashboardView').hidden = true;
  $('toolbar').hidden = true;
  $('loginView').hidden = false;
  $('loginError').textContent = message;
  $('adminKey').value = '';
  $('adminKey').focus();
}

function showDashboard() {
  $('loginView').hidden = true;
  $('dashboardView').hidden = false;
  $('toolbar').hidden = false;
}

function showBanner(message) {
  $('banner').textContent = message;
  $('banner').hidden = !message;
}

function describeError(err) {
  if (!(err instanceof ApiError)) {
    return `Can't reach the backend at ${API_BASE || '(VITE_API_BASE_URL not set)'}. Check that it is running and that this site's origin is in CORS_ORIGINS.`;
  }
  if (err.status === 503 && err.message.startsWith('STORAGE_UNAVAILABLE')) {
    const reason = err.message.split(':').slice(1).join(':').trim();
    return `Sign-ups are only being emailed, not stored (${reason || 'storage not configured'}). See docs/DEPLOYMENT.md.`;
  }
  if (err.status === 503 && err.message.startsWith('ADMIN_DISABLED')) {
    return 'The admin API is disabled. Set VANIKA_ADMIN_KEY on the backend.';
  }
  if (err.status === 503) return 'The database is unreachable right now. Try again in a minute.';
  return `Request failed (${err.status}). ${err.message}`;
}

// Auth failures send the admin back to the sign-in screen; anything else is shown in place.
function handleError(err) {
  if (err instanceof ApiError && err.status === 401) {
    saveKey('');
    state.key = '';
    showLogin("That key didn't work. Check VANIKA_ADMIN_KEY and try again.");
    return true;
  }
  if (err instanceof ApiError && err.status === 429) {
    saveKey('');
    state.key = '';
    showLogin('Too many wrong attempts. Wait 5 minutes and try again.');
    return true;
  }
  if (err instanceof ApiError && err.status === 503 && err.message.startsWith('ADMIN_DISABLED')) {
    showLogin(describeError(err));
    return true;
  }
  showBanner(describeError(err));
  return false;
}

// ─── stats ───
function renderTiles(stats) {
  $('statTotal').textContent = numberFmt.format(stats.total);
  $('statToday').textContent = numberFmt.format(stats.today);
  $('stat7').textContent = numberFmt.format(stats.last7Days);
  $('stat30').textContent = numberFmt.format(stats.last30Days);
}

function renderChart(daily) {
  const chart = $('dailyChart');
  chart.replaceChildren();
  const max = niceMax(Math.max(0, ...daily.map((d) => d.count)));
  const ticks = [0, max / 4, max / 2, (3 * max) / 4, max];

  const yAxis = el('div', { class: 'chart-y', 'aria-hidden': 'true' });
  const plot = el('div', { class: 'chart-plot' });
  ticks.forEach((t) => {
    const pct = `${(t / max) * 100}%`;
    yAxis.append(el('span', { text: numberFmt.format(t), style: { bottom: pct } }));
    if (t > 0) plot.append(el('div', { class: 'chart-grid', style: { bottom: pct } }));
  });

  const cols = el('div', { class: 'chart-cols' });
  const tip = $('chartTip');
  daily.forEach((d) => {
    const label = `${shortDayFmt.format(new Date(`${d.date}T00:00:00Z`))}: ${d.count} sign-up${d.count === 1 ? '' : 's'}`;
    const col = el('div', { class: 'chart-col', tabindex: '0', 'aria-label': label });
    if (d.count > 0) {
      col.append(el('div', { class: 'chart-bar', style: { height: `${(d.count / max) * 100}%` } }));
    }
    const show = () => {
      const rect = col.getBoundingClientRect();
      tip.replaceChildren(
        el('strong', { text: `${d.count}` }),
        ` sign-up${d.count === 1 ? '' : 's'} · ${shortDayFmt.format(new Date(`${d.date}T00:00:00Z`))}`,
      );
      tip.style.left = `${rect.left + rect.width / 2}px`;
      tip.style.top = `${rect.top + rect.height - (rect.height * d.count) / max}px`;
      tip.hidden = false;
    };
    const hide = () => { tip.hidden = true; };
    col.addEventListener('mouseenter', show);
    col.addEventListener('focus', show);
    col.addEventListener('mouseleave', hide);
    col.addEventListener('blur', hide);
    cols.append(col);
  });
  plot.append(cols);

  const xAxis = el('div', { class: 'chart-x', 'aria-hidden': 'true' });
  [0, 7, 14, 21, 29].forEach((i) => {
    const d = daily[i];
    if (!d) return;
    const left = `${((i + 0.5) / daily.length) * 100}%`;
    xAxis.append(el('span', { text: shortDayFmt.format(new Date(`${d.date}T00:00:00Z`)), style: { left } }));
  });

  chart.append(yAxis, plot, xAxis);

  // Accessible table view of the same data
  const tbody = $('dailyTable').querySelector('tbody');
  tbody.replaceChildren(...daily.map((d) => el('tr', {}, [el('td', { text: d.date }), el('td', { text: String(d.count) })])));
}

function renderBreakdown(listId, counts, total, labelFor) {
  const list = $(listId);
  const entries = Object.entries(counts || {}).sort((a, b) => b[1] - a[1]);
  if (!entries.length) {
    list.replaceChildren(el('li', { class: 'muted small', text: 'No sign-ups yet.' }));
    return;
  }
  list.replaceChildren(...entries.map(([source, count]) => {
    const pct = total ? Math.round((count / total) * 100) : 0;
    return el('li', { class: 'source-row' }, [
      el('div', { class: 'source-meta' }, [
        el('span', { text: labelFor(source) }),
        el('span', { class: 'count', text: `${numberFmt.format(count)} · ${pct}%` }),
      ]),
      el('div', { class: 'source-track', 'aria-hidden': 'true' }, [
        el('div', { class: 'source-fill', style: { width: `${pct}%` } }),
      ]),
    ]);
  }));
}

async function loadStats() {
  const stats = await adminRequest('/stats', state.key);
  renderTiles(stats);
  renderChart(stats.daily);
  renderBreakdown('sourceList', stats.bySource, stats.total, sourceLabel);
  renderBreakdown('typeList', stats.byType, stats.total, (t) => TYPE_LABELS[t] || t);
}

// ─── subscriber list ───
function mailStatus(status = {}, error = '') {
  const part = (label, value) => {
    const map = { sent: ['ok', '✓'], failed: ['fail', '✕'], pending: ['wait', '…'] };
    const [cls, icon] = map[value] || ['wait', '–'];
    const reason = value === 'failed' && error ? ` — ${error}` : '';
    return el('span', { class: cls, title: `${label}: ${value || 'unknown'}${reason}`, text: `${icon} ${label}` });
  };
  return el('span', { class: 'mail-status' }, [part('Team', status.admin), ' · ', part('Welcome', status.user)]);
}

function renderRows(items) {
  $('subsBody').replaceChildren(...items.map((s) => {
    const del = el('button', { type: 'button', class: 'btn btn-danger', text: 'Remove', 'aria-label': `Remove ${s.email}` });
    del.addEventListener('click', () => removeSubscriber(s.email));
    const sources = (s.sources && s.sources.length ? s.sources : [s.firstSource || 'unknown'])
      .map((src) => el('span', { class: 'chip', title: sourceLabel(src), text: src }));
    return el('tr', {}, [
      el('td', { class: 'email', text: s.email }),
      el('td', {}, [el('span', { class: 'chip', text: TYPE_LABELS[s.emailType] || s.emailType || '–' })]),
      el('td', { class: 'when', title: s.createdAt ? dateTimeFmt.format(new Date(s.createdAt)) : '', text: s.createdAt ? relativeTime(s.createdAt) : '–' }),
      el('td', {}, sources),
      el('td', { class: 'num', text: String(s.signupCount || 1) }),
      el('td', {}, [mailStatus(s.emailStatus, s.emailError)]),
      el('td', { class: 'num' }, [del]),
    ]);
  }));
}

async function loadSubscribers() {
  const params = new URLSearchParams({ limit: PAGE_SIZE, offset: state.offset });
  if (state.search) params.set('search', state.search);
  const page = await adminRequest(`/subscribers?${params}`, state.key);
  state.total = page.total;
  renderRows(page.items);

  const empty = $('emptyState');
  empty.hidden = page.items.length > 0;
  empty.textContent = state.search
    ? `No subscribers match “${state.search}”.`
    : 'No one has joined yet. Sign-ups from vanika.ai will appear here.';

  const from = page.total ? state.offset + 1 : 0;
  const to = Math.min(state.offset + PAGE_SIZE, page.total);
  $('pageInfo').textContent = `Showing ${from}–${to} of ${numberFmt.format(page.total)}`;
  $('prevBtn').disabled = state.offset === 0;
  $('nextBtn').disabled = state.offset + PAGE_SIZE >= page.total;
}

async function refresh() {
  $('refreshBtn').disabled = true;
  try {
    await Promise.all([loadStats(), loadSubscribers()]);
    showBanner('');
    $('updatedAt').textContent = `Updated ${new Intl.DateTimeFormat(undefined, { timeStyle: 'short' }).format(new Date())}`;
    return true;
  } catch (err) {
    handleError(err);
    return false;
  } finally {
    $('refreshBtn').disabled = false;
  }
}

async function removeSubscriber(email) {
  const ok = window.confirm(`Remove ${email} from the waitlist?\n\nThis permanently deletes their record and cannot be undone. Export a CSV first if you need a copy.`);
  if (!ok) return;
  try {
    await adminRequest(`/subscribers/${encodeURIComponent(email)}`, state.key, { method: 'DELETE' });
    if (state.offset >= state.total - 1 && state.offset > 0) state.offset -= PAGE_SIZE;
    await refresh();
  } catch (err) {
    handleError(err);
  }
}

async function exportCsv() {
  const btn = $('exportBtn');
  btn.disabled = true;
  btn.textContent = 'Exporting…';
  try {
    const response = await adminRequest('/subscribers/export.csv', state.key, { raw: true });
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = el('a', { href: url, download: `vanika-waitlist-${new Date().toISOString().slice(0, 10)}.csv` });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (err) {
    handleError(err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Export CSV';
  }
}

// ─── wiring ───
$('loginForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const key = $('adminKey').value.trim();
  if (!key) return;
  const btn = $('loginBtn');
  btn.disabled = true;
  btn.textContent = 'Checking…';
  state.key = key;
  state.offset = 0;
  try {
    await adminRequest('/stats', key);
    saveKey(key);
    showDashboard();
    await refresh();
  } catch (err) {
    if (!handleError(err)) showLogin(describeError(err));
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sign in';
  }
});

$('refreshBtn').addEventListener('click', refresh);
$('exportBtn').addEventListener('click', exportCsv);
$('signOutBtn').addEventListener('click', () => {
  saveKey('');
  state.key = '';
  showLogin();
});
$('prevBtn').addEventListener('click', () => {
  state.offset = Math.max(0, state.offset - PAGE_SIZE);
  loadSubscribers().catch(handleError);
});
$('nextBtn').addEventListener('click', () => {
  state.offset += PAGE_SIZE;
  loadSubscribers().catch(handleError);
});

let searchTimer;
$('searchInput').addEventListener('input', (e) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.search = e.target.value.trim();
    state.offset = 0;
    loadSubscribers().catch(handleError);
  }, 250);
});

// Resume a session from this tab
state.key = loadKey();
if (state.key) {
  showDashboard();
  refresh();
} else {
  showLogin();
}
