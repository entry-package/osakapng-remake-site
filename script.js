/* Progressive enhancement: every article and profile is available without JS. */
(() => {
  'use strict';
  const toggle = document.querySelector('.menu-toggle');
  const nav = document.querySelector('#site-nav');
  const closeMenu = () => {
    nav?.classList.remove('open');
    toggle?.setAttribute('aria-expanded', 'false');
    toggle?.setAttribute('aria-label', 'メニューを開く');
  };
  toggle?.addEventListener('click', () => {
    const open = toggle.getAttribute('aria-expanded') !== 'true';
    nav.classList.toggle('open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'メニューを閉じる' : 'メニューを開く');
  });
  nav?.addEventListener('click', event => { if (event.target.closest('a')) closeMenu(); });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && nav?.classList.contains('open')) { closeMenu(); toggle.focus(); }
  });
  document.addEventListener('click', event => { if (!event.target.closest('.site-header')) closeMenu(); });
  matchMedia('(min-width:721px)').addEventListener('change', closeMenu);

  const search = document.querySelector('#news-search');
  const year = document.querySelector('#news-year');
  if (search && year) {
    const params = new URLSearchParams(location.search);
    search.value = params.get('q') || '';
    if ([...year.options].some(o => o.value === params.get('year'))) year.value = params.get('year');
    const normalize = value => value.normalize('NFKC').toLocaleLowerCase('ja').trim();
    const filter = () => {
      const terms = normalize(search.value).split(/\s+/).filter(Boolean);
      let count = 0;
      document.querySelectorAll('[data-news]').forEach(card => {
        const match = (!year.value || card.dataset.year === year.value) && terms.every(term => normalize(card.dataset.search).includes(term));
        card.hidden = !match;
        if (match) count++;
      });
      document.querySelector('#news-count').textContent = count;
      document.querySelector('#empty-results').hidden = count !== 0;
      const query = new URLSearchParams();
      if (search.value.trim()) query.set('q', search.value.trim());
      if (year.value) query.set('year', year.value);
      history.replaceState(null, '', location.pathname + (query.size ? '?' + query.toString() : ''));
    };
    search.addEventListener('input', filter);
    year.addEventListener('change', filter);
    search.form.addEventListener('submit', event => { event.preventDefault(); filter(); });
    search.form.addEventListener('reset', () => setTimeout(filter, 0));
    filter();
  }
  const form = document.querySelector('#contact-form');
  if (form) {
    const status = form.querySelector('[role="status"]');
    const compose = () => {
      const data = new FormData(form);
      return { subject: '【OsakaPNG】' + data.get('topic'), body: 'ご相談の種類：' + data.get('topic') + '\nお名前：' + data.get('name') + '\nメールアドレス：' + data.get('email') + '\n\nお問い合わせ内容：\n' + data.get('message') };
    };
    form.addEventListener('submit', event => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const {subject, body} = compose();
      location.href = 'mailto:info@package-inc.com?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(body);
      status.textContent = 'メールアプリで内容を確認し、送信してください。開かない場合は「本文をコピー」をご利用ください。この画面では送信完了は確認できません。';
    });
    document.querySelector('#copy-message').addEventListener('click', async () => {
      if (!form.reportValidity()) return;
      const {subject, body} = compose();
      try {
        await navigator.clipboard.writeText('宛先：info@package-inc.com\n件名：' + subject + '\n\n' + body);
        status.textContent = '宛先・件名・本文をコピーしました。普段のメールサービスに貼り付けて送信してください。';
      } catch {
        status.textContent = 'コピーできませんでした。入力内容を選択してコピーし、info@package-inc.com へお送りください。';
      }
    });
  }
})();
