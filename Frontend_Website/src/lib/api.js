// Client for the Vanika mail backend (FastAPI, Backend_Website/).
//
// Configure with VITE_API_BASE_URL (e.g. https://mailsbackend.azurewebsites.net).
// The older VITE_MAIL_BACKEND_URL (full .../vanika/subscribe URL) still works.
const env = import.meta.env;

function resolveApiBase() {
  if (env.VITE_API_BASE_URL) return env.VITE_API_BASE_URL.replace(/\/+$/, '');
  if (env.VITE_MAIL_BACKEND_URL) {
    return env.VITE_MAIL_BACKEND_URL.replace(/\/vanika\/subscribe\/?$/, '').replace(/\/+$/, '');
  }
  if (env.DEV) return 'http://127.0.0.1:8000';
  console.error('[Vanika] VITE_API_BASE_URL is not set at build time — forms cannot reach the backend.');
  return '';
}

export const API_BASE = resolveApiBase();
const ACCESS_KEY = env.VITE_MAIL_ACCESS_KEY || '';

const MESSAGES = {
  INVALID_EMAIL: 'Please enter a valid email address.',
  RATE_LIMITED: 'Too many attempts. Please wait a minute and try again.',
  BOT_CHECK_FAILED: "We couldn't verify you're human. Please refresh the page and try again.",
  NETWORK: "We couldn't reach our server. Check your connection and try again.",
  UNKNOWN: 'Something went wrong on our side. Please try again in a moment.',
};

// Email-policy rejections: the server's message is written for visitors, show it as-is
const POLICY_CODES = new Set([
  'INVALID_EMAIL', 'EMAIL_TYPO', 'DISPOSABLE_EMAIL', 'ROLE_EMAIL',
  'UNDELIVERABLE_DOMAIN', 'PERSONAL_EMAIL_NOT_ALLOWED',
]);

function marketingParams() {
  const params = new URLSearchParams(window.location.search);
  const out = {};
  for (const key of ['utm_source', 'utm_medium', 'utm_campaign']) {
    const value = params.get(key);
    if (value) out[key] = value;
  }
  // Only record where visitors came from when it's another site
  if (document.referrer && !document.referrer.startsWith(window.location.origin)) {
    out.referrer = document.referrer;
  }
  return out;
}

/**
 * Add an email to the waitlist.
 * Resolves to { ok: true, alreadySubscribed } or { ok: false, message, suggestion? }.
 */
export async function joinWaitlist({ email, source, honeypot = '', turnstileToken = '', keepEmail = false }) {
  const body = new URLSearchParams({
    clientemail: email,
    accesskey: ACCESS_KEY,
    source,
    website: honeypot,
    ...marketingParams(),
  });
  if (turnstileToken) body.set('cf-turnstile-response', turnstileToken);
  // The visitor saw the "did you mean" hint and chose to keep their address
  if (keepEmail) body.set('keep_email', '1');

  let response;
  try {
    response = await fetch(`${API_BASE}/vanika/subscribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });
  } catch {
    return { ok: false, message: MESSAGES.NETWORK };
  }

  const data = await response.json().catch(() => ({}));
  if (response.ok && String(data.status).toLowerCase() === 'success') {
    return { ok: true, alreadySubscribed: Boolean(data.alreadySubscribed) };
  }
  if (POLICY_CODES.has(data.code) && data.message) {
    return { ok: false, message: data.message, suggestion: data.suggestion };
  }
  return { ok: false, message: MESSAGES[data.code] || MESSAGES.UNKNOWN };
}

/** Error with the HTTP status, thrown by adminRequest. */
export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `HTTP ${status}`);
    this.status = status;
  }
}

/** Authenticated call to the /vanika/admin API. Returns parsed JSON or a Response for files. */
export async function adminRequest(path, adminKey, { method = 'GET', raw = false } = {}) {
  const response = await fetch(`${API_BASE}/vanika/admin${path}`, {
    method,
    headers: { 'X-Admin-Key': adminKey, Accept: raw ? '*/*' : 'application/json' },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(response.status, typeof data.detail === 'string' ? data.detail : undefined);
  }
  return raw ? response : response.json();
}
