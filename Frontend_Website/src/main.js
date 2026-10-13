// Landing page behaviour: nav state, scroll reveal, waitlist forms.
import { joinWaitlist } from './lib/api.js';

// nav scroll state — switch to light backdrop after the hero is mostly scrolled past
const nav = document.getElementById('nav');
const heroEl = document.querySelector('.hero');
const onScroll = () => {
  const threshold = heroEl ? heroEl.offsetHeight - 80 : 8;
  nav.classList.toggle('scrolled', window.scrollY > threshold);
};
onScroll();
window.addEventListener('scroll', onScroll, { passive: true });

// reveal on scroll
const reveals = document.querySelectorAll('.reveal');
if ('IntersectionObserver' in window) {
  const io = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('in');
        io.unobserve(e.target);
      }
    });
  }, { threshold: 0.08, rootMargin: '0px 0px -60px 0px' });
  reveals.forEach(el => io.observe(el));
} else {
  reveals.forEach(el => el.classList.add('in'));
}

// Cloudflare Turnstile bot check — only when VITE_TURNSTILE_SITE_KEY is set at build time
const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY || '';
let turnstileLoader = null;

function loadTurnstile() {
  turnstileLoader ??= new Promise((resolve, reject) => {
    window.onVanikaTurnstileLoad = () => resolve(window.turnstile);
    const script = document.createElement('script');
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit&onload=onVanikaTurnstileLoad';
    script.async = true;
    script.onerror = reject;
    document.head.append(script);
  });
  return turnstileLoader;
}

function attachTurnstile(form) {
  const state = { token: '', widgetId: null, api: null };
  if (!TURNSTILE_SITE_KEY) return state;
  const slot = document.createElement('div');
  slot.className = 'turnstile-slot';
  form.querySelector('.waitlist-row').after(slot);
  loadTurnstile()
    .then((api) => {
      state.api = api;
      state.widgetId = api.render(slot, {
        sitekey: TURNSTILE_SITE_KEY,
        appearance: 'interaction-only', // invisible unless Cloudflare needs the visitor to click
        theme: 'dark',
        size: 'flexible',
        callback: (token) => { state.token = token; },
        'expired-callback': () => { state.token = ''; },
      });
    })
    .catch(() => console.error('[Vanika] Could not load the Turnstile bot check'));
  return state;
}

async function turnstileToken(state) {
  // The check usually finishes within a second of page load; wait briefly if not
  for (let i = 0; i < 20 && TURNSTILE_SITE_KEY && !state.token; i += 1) {
    await new Promise((r) => setTimeout(r, 250));
  }
  return state.token;
}

// waitlist forms
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function wireWaitlistForm(form) {
  const row = form.querySelector('.waitlist-row');
  const emailEl = form.querySelector('input[type="email"]');
  const hpEl = form.querySelector('.hp-input');
  const errorEl = form.querySelector('.waitlist-error');
  const submitBtn = form.querySelector('button[type="submit"]');
  const success = document.getElementById(form.dataset.success);
  const successTitle = success.querySelector('[data-success-title]');
  const successText = success.querySelector('[data-success-text]');
  const idleLabel = submitBtn.textContent;
  const bot = attachTurnstile(form);

  function showError(message, suggestion) {
    errorEl.replaceChildren(message);
    if (suggestion) {
      // One click to accept "Did you mean …?"
      const fix = document.createElement('button');
      fix.type = 'button';
      fix.className = 'suggestion';
      fix.textContent = `Use ${suggestion}`;
      fix.addEventListener('click', () => {
        emailEl.value = suggestion;
        clearError();
        form.requestSubmit();
      });
      // …or keep what they typed (real domains can look like typos, e.g. cloud.com)
      const keep = document.createElement('button');
      keep.type = 'button';
      keep.className = 'suggestion';
      keep.textContent = 'Keep my address';
      keep.addEventListener('click', () => {
        form.dataset.keepEmail = '1';
        clearError();
        form.requestSubmit();
      });
      errorEl.append(' ', fix, ' · ', keep);
    }
    errorEl.classList.add('show');
    row.classList.add('invalid');
    emailEl.setAttribute('aria-invalid', 'true');
  }

  function clearError() {
    errorEl.classList.remove('show');
    row.classList.remove('invalid');
    emailEl.removeAttribute('aria-invalid');
  }

  function showSuccess(alreadySubscribed) {
    if (alreadySubscribed) {
      successTitle.textContent = "You're already on the list.";
      successText.textContent = "No need to sign up twice — we'll email you when early access opens.";
    }
    form.hidden = true;
    success.classList.add('show');
    success.focus();
  }

  emailEl.addEventListener('input', clearError);

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearError();

    const email = emailEl.value.trim();
    const keepEmail = form.dataset.keepEmail === '1';
    delete form.dataset.keepEmail;
    if (!EMAIL_PATTERN.test(email)) {
      showError('Please enter a valid email address, like you@company.com.');
      emailEl.focus();
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Joining…';

    const result = await joinWaitlist({
      email,
      source: form.dataset.source,
      honeypot: hpEl ? hpEl.value : '',
      turnstileToken: await turnstileToken(bot),
      keepEmail,
    });

    submitBtn.disabled = false;
    submitBtn.textContent = idleLabel;
    // Turnstile tokens are single-use
    if (bot.api && bot.widgetId !== null) {
      bot.token = '';
      bot.api.reset(bot.widgetId);
    }

    if (result.ok) {
      form.reset();
      showSuccess(result.alreadySubscribed);
    } else {
      showError(result.message, result.suggestion);
      emailEl.focus();
    }
  });
}

document.querySelectorAll('form.waitlist').forEach(wireWaitlistForm);
