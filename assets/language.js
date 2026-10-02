(() => {
  const select = document.querySelector('[data-language-select]');
  if (!select) return;
  const locales = ['en', 'zh-Hans', 'zh-Hant', 'ja', 'ko', 'de', 'fr', 'es'];
  const current = document.documentElement.lang || 'en';
  const explicitLocale = locales.includes(current) && current !== 'en' ? current : null;
  const stored = (() => { try { return localStorage.getItem('locus-language'); } catch { return null; } })();
  const save = value => { try { localStorage.setItem('locus-language', value); } catch {} };
  const systemLocale = () => {
    const language = (navigator.languages?.[0] || navigator.language || '').toLowerCase();
    const parts = language.split('-');
    if (parts[0] === 'zh') {
      if (parts.includes('hans')) return 'zh-Hans';
      if (parts.includes('hant')) return 'zh-Hant';
      return parts.some(part => ['tw', 'hk', 'mo'].includes(part)) ? 'zh-Hant' : 'zh-Hans';
    }
    return locales.includes(parts[0]) ? parts[0] : 'en';
  };
  const logicalPath = () => {
    const prefix = /^\/(zh-Hans|zh-Hant|ja|ko|de|fr|es)(?=\/|$)/;
    const path = location.pathname.replace(prefix, '');
    return path || '/';
  };
  const destination = locale => `${locale === 'en' ? '' : `/${locale}`}${logicalPath()}${location.search}${location.hash}`;
  const navigate = locale => {
    const target = destination(locale);
    if (target !== `${location.pathname}${location.search}${location.hash}`) location.assign(target);
  };

  if (explicitLocale) {
    select.value = stored === 'system' && systemLocale() === explicitLocale ? 'system' : explicitLocale;
  } else if (stored === 'en') {
    select.value = 'en';
  } else {
    select.value = 'system';
    const target = stored && locales.includes(stored) ? stored : systemLocale();
    if (target !== 'en') {
      if (!stored) save('system');
      navigate(target);
    }
  }
  select.addEventListener('change', () => {
    const value = select.value;
    save(value);
    navigate(value === 'system' ? systemLocale() : value);
  });
})();
