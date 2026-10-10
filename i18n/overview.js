/* No network requests, tracking, browser-language redirects, or stored form data. */
(() => {
  'use strict';
  const form = document.querySelector('.intl-mail');
  if (!form) return;
  form.addEventListener('submit', event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const values = new FormData(form);
    const name = String(values.get('name') || '').trim();
    const email = String(values.get('email') || '').trim();
    const message = String(values.get('message') || '').trim();
    if (!name || !email || !message) return;
    const body = `${name}\n${email}\n\n${message}`;
    const url = `mailto:${form.dataset.email}?subject=${encodeURIComponent(form.dataset.subject)}&body=${encodeURIComponent(body)}`;
    const status = form.querySelector('[data-mail-status]');
    status.textContent = status.dataset.ready;
    window.location.href = url;
  });
})();
