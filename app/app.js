(() => {
  const sourceDocs = [
    {
      id: '152fz', short: '152-ФЗ', title: 'Федеральный закон № 152-ФЗ «О персональных данных»',
      kind: 'Российская Федерация', mark: 'РФ', tone: 'ru',
      description: 'Федеральный закон Российской Федерации «О персональных данных».',
      href: 'https://mintrud.gov.ru/docs/laws/130', label: 'Открыть текст на сайте Минтруда',
      articles: ['ст. 6 · условия обработки', 'ст. 12 · трансграничная передача', 'ст. 18.1 · обязанности оператора'],
      searchTerms: ['152-фз', 'персональные данные', 'обработка персональных данных', 'условия обработки', 'трансграничная передача', 'оператор', 'согласие', 'россия']
    },
    {
      id: 'gdpr', short: 'GDPR', title: 'Регламент (ЕС) 2016/679 — General Data Protection Regulation',
      kind: 'Европейский союз', mark: 'EU', tone: 'eu',
      description: 'Текст регламента Европейского союза о защите персональных данных.',
      href: 'https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng', label: 'Открыть текст в EUR-Lex',
      articles: ['ст. 5 · принципы обработки', 'ст. 6 · законность обработки', 'ст. 28 · обработчик', 'ст. 44 · передача данных'],
      searchTerms: ['gdpr', 'персональные данные', 'принципы обработки', 'законность обработки', 'обработчик', 'поставщик', 'внешний api', 'трансграничная передача', 'третьи страны', 'европейский союз', 'ес', 'обучение модели']
    },
    {
      id: 'ai-act', short: 'AI Act', title: 'Регламент (ЕС) 2024/1689 — Artificial Intelligence Act',
      kind: 'Европейский союз', mark: 'AI', tone: 'ai',
      description: 'Текст регламента ЕС, устанавливающего гармонизированные правила в области ИИ.',
      href: 'https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng', label: 'Открыть текст в EUR-Lex',
      articles: ['ст. 4 · грамотность в области ИИ', 'ст. 14 · человеческий надзор', 'ст. 26 · обязанности развёртывающих лиц'],
      searchTerms: ['ai act', 'искусственный интеллект', 'ии', 'грамотность в области ии', 'человеческий надзор', 'развёртывающие лица', 'высокий риск', 'европейский союз', 'ес']
    }
  ];

  const scenarioData = [
    { number: '01', tag: 'Персональные данные', title: 'Данные в ИИ-сервисе', text: 'Документы и статьи о персональных данных при использовании внешнего ИИ-сервиса.', query: 'персональные данные ИИ-сервис' },
    { number: '02', tag: 'Поставщики', title: 'Внешний поставщик технологии', text: 'Материалы об обработчиках данных и подключении внешних API.', query: 'поставщик обработчик внешний API' },
    { number: '03', tag: 'Обучение модели', title: 'Данные для обучения', text: 'Статьи о принципах обработки данных и использовании моделей.', query: 'персональные данные обучение модели' },
    { number: '04', tag: 'Трансграничная передача', title: 'Передача между странами', text: 'Документы о трансграничной передаче персональных данных.', query: 'трансграничная передача данных' },
    { number: '05', tag: 'Контроль человека', title: 'Надзор за ИИ-системой', text: 'Статьи AI Act о грамотности, человеческом надзоре и обязанностях развёртывающих лиц.', query: 'человеческий надзор ИИ' },
    { number: '06', tag: 'Россия и ЕС', title: 'Несколько юрисдикций', text: 'Перейдите к нормативным актам России и Европейского союза.', query: 'персональные данные Россия ЕС ИИ' }
  ];

  const storageKey = 'pravo-ryadom:saved-v1';
  const view = document.getElementById('view');
  let page = 'overview';
  let activeFilter = 'all';
  let activeQuery = '';
  let toastTimer;
  let saved = readSaved();

  function readSaved() {
    try { const value = JSON.parse(localStorage.getItem(storageKey) || '[]'); return Array.isArray(value) ? value : []; }
    catch { return []; }
  }

  function iconSearch() { return '<svg class="search-icon" viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.7" cy="8.7" r="5.7"/><path d="m13 13 4 4"/></svg>'; }
  function searchForm(value = '', placeholder = 'Название документа, статья или тема') {
    return `<form class="search-form" data-search-form>${iconSearch()}<input type="search" name="q" value="${escapeAttr(value)}" aria-label="Поиск по нормативным документам" placeholder="${escapeAttr(placeholder)}" autocomplete="off"/><button class="search-submit" type="submit">Найти документы</button></form>`;
  }
  function escapeHtml(s) { return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
  function escapeAttr(s) { return escapeHtml(s); }
  function docFor(id) { return sourceDocs.find(d => d.id === id); }
  function isSaved(id) { return saved.includes(id); }
  function updateSavedCount() { const el = document.getElementById('saved-count'); if (el) el.textContent = saved.length; }
  function pluralize(number, forms) {
    const n = Math.abs(number) % 100;
    const last = n % 10;
    if (n > 10 && n < 20) return forms[2];
    if (last > 1 && last < 5) return forms[1];
    if (last === 1) return forms[0];
    return forms[2];
  }
  function notify(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('is-visible');
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => toast.classList.remove('is-visible'), 2200);
  }

  function navTo(next, options = {}) {
    page = next;
    activeFilter = 'all';
    document.querySelectorAll('[data-nav]').forEach(button => button.classList.toggle('is-active', button.dataset.nav === page));
    const labels = { overview: 'Обзор', scenarios: 'Сценарии', sources: 'Источники', compare: 'Сравнение', saved: 'Сохранённое', results: 'Результаты поиска' };
    document.getElementById('breadcrumb-current').textContent = labels[page] || 'Обзор';
    document.getElementById('sidebar').classList.remove('is-open');
    render();
    if (options.focusSearch) window.setTimeout(() => view.querySelector('input[name="q"]')?.focus(), 20);
    view.focus({ preventScroll: true });
  }

  function render() {
    updateSavedCount();
    if (page === 'overview') view.innerHTML = renderOverview();
    else if (page === 'scenarios') view.innerHTML = renderScenarios();
    else if (page === 'sources') view.innerHTML = renderSourcesPage();
    else if (page === 'compare') view.innerHTML = renderCompare();
    else if (page === 'saved') view.innerHTML = renderSaved();
    else if (page === 'results') view.innerHTML = renderResults();
    else { page = 'overview'; view.innerHTML = renderOverview(); }
  }

  function renderOverview() {
    const recent = sourceDocs.map(doc => `<div class="recent-item"><span class="doc-mini">${doc.mark}</span><span><strong>${doc.title}</strong><small>${doc.kind} · первоисточник</small></span><a href="${doc.href}" target="_blank" rel="noopener noreferrer" aria-label="Открыть ${escapeAttr(doc.short)}">↗</a></div>`).join('');
    return `
      <div class="welcome-row"><div><p class="eyebrow">Ваш правовой компас</p><h1>Регулирование ИИ и данных</h1><p class="welcome-subtitle">Навигация по нормативным документам и связанным статьям.</p></div></div>
      <section class="hero" aria-label="Начать поиск"><div class="hero-copy"><div class="hero-kicker"><span></span> ИИ · данные · регулирование</div><h2>Найдите нужные документы и статьи</h2><p>Ищите по названию акта, номеру статьи или теме.</p><button class="hero-cta" data-focus-search>Открыть поиск <span>↗</span></button></div><div class="hero-art" aria-hidden="true"><div class="orbit"></div><div class="orbit orbit-two"></div><i class="orbit-dot dot-one"></i><i class="orbit-dot dot-two"></i><div class="hero-core"><svg viewBox="0 0 110 112"><path d="M55 7 91 20v28c0 24-15 43-36 56C34 91 19 72 19 48V20L55 7Z"/><path d="M38 54h34M55 37v34M42 42l26 26M68 42 42 68"/><circle cx="55" cy="54" r="24" fill="none"/></svg><b>§</b></div></div></section>
      <div class="search-panel">${searchForm()}</div>
      <div class="quick-prompts"><span class="quick-label">Быстрый поиск</span><button class="prompt-chip" data-query="персональные данные">Персональные данные</button><button class="prompt-chip" data-query="трансграничная передача">Трансграничная передача</button><button class="prompt-chip" data-query="искусственный интеллект">Искусственный интеллект</button></div>
      <section class="section-head"><div><h2>Выберите направление</h2><p>Начните с темы, которая ближе к вашей задаче</p></div><button class="text-link" data-nav="scenarios">Все сценарии <span>→</span></button></section>
      <div class="overview-grid"><div class="topic-grid">
        <button class="topic-card" data-query="персональные данные"><span class="topic-top"><span class="topic-icon green">◉</span><span class="topic-arrow">↗</span></span><strong>Персональные данные</strong><p>152-ФЗ и GDPR</p></button>
        <button class="topic-card" data-query="трансграничная передача"><span class="topic-top"><span class="topic-icon violet">⇄</span><span class="topic-arrow">↗</span></span><strong>Передача данных</strong><p>Статьи о трансграничной передаче</p></button>
        <button class="topic-card" data-query="искусственный интеллект"><span class="topic-top"><span class="topic-icon amber">✳</span><span class="topic-arrow">↗</span></span><strong>Искусственный интеллект</strong><p>AI Act и выбранные статьи</p></button>
        <button class="topic-card" data-query="человеческий надзор"><span class="topic-top"><span class="topic-icon blue">⌖</span><span class="topic-arrow">↗</span></span><strong>Человеческий надзор</strong><p>Статья 14 AI Act</p></button>
      </div><aside class="overview-aside"><div class="aside-top"><span>путеводитель</span><span class="aside-icon">✳</span></div><h3>С чего начать</h3><p>Выберите направление и откройте связанные нормативные документы.</p><a class="aside-link" href="#scenarios" data-nav="scenarios">Смотреть сценарии <span>→</span></a></aside></div>
      <div class="bottom-row"><section class="recent-card"><div class="section-head"><div><h2>Нормативные документы</h2><p>Основные источники навигатора</p></div><button class="text-link" data-nav="sources">Каталог <span>→</span></button></div><div class="recent-list">${recent}</div></section><aside class="coverage-card"><div><h3>Три документа в навигаторе</h3><p>152-ФЗ, GDPR и AI Act</p></div><div class="coverage-marks"><span class="coverage-mark ru">РФ</span><span class="coverage-mark eu">EU</span><span class="coverage-mark ai">AI</span></div><button class="text-link" data-nav="compare" style="align-self:flex-start;margin-top:13px">Сравнить документы <span>→</span></button></aside></div>`;
  }

  function renderScenarios() {
    return `<div class="subpage-heading"><div><p class="eyebrow">Навигация по темам</p><h1>Сценарии использования</h1><p>Выберите направление и откройте связанные нормативные документы.</p></div><span class="subpage-count">${scenarioData.length} тем</span></div><div class="scenario-grid">${scenarioData.map(item => `<article class="scenario-card"><div class="scenario-card-top"><span class="scenario-number">ТЕМА ${item.number}</span><span class="scenario-tag">${item.tag}</span></div><h3>${item.title}</h3><p>${item.text}</p><button data-query="${escapeAttr(item.query)}">Открыть документы <span>↗</span></button></article>`).join('')}</div>`;
  }

  function sourceCard(doc) {
    return `<article class="source-card"><div class="source-symbol ${doc.tone}">${doc.mark}</div><div class="source-body"><div class="source-meta"><span class="source-type">${doc.kind}</span></div><h3>${doc.title}</h3><p>${doc.description}</p><div class="source-foot"><a href="${doc.href}" target="_blank" rel="noopener noreferrer">${doc.label} ↗</a></div><div class="article-tags">${doc.articles.map(article => `<span>${article}</span>`).join('')}</div></div><button class="bookmark-button ${isSaved(doc.id) ? 'is-saved' : ''}" data-save="${doc.id}" aria-label="${isSaved(doc.id) ? 'Убрать из сохранённого' : 'Сохранить'} ${escapeAttr(doc.short)}" title="${isSaved(doc.id) ? 'Убрать из сохранённого' : 'Сохранить'}">${isSaved(doc.id) ? '▣' : '♧'}</button></article>`;
  }

  function renderSourcesPage() {
    const filters = [['all', 'Все документы'], ['ru', '152-ФЗ'], ['eu', 'GDPR'], ['ai', 'AI Act']];
    const shown = activeFilter === 'all' ? sourceDocs : sourceDocs.filter(d => activeFilter === 'ru' ? d.id === '152fz' : activeFilter === 'eu' ? d.id === 'gdpr' : d.id === 'ai-act');
    return `<div class="subpage-heading"><div><p class="eyebrow">Нормативная база</p><h1>Источники</h1><p>Тексты документов и связанные статьи по выбранным направлениям.</p></div><span class="subpage-count">${sourceDocs.length} документа</span></div><div class="source-toolbar"><div class="filter-list">${filters.map(([id, label]) => `<button class="filter-button ${activeFilter === id ? 'is-active' : ''}" data-filter="${id}">${label}</button>`).join('')}</div></div><div class="source-list">${shown.map(doc => sourceCard(doc)).join('')}</div>`;
  }

  function renderCompare() {
    const rows = [
      ['Идентификатор', doc => doc.short],
      ['Юрисдикция', doc => doc.kind],
      ['Предмет', doc => doc.description],
      ['Статьи', doc => doc.articles.join('; ')]
    ];
    return `<div class="subpage-heading"><div><p class="eyebrow">Сопоставление</p><h1>Сравнение документов</h1><p>Основные сведения и выбранные статьи нормативных актов в одном месте.</p></div><span class="subpage-count">${sourceDocs.length} документа</span></div><div class="compare-table-wrap"><table class="compare-table"><thead><tr><th>Параметр</th>${sourceDocs.map(doc => `<th><span class="table-doc">${doc.short}</span><span class="table-label">${doc.kind}</span></th>`).join('')}</tr></thead><tbody>${rows.map(([label, value]) => `<tr><th>${label}</th>${sourceDocs.map(doc => `<td>${value(doc)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }

  function renderSaved() {
    const docs = sourceDocs.filter(doc => isSaved(doc.id));
    return `<div class="subpage-heading"><div><p class="eyebrow">Личная подборка</p><h1>Сохранённое</h1><p>Закладки хранятся локально в этом браузере.</p></div><span class="subpage-count">${docs.length} ${docs.length === 1 ? 'документ' : 'документа'}</span></div>${docs.length ? `<div class="source-list">${docs.map(doc => sourceCard(doc)).join('')}</div>` : `<div class="empty-state"><div class="empty-icon">♧</div><h3>Здесь пока пусто</h3><p>Сохраняйте источники, к которым хотите быстро вернуться.</p><button data-nav="sources">Перейти к источникам →</button></div>`}`;
  }

  function searchDocuments(query) {
    const normalized = query.toLocaleLowerCase('ru').replace(/ё/g, 'е');
    const queryTokens = normalized.match(/[a-zа-я0-9]+/g) || [];
    const ignored = new Set(['можно', 'ли', 'как', 'что', 'где', 'когда', 'какие', 'какой', 'это', 'для', 'при', 'про', 'или', 'the', 'and', 'for']);
    const terms = [...new Set(queryTokens.filter(token => !ignored.has(token) && token.length > 1))];
    if (!terms.length) return [];

    return sourceDocs.map(doc => {
      const corpus = `${doc.title} ${doc.description} ${doc.kind} ${doc.short} ${doc.articles.join(' ')} ${doc.searchTerms.join(' ')}`
        .toLocaleLowerCase('ru').replace(/ё/g, 'е');
      const corpusTokens = corpus.match(/[a-zа-я0-9]+/g) || [];
      let score = 0;
      for (const term of terms) {
        if (corpus.includes(term)) score += term.length > 4 ? 2 : 1;
        else if (term.length > 4 && corpusTokens.some(token => token.startsWith(term.slice(0, 5)) || term.startsWith(token.slice(0, 5)))) score += 1;
      }
      if (/(поставщик|обработчик|api|облач)/.test(normalized) && doc.id === 'gdpr') score += 2;
      if (/(трансгранич|передач|за рубеж)/.test(normalized) && ['152fz', 'gdpr'].includes(doc.id)) score += 2;
      return { doc, score };
    }).filter(item => item.score > 0).sort((a, b) => b.score - a.score).map(item => item.doc);
  }

  function renderResults() {
    const hits = searchDocuments(activeQuery);
    return `<div class="subpage-heading"><div><p class="eyebrow">Поиск по нормативным актам</p><h1>Результаты поиска</h1><p>Документы и связанные статьи по запросу.</p></div><span class="subpage-count">${hits.length} ${pluralize(hits.length, ['документ', 'документа', 'документов'])}</span></div><div class="search-panel" style="margin:0 0 15px;padding:10px">${searchForm(activeQuery, 'Название документа, статья или тема')}</div>${hits.length ? `<div class="source-list">${hits.map(doc => sourceCard(doc)).join('')}</div>` : `<div class="empty-state"><div class="empty-icon">⌕</div><h3>Документы не найдены</h3><p>Попробуйте название акта, номер статьи или другое тематическое слово.</p><button data-nav="sources">Открыть каталог документов →</button></div>`}`;
  }

  function submitQuery(query) {
    activeQuery = String(query || '').trim();
    if (!activeQuery) { notify('Введите вопрос или выберите пример.'); view.querySelector('input[name="q"]')?.focus(); return; }
    navTo('results');
  }

  function toggleSave(id) {
    if (saved.includes(id)) { saved = saved.filter(item => item !== id); notify('Убрано из сохранённого'); }
    else { saved = [...saved, id]; notify('Добавлено в сохранённое'); }
    try { localStorage.setItem(storageKey, JSON.stringify(saved)); } catch { notify('Браузер не разрешил сохранить закладку'); }
    render();
  }

  document.addEventListener('click', event => {
    const save = event.target.closest('[data-save]');
    if (save) { toggleSave(save.dataset.save); return; }
    const filter = event.target.closest('[data-filter]');
    if (filter) { activeFilter = filter.dataset.filter; render(); return; }
    const queryButton = event.target.closest('[data-query]');
    if (queryButton) { submitQuery(queryButton.dataset.query); return; }
    const nav = event.target.closest('[data-nav]');
    if (nav) { event.preventDefault(); navTo(nav.dataset.nav, { focusSearch: nav.hasAttribute('data-focus-search') }); return; }
    const focus = event.target.closest('[data-focus-search]');
    if (focus) { view.querySelector('input[name="q"]')?.focus(); }
  });

  document.addEventListener('submit', event => {
    const form = event.target.closest('[data-search-form]');
    if (!form) return;
    event.preventDefault();
    submitQuery(new FormData(form).get('q'));
  });

  document.getElementById('mobile-menu').addEventListener('click', () => document.getElementById('sidebar').classList.toggle('is-open'));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') document.getElementById('sidebar').classList.remove('is-open');
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); navTo('overview', { focusSearch: true }); }
  });

  render();
})();
