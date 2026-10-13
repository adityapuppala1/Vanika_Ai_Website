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

  function showError(message) {
    errorEl.textContent = message;
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
    });

    submitBtn.disabled = false;
    submitBtn.textContent = idleLabel;

    if (result.ok) {
      form.reset();
      showSuccess(result.alreadySubscribed);
    } else {
      showError(result.message);
    }
  });
}

document.querySelectorAll('form.waitlist').forEach(wireWaitlistForm);
