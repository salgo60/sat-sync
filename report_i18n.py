"""Shared Swedish/English presentation helpers for the standalone OSM reports."""

import html


def text(sv: str, en: str, tag: str = "span") -> str:
    return (
        f'<{tag} data-sv="{html.escape(sv, quote=True)}"'
        f' data-en="{html.escape(en, quote=True)}">{html.escape(sv)}</{tag}>'
    )


def attribute(name: str, sv: str, en: str) -> str:
    return (
        f'{name}="{html.escape(sv, quote=True)}"'
        f' data-sv-{name}="{html.escape(sv, quote=True)}"'
        f' data-en-{name}="{html.escape(en, quote=True)}"'
    )


LANGUAGE_BUTTON = '<button type="button" id="lang-btn" lang="en">English</button>'
LANGUAGE_STYLE = """#lang-btn { background:#ffffff26; color:white; border:1px solid #ffffff80;
  border-radius:6px; padding:.45rem .8rem; cursor:pointer; font:inherit; margin-bottom:.7rem; }
#lang-btn:hover { background:#ffffff40; }
"""
LANGUAGE_SCRIPT = """
let lang = new URLSearchParams(window.location.search).get('lang') === 'en' ? 'en' : 'sv';
const t = (sv, en) => lang === 'en' ? en : sv;
function wikiLanguage(href) {
  const url = new URL(href);
  if (url.origin === 'https://wiki.openstreetmap.org') url.searchParams.set('uselang', lang);
  return url.href;
}
function initializeLanguage(renderLanguage) {
  function applyLanguage() {
    const details = new Map([...document.querySelectorAll('details[id]')].map(el => [el.id, el.open]));
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-sv][data-en]').forEach(el => {
      el.textContent = el.dataset[lang];
    });
    for (const attr of ['placeholder', 'alt', 'aria-label']) {
      document.querySelectorAll(`[data-sv-${attr}]`).forEach(el => {
        el.setAttribute(attr, el.getAttribute(`data-${lang}-${attr}`));
      });
    }
    document.querySelectorAll('a[data-lang-link]').forEach(el => {
      const url = new URL(el.getAttribute('href'), window.location.href);
      url.searchParams.set('lang', lang);
      el.href = url.href;
    });
    const button = document.getElementById('lang-btn');
    button.textContent = t('English', 'Svenska');
    button.lang = t('en', 'sv');
    renderLanguage();
    document.querySelectorAll('details[id]').forEach(el => {
      if (details.has(el.id)) el.open = details.get(el.id);
    });
  }
  document.getElementById('lang-btn').addEventListener('click', () => {
    lang = t('en', 'sv');
    const url = new URL(window.location.href);
    url.searchParams.set('lang', lang);
    window.history.replaceState({}, '', url.href);
    applyLanguage();
  });
  window.addEventListener('popstate', () => {
    lang = new URLSearchParams(window.location.search).get('lang') === 'en' ? 'en' : 'sv';
    applyLanguage();
  });
  applyLanguage();
}
"""
