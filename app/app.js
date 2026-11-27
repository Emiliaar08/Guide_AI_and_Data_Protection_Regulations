(() => {
  'use strict';
  const { documents, articles, scenarios } = window.NavigatorData;
  const api = window.NavigatorApi;
  const view = document.getElementById('view');
  const dialog = document.getElementById('auth-dialog');
  const pending = new Map();
  let user = null;
  let state;
  let sessionEpoch = 0;
  let sessionChecking = true;
  let transitionBusy = false;
  let workspaceReady = true;
  let guestImport = [];
  let guestSelection = null;
  let authIntent = null;
  let writeQueue = Promise.resolve();
  let notice = null;
  const failedWrites = new Map();
  const latestWrites = new Map();
  const favoriteOperations = new Set();
  const deletingChats = new Set();
  const chatRevisions = new Map();
  let page = ['chat', 'sources', 'compare', 'saved'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'chat';
  let sourceFilter = 'all';
  let savedTab = 'answers';
  let authBusy = false;
  let toastTimer;
  let lastRender = null;
  let menuAnimation = null;
  let authCloseAnimation = null;
  let authLayoutAnimation = null;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const citationAnimations = new WeakMap();
  const pageScrollPositions = new Map();

  const id = () => window.crypto?.randomUUID?.() || `id-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
  const docFor = documentId => documents.find(item => item.id === documentId);
  const activeChat = () => state.chats.find(item => item.id === state.activeChatId);
  const storageKey = () => `pravo-ryadom:preferences-v1:${encodeURIComponent(user.id)}`;
  const shortDate = date => new Intl.DateTimeFormat('ru', { day: 'numeric', month: 'short' }).format(new Date(date));
  const time = date => new Intl.DateTimeFormat('ru', { hour: '2-digit', minute: '2-digit' }).format(new Date(date));
  const icon = name => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
  const plural = (n, forms) => forms[n % 100 > 10 && n % 100 < 20 ? 2 : n % 10 === 1 ? 0 : n % 10 > 1 && n % 10 < 5 ? 1 : 2];
  const emptyState = () => ({ chats: [], favoriteArticles: [], favoriteAnswers: [], activeChatId: null });
  state = emptyState();

  function readPreferences() {
    if (!user) return {};
    try {
      const value = JSON.parse(localStorage.getItem(storageKey()) || '{}');
      return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
    } catch { return {}; }
  }
  function persist() {
    if (!user || !workspaceReady) return;
    const drafts = {};
    for (const chat of state.chats) {
      if (chat.draft) drafts[chat.id] = { text: chat.draft, jurisdiction: chat.jurisdiction || '', createdAt: chat.createdAt };
    }
    try { localStorage.setItem(storageKey(), JSON.stringify({ activeChatId: state.activeChatId, drafts })); }
    catch { notify('Не удалось сохранить черновик в браузере.'); }
  }
  function showNotice(text, action = 'retry') {
    notice = text ? { text, action } : null;
    renderStatus();
  }
  function renderStatus() {
    const element = document.getElementById('workspace-status');
    element.hidden = !notice;
    element.innerHTML = notice ? `<span>${escape(notice.text)}</span>${notice.action === 'retry' ? '<button class="text-button" data-retry-sync>Повторить</button>' : notice.action === 'login' ? '<button class="text-button" data-auth="login">Войти</button>' : ''}` : '';
  }
  function cancelAnswers() {
    for (const controller of pending.values()) controller.abort();
    pending.clear();
    for (const chat of state.chats) for (const message of chat.messages) {
      if (message.status === 'pending') message.status = 'interrupted';
    }
  }
  function serializeChat(chat) {
    return JSON.parse(JSON.stringify({ id: chat.id, title: chat.title, jurisdiction: chat.jurisdiction || '', createdAt: chat.createdAt, updatedAt: chat.updatedAt, messages: chat.messages }));
  }
  function sessionExpired() {
    cancelAnswers();
    sessionEpoch++;
    user = null;
    transitionBusy = false;
    workspaceReady = true;
    failedWrites.clear();
    latestWrites.clear();
    favoriteOperations.clear();
    const recovered = guestImport;
    state = emptyState();
    state.chats = recovered;
    state.activeChatId = recovered.some(chat => chat.id === guestSelection) ? guestSelection : recovered[0]?.id || null;
    guestImport = [];
    guestSelection = null;
    authIntent = null;
    showNotice('Сессия закончилась. Войдите ещё раз, чтобы открыть свои чаты и избранное.', 'login');
    render();
  }
  function storageError(error, epoch) {
    if (epoch !== sessionEpoch) return;
    if (error.status === 401) { sessionExpired(); return; }
    showNotice(error.status === 503
      ? 'Хранилище временно недоступно. Изменения ещё не сохранены.'
      : error.status === 422 ? 'Сервер не принял изменения. Проверьте ограничения чата и повторите сохранение.'
      : 'Не удалось сохранить или загрузить данные. Проверьте соединение и повторите.');
  }
  function queueWrite(key, run, apply = () => {}) {
    const epoch = sessionEpoch;
    const owner = user?.id;
    if (!owner) return Promise.resolve(false);
    const job = { key, run, apply };
    latestWrites.set(key, job);
    const task = async () => {
      try {
        if (epoch !== sessionEpoch || user?.id !== owner || latestWrites.get(key) !== job) return false;
        const response = await run();
        if (epoch !== sessionEpoch || user?.id !== owner || latestWrites.get(key) !== job) return false;
        failedWrites.delete(key);
        apply(response);
        if (!failedWrites.size && workspaceReady) showNotice(null);
        return true;
      } catch (error) {
        if (epoch === sessionEpoch && latestWrites.get(key) === job) {
          if (error.status !== 401) failedWrites.set(key, job);
          storageError(error, epoch);
        }
        return false;
      }
    };
    writeQueue = writeQueue.catch(() => {}).then(task);
    return writeQueue;
  }
  function saveChatToServer(chat) {
    if (!user || !workspaceReady || deletingChats.has(chat.id)) return;
    const revision = (chatRevisions.get(chat.id) || 0) + 1;
    chatRevisions.set(chat.id, revision);
    const snapshot = serializeChat(chat);
    void queueWrite('chat:' + chat.id, () => api.putChat(snapshot), saved => {
      if (!state.chats.includes(chat) || chatRevisions.get(chat.id) !== revision || pending.has(chat.id)) return;
      const draft = chat.draft || '';
      const jurisdiction = chat.jurisdiction;
      Object.assign(chat, saved, { draft, jurisdiction });
      render();
    });
  }
  function applyWorkspace(data) {
    if (!data || !Array.isArray(data.chats) || !Array.isArray(data.favoriteArticles) || !Array.isArray(data.favoriteAnswers)) throw Object.assign(new Error('Invalid workspace'), { code: 'format' });
    const preferences = readPreferences();
    const drafts = preferences.drafts && typeof preferences.drafts === 'object' && !Array.isArray(preferences.drafts) ? preferences.drafts : {};
    for (const chat of guestImport) {
      if (chat.draft) drafts[chat.id] = { text: chat.draft, jurisdiction: chat.jurisdiction, createdAt: chat.createdAt };
    }
    const chats = data.chats.map(chat => ({ ...chat, jurisdiction: drafts[chat.id]?.jurisdiction ?? chat.jurisdiction, draft: typeof drafts[chat.id]?.text === 'string' ? drafts[chat.id].text : '' }));
    for (const [key, draft] of Object.entries(drafts)) {
      if (draft && /^[A-Za-z0-9_-]{1,64}$/.test(key) && typeof draft.text === 'string' && draft.text && !chats.some(chat => chat.id === key)) chats.push({ ...makeChat(), id: key, createdAt: draft.createdAt || new Date().toISOString(), jurisdiction: draft.jurisdiction || '', draft: draft.text });
    }
    const selection = guestSelection || state.activeChatId || preferences.activeChatId;
    state = { chats, favoriteArticles: data.favoriteArticles, favoriteAnswers: data.favoriteAnswers, activeChatId: chats.some(chat => chat.id === selection) ? selection : chats[0]?.id || null };
  }
  async function loadAccountWorkspace() {
    const epoch = sessionEpoch;
    if (!user || transitionBusy) return false;
    transitionBusy = true;
    workspaceReady = false;
    showNotice(guestImport.length ? 'Переносим ваши гостевые чаты…' : 'Загружаем ваши чаты…', null);
    render();
    try {
      for (const chat of guestImport) {
        await api.putChat(serializeChat(chat));
        if (epoch !== sessionEpoch) return false;
      }
      const data = await api.workspace();
      if (epoch !== sessionEpoch) return false;
      applyWorkspace(data);
      guestImport = [];
      guestSelection = null;
      workspaceReady = true;
      showNotice(null);
      persist();
      return true;
    } catch (error) { storageError(error, epoch); return false; }
    finally {
      if (epoch === sessionEpoch) { transitionBusy = false; render(); }
    }
  }
  async function enterAccount(nextUser) {
    captureDraft();
    cancelAnswers();
    guestImport = !user ? state.chats.filter(chat => chat.messages.length || chat.draft).map(chat => JSON.parse(JSON.stringify(chat))) : [];
    guestSelection = state.activeChatId;
    sessionEpoch++;
    user = nextUser;
    failedWrites.clear();
    latestWrites.clear();
    workspaceReady = false;
    const loaded = await loadAccountWorkspace();
    if (loaded) await completeAuthIntent();
    return loaded;
  }
  async function completeAuthIntent() {
    if (authIntent) {
      const intent = authIntent;
      authIntent = null;
      if (intent.kind === 'article' && !state.favoriteArticles.includes(intent.id)) await saveArticle(intent.id);
      if (intent.kind === 'answer' && !state.favoriteAnswers.some(item => item.message.id === intent.id)) await saveAnswer(intent.id);
    }
  }
  function canEditWorkspace() {
    if (transitionBusy || user && !workspaceReady) { notify('Дождитесь загрузки рабочего пространства или повторите подключение.'); return false; }
    return true;
  }
  function requireAccount(kind, key) {
    if (sessionChecking) { notify('Проверяем вход. Подождите немного.'); return false; }
    if (!user) { authIntent = { kind, id: key }; openAuth(); notify('Войдите, чтобы добавить в избранное.'); return false; }
    return canEditWorkspace();
  }
  async function retrySync() {
    if (transitionBusy) return;
    if (!user) { await initializeSession(); return; }
    if (!workspaceReady) { if (await loadAccountWorkspace()) await completeAuthIntent(); return; }
    for (const job of [...failedWrites.values()]) {
      if (latestWrites.get(job.key) === job) await queueWrite(job.key, job.run, job.apply);
    }
  }
  async function initializeSession() {
    const epoch = sessionEpoch;
    sessionChecking = true;
    renderShell();
    try {
      const result = await api.session();
      if (epoch === sessionEpoch && result?.user?.id) await enterAccount(result.user);
    } catch (error) {
      if (epoch === sessionEpoch && error.status !== 401) {
        notify(error.status === 503 ? 'Вход временно недоступен. Можно пользоваться чатом без входа.' : 'Не удалось проверить вход. Проверьте соединение с сервером.');
      }
    } finally { sessionChecking = false; renderShell(); }
  }
  function notify(text) {
    const toast = document.getElementById('toast');
    toast.textContent = text;
    toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 3200);
  }
  function captureDraft() {
    const composer = view.querySelector('[data-composer]');
    if (!composer || page !== 'chat' || transitionBusy || user && !workspaceReady) return;
    const text = composer.elements.message.value;
    if (!activeChat() && text.trim()) {
      const chat = makeChat();
      state.chats.unshift(chat);
      state.activeChatId = chat.id;
    }
    if (activeChat()) { activeChat().draft = text; persist(); }
  }
  function makeChat() {
    const date = new Date().toISOString();
    return { id: id(), title: 'Новый чат', createdAt: date, updatedAt: date, jurisdiction: '', messages: [], draft: '' };
  }
  function reveal(element, duration = 240, distance = 7) {
    if (!element || reducedMotion.matches || !element.animate) return;
    element.getAnimations().forEach(animation => animation.cancel());
    element.animate([
      { opacity: 0, transform: `translateY(${distance}px)` },
      { opacity: 1, transform: 'translateY(0)' }
    ], { duration, easing: 'cubic-bezier(.22, 1, .36, 1)' });
  }
  function setCitationOpen(card, expanded) {
    if (!card) return;
    const previous = citationAnimations.get(card);
    if (!previous && card.open === expanded) return;
    const start = card.getBoundingClientRect().height;
    if (previous) { previous.onfinish = null; previous.cancel(); citationAnimations.delete(card); }
    card.dataset.expanded = String(expanded);
    if (reducedMotion.matches || !card.animate) { card.open = expanded; return; }
    card.open = true;
    const end = expanded ? card.getBoundingClientRect().height : card.querySelector('summary').getBoundingClientRect().height + 2;
    const animation = card.animate([{ height: `${start}px` }, { height: `${end}px` }], {
      duration: 230, easing: 'cubic-bezier(.22, 1, .36, 1)', fill: 'both'
    });
    citationAnimations.set(card, animation);
    animation.onfinish = () => {
      card.open = expanded;
      citationAnimations.delete(card);
      animation.cancel();
      if (expanded && card.isConnected) card.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    };
  }
  function closeMenu() {
    const sidebar = document.getElementById('sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    const wasOpen = sidebar.classList.contains('is-open');
    sidebar.classList.remove('is-open');
    sidebar.inert = window.matchMedia('(max-width: 980px)').matches;
    backdrop.style.pointerEvents = 'none';
    if (menuAnimation) { menuAnimation.onfinish = null; menuAnimation.cancel(); }
    if (wasOpen && window.matchMedia('(max-width: 980px)').matches && !reducedMotion.matches && backdrop.animate) {
      menuAnimation = backdrop.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 180, fill: 'forwards' });
      menuAnimation.onfinish = () => { backdrop.hidden = true; menuAnimation.cancel(); menuAnimation = null; };
    } else { backdrop.hidden = true; menuAnimation = null; }
    document.getElementById('mobile-menu').setAttribute('aria-expanded', 'false');
    document.body.classList.remove('menu-open');
    if (wasOpen) document.getElementById('mobile-menu').focus({ preventScroll: true });
  }
  function navTo(next, { focus = true } = {}) {
    captureDraft();
    if (page !== 'chat') pageScrollPositions.set(page, view.scrollTop);
    page = ['chat', 'sources', 'compare', 'saved'].includes(next) ? next : 'chat';
    history.replaceState(null, '', '#' + page);
    closeMenu();
    render();
    view.scrollTop = pageScrollPositions.get(page) || 0;
    if (focus) view.focus({ preventScroll: true });
    document.getElementById('chat-scroll')?.scrollTo({ top: 1000000 });
  }
  function newChat(draft = '') {
    if (!canEditWorkspace()) return;
    captureDraft();
    const reusable = state.chats.find(chat => !chat.messages.length && !chat.draft);
    const chat = reusable || makeChat();
    chat.draft = draft;
    if (!reusable) state.chats.unshift(chat);
    state.activeChatId = chat.id;
    persist();
    // Данные уже перенесены: не захватываем черновик предыдущего чата повторно.
    page = 'chat';
    history.replaceState(null, '', '#chat');
    closeMenu();
    render();
    view.querySelector('textarea')?.focus();
  }
  function heading(eyebrow, title, description, count = '') {
    return `<div class="page-heading"><div><p class="eyebrow">${eyebrow}</p><h1>${title}</h1><p>${description}</p></div>${count ? `<span class="count-label">${count}</span>` : ''}</div>`;
  }
  function renderShell() {
    document.querySelectorAll('.nav-item[data-nav]').forEach(button => {
      const selected = button.dataset.nav === page;
      button.classList.toggle('is-active', selected);
      if (selected) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
    const labels = { chat: 'Право рядом', sources: 'Источники', compare: 'Сравнение документов', saved: 'Избранное' };
    document.getElementById('breadcrumb-current').textContent = page === 'chat' && activeChat()?.messages.length ? activeChat().title : labels[page];
    document.getElementById('saved-count').textContent = state.favoriteArticles.length + state.favoriteAnswers.length;
    renderStatus();
    const chats = state.chats.filter(chat => chat.messages.length || chat.draft).slice().sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    document.getElementById('chat-history').innerHTML = chats.length ? chats.map(chat => `<div class="history-item ${page === 'chat' && chat.id === state.activeChatId ? 'is-active' : ''}"><button class="history-open" data-open-chat="${escape(chat.id)}" title="${escape(chat.title)}" ${page === 'chat' && chat.id === state.activeChatId ? 'aria-current="true"' : ''}>${escape(chat.title)}</button><button class="history-delete" data-delete-chat="${escape(chat.id)}" aria-label="Удалить чат: ${escape(chat.title)}">${icon('trash')}</button></div>`).join('') : '<p class="history-empty">Здесь появятся ваши диалоги.</p>';
    const trigger = document.getElementById('account-trigger');
    trigger.hidden = Boolean(user);
    trigger.disabled = sessionChecking;
    document.getElementById('sidebar-account').innerHTML = user
      ? `<div class="account-block"><span class="account-avatar">${escape((user.name || user.email).slice(0, 1).toUpperCase())}</span><div class="account-copy"><strong>${escape(user.name || 'Мой аккаунт')}</strong><small>${escape(user.email)}</small></div></div><button class="text-button" data-logout ${transitionBusy ? 'disabled' : ''}>Выйти из аккаунта</button>`
      : `<div class="account-invite"><button class="button button-secondary" data-auth="login" ${sessionChecking ? 'disabled' : ''}>${icon('user')} Личный кабинет</button></div>`;
  }
  function render() {
    const scrollPosition = document.getElementById('chat-scroll')?.scrollTop || 0;
    const openCitations = [...view.querySelectorAll('.citation-card[open]')].filter(card => card.dataset.expanded !== 'false').map(card => card.id);
    const context = { page, chatId: state.activeChatId, filter: sourceFilter, tab: savedTab, messageIds: new Set(activeChat()?.messages.map(message => message.id) || []) };
    const focused = document.activeElement;
    const wasComposing = focused?.matches('#view textarea[name="message"]');
    const selection = wasComposing ? [focused.selectionStart, focused.selectionEnd] : null;
    const action = ['data-save-article', 'data-save-answer', 'data-remove-answer', 'data-filter', 'data-saved-tab'].find(attribute => focused?.hasAttribute(attribute));
    const actionValue = action ? focused.getAttribute(action) : null;
    renderShell();
    view.classList.toggle('view-chat', page === 'chat');
    const screens = { chat: renderChat, sources: renderSources, compare: renderCompare, saved: renderSaved };
    view.innerHTML = screens[page]();
    for (const key of openCitations) {
      const card = document.getElementById(key);
      if (card) { card.open = true; card.dataset.expanded = 'true'; }
    }
    if (document.getElementById('chat-scroll')) document.getElementById('chat-scroll').scrollTop = scrollPosition;
    if (wasComposing) {
      const textarea = view.querySelector('textarea');
      textarea?.focus({ preventScroll: true });
      textarea?.setSelectionRange(...selection);
    } else if (action) {
      (view.querySelector(`[${action}="${CSS.escape(actionValue)}"]`) || view).focus({ preventScroll: true });
    }
    if (!lastRender || lastRender.page !== page || page === 'chat' && lastRender.chatId !== context.chatId) {
      reveal(view, 260);
    } else if (page === 'sources' && lastRender.filter !== sourceFilter) {
      reveal(view.querySelector('.article-list'), 220, 5);
    } else if (page === 'saved' && lastRender.tab !== savedTab) {
      reveal(view.lastElementChild, 220, 5);
    } else if (page === 'chat') {
      for (const key of context.messageIds) {
        if (!lastRender.messageIds.has(key)) reveal(document.getElementById('message-' + key), 280);
      }
    }
    lastRender = context;
  }
  function composer({ draft = '', jurisdiction = '', busy = false } = {}) {
    const blocked = transitionBusy || user && !workspaceReady;
    return `<form class="composer" data-composer novalidate>
      <textarea ${blocked ? 'disabled' : ''} name="message" rows="2" maxlength="2000" aria-label="Сообщение навигатору" aria-describedby="composer-error" placeholder="Спросите об ИИ и персональных данных…">${escape(draft)}</textarea>
      <div class="composer-bottom"><span class="jurisdiction-control"><select name="jurisdiction" aria-label="Юрисдикция" ${blocked ? 'disabled' : ''}><option value="" ${jurisdiction === '' ? 'selected' : ''}>Россия и ЕС</option><option value="ru" ${jurisdiction === 'ru' ? 'selected' : ''}>Россия</option><option value="eu" ${jurisdiction === 'eu' ? 'selected' : ''}>Европейский союз</option></select>${icon('chevron')}</span>${busy ? `<button class="send-button" type="button" data-stop-answer aria-label="Остановить ответ" title="Остановить ответ">${icon('stop')}</button>` : `<button class="send-button" ${blocked ? 'disabled' : ''} type="submit" aria-label="Отправить сообщение" title="Отправить · Enter">${icon('send')}</button>`}</div>
      <p class="composer-error" id="composer-error" role="alert" hidden></p>
    </form>`;
  }
  function prompts() {
    return `<div class="prompt-row">${[
      ['Персональные данные', scenarios[0].query], ['Передача данных за рубеж', scenarios[3].query], ['Человеческий надзор', scenarios[4].query]
    ].map(([label, query]) => `<button class="prompt-chip" data-topic="${escape(query)}">${label} ↗</button>`).join('')}</div>`;
  }
  function articleCard(article) {
    const doc = docFor(article.documentId);
    const saved = state.favoriteArticles.includes(article.id);
    return `<article class="article-card" data-article="${escape(article.id)}"><div class="article-body"><div class="article-meta"><span class="article-number">${escape(doc.short)} · Статья ${escape(article.number)}</span><span>${escape(doc.jurisdiction)}</span></div><h2>${escape(article.title)}</h2><div class="article-actions"><a href="${escape(article.url)}" target="_blank" rel="noopener noreferrer">Первоисточник ↗</a><button class="text-button" data-topic="${escape(`Помоги разобраться в статье ${article.number} ${doc.short}: «${article.title}».`)}">Обсудить в чате</button></div></div><button class="save-button ${saved ? 'is-saved' : ''}" data-save-article="${escape(article.id)}" ${favoriteOperations.has('article:' + article.id) ? 'disabled aria-busy="true"' : ''} aria-pressed="${saved}" aria-label="${saved ? 'Убрать из избранного' : 'Добавить в избранное'}: ${escape(doc.short)}, статья ${escape(article.number)}">${icon('star')}</button></article>`;
  }
  function renderSources() {
    const shown = articles.filter(article => sourceFilter === 'all' || article.documentId === sourceFilter);
    return `${heading('Нормативная база', 'Источники', 'Выберите документ, чтобы изучить его отдельные статьи.', `${shown.length} ${plural(shown.length, ['статья', 'статьи', 'статей'])}`)}<div class="source-toolbar"><div class="filter-list" aria-label="Документ">${[{ id: 'all', short: 'Все статьи' }, ...documents].map(doc => `<button class="filter-button ${sourceFilter === doc.id ? 'is-active' : ''}" aria-pressed="${sourceFilter === doc.id}" data-filter="${escape(doc.id)}">${escape(doc.short)}</button>`).join('')}</div><button class="text-button" data-nav="compare">Сравнить документы</button></div><div class="article-list">${shown.map(articleCard).join('')}</div>`;
  }
  function renderCompare() {
    const rows = [['Юрисдикция', doc => escape(doc.jurisdiction)], ['Документ', doc => escape(doc.title)], ['Предмет', doc => escape(doc.description)], ['Статьи в каталоге', doc => articles.filter(article => article.documentId === doc.id).map(article => `<a href="${escape(article.url)}" target="_blank" rel="noopener noreferrer">Статья ${escape(article.number)}</a>`).join('<br>')]];
    return `<div class="back-row"><button class="text-button back-button" data-nav="sources">${icon('back')} Назад к источникам</button></div>${heading('Россия и Европейский союз', 'Сравнение документов', 'Основные сведения и ссылки на статьи нормативных актов.')}
      <div class="compare-wrap" role="region" aria-label="Сравнение нормативных документов" tabindex="0"><table class="compare-table"><thead><tr><th scope="col">Параметр</th>${documents.map(doc => `<th scope="col">${escape(doc.short)}</th>`).join('')}</tr></thead><tbody>${rows.map(([label, value]) => `<tr><th scope="row">${label}</th>${documents.map(doc => `<td>${value(doc)}</td>`).join('')}</tr>`).join('')}<tr><th scope="row">Подробнее</th>${documents.map(doc => `<td><button class="text-button" data-document="${escape(doc.id)}">Смотреть статьи →</button></td>`).join('')}</tr></tbody></table></div>`;
  }
  function safeUrl(value) {
    try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : ''; }
    catch { return ''; }
  }
  function applyCatalog(catalog) {
    if (!catalog || !Array.isArray(catalog.documents) || !Array.isArray(catalog.articles)) throw new Error('Invalid catalog');
    const validId = value => typeof value === 'string' && /^[a-zA-Z0-9:._-]+$/.test(value);
    const nextDocuments = catalog.documents.map(doc => {
      if (!doc || !validId(doc.id) || ![doc.short, doc.title, doc.jurisdiction].every(value => typeof value === 'string' && value.trim()) || !safeUrl(doc.url)) throw new Error('Invalid document');
      return { ...doc, description: String(doc.description || ''), mark: String(doc.mark || doc.short.slice(0, 3)), tone: ['ru', 'eu', 'ai'].includes(doc.tone) ? doc.tone : 'ru', url: safeUrl(doc.url) };
    });
    const nextArticles = catalog.articles.map(article => {
      if (!article || !validId(article.id) || !nextDocuments.some(doc => doc.id === article.documentId) || ![article.number, article.title].every(value => typeof value === 'string' && value.trim()) || !safeUrl(article.url)) throw new Error('Invalid article');
      return { ...article, keywords: String(article.keywords || ''), url: safeUrl(article.url) };
    });
    if (new Set(nextDocuments.map(doc => doc.id)).size !== nextDocuments.length || new Set(nextArticles.map(article => article.id)).size !== nextArticles.length) throw new Error('Duplicate catalog IDs');
    captureDraft();
    documents.splice(0, documents.length, ...nextDocuments);
    articles.splice(0, articles.length, ...nextArticles);
    if (sourceFilter !== 'all' && !docFor(sourceFilter)) sourceFilter = 'all';
    render();
  }
  function renderAnswerText(message) {
    const text = escape(message.text).replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
    const ids = new Set((message.citations || []).map(citation => citation.id).filter(Boolean));
    return text.replace(/\[([a-zA-Z][a-zA-Z0-9_-]*)\]/g, (label, key) => ids.has(key)
      ? `<button class="citation-ref" data-citation="${escape(message.id + ':' + key)}" aria-label="Открыть источник ${escape(key)}">${label}</button>` : label);
  }
  function renderCitations(citations = [], messageId = '') {
    if (!Array.isArray(citations) || !citations.length) return '';
    return `<div class="citation-section"><span class="citation-heading">Источники</span><ul class="citation-list">${citations.map((citation, index) => {
      const url = safeUrl(citation.url);
      const jurisdiction = { ru: 'Россия', eu: 'Европейский союз' }[citation.jurisdiction] || citation.jurisdiction;
      return `<li><details class="citation-card" id="citation-${escape(messageId + ':' + (citation.id || index))}"><summary>${citation.id ? `<span class="citation-id">${escape(citation.id)}</span>` : ''}<span class="citation-title"><strong>${escape(citation.doc_title)}</strong> · ${escape(citation.article)}</span>${icon('chevron')}</summary><div class="citation-body">${citation.excerpt ? `<blockquote>${escape(citation.excerpt)}</blockquote>` : ''}<p class="citation-meta">${[jurisdiction, citation.edition].filter(Boolean).map(escape).join(' · ')}</p>${url ? `<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">Первоисточник ${icon('link')}</a>` : ''}</div></details></li>`;
    }).join('')}</ul></div>`;
  }
  function errorMessage(message) {
    return message.errorText || (message.status === 'interrupted' ? 'Получение ответа остановлено. Можно повторить запрос.' : 'Не удалось получить ответ. Попробуйте ещё раз.');
  }
  function renderMessage(message, chat) {
    const saved = state.favoriteAnswers.some(item => item.message.id === message.id);
    const failed = ['error', 'interrupted'].includes(message.status);
    return `<article class="message message-${message.role}" id="message-${escape(message.id)}"><div class="message-label">${icon('mark')} ${message.role === 'user' ? 'Вы' : 'Право рядом'}</div><div class="message-content">${message.role === 'assistant' ? renderAnswerText(message) : escape(message.text)}</div>${renderCitations(message.citations, message.id)}${failed ? `<div class="message-error" role="status">${escape(errorMessage(message))}</div><button class="text-button" data-retry="${escape(message.id)}" ${pending.has(chat.id) ? 'disabled' : ''}>Повторить запрос</button>` : ''}${message.role === 'assistant' ? `<div class="message-actions"><button class="icon-button" data-copy-answer="${escape(message.id)}" aria-label="Скопировать ответ" title="Скопировать ответ">${icon('copy')}</button><button class="icon-button ${saved ? 'is-saved' : ''}" data-save-answer="${escape(message.id)}" ${favoriteOperations.has('answer:' + message.id) ? 'disabled aria-busy="true"' : ''} aria-label="${saved ? 'Убрать ответ из избранного' : 'Добавить ответ в избранное'}" title="${saved ? 'В избранном' : 'В избранное'}" aria-pressed="${saved}">${icon('star')}</button></div>` : ''}</article>`;
  }
  function renderChat() {
    const chat = activeChat();
    const messages = chat?.messages || [];
    const busy = chat && pending.has(chat.id);
    const form = `<div class="composer-dock">${composer({ draft: chat?.draft || '', jurisdiction: chat?.jurisdiction || '', busy })}${messages.length ? '<p class="composer-note">152-ФЗ · GDPR · AI Act</p>' : ''}</div>`;
    return messages.length
      ? `<section class="chat-page" aria-label="Диалог с навигатором"><div class="messages" id="chat-scroll"><div class="message-list" role="log" aria-label="Переписка">${messages.map(message => renderMessage(message, chat)).join('')}${busy ? '<div class="pending-label" role="status"><span class="pending-dots" aria-hidden="true"><i></i><i></i><i></i></span>Ищу ответ в документах…</div>' : ''}</div></div>${form}</section>`
      : `<section class="chat-page is-empty" aria-label="Новый чат"><div class="chat-intro">${icon('mark')}<h1>Что разберём сегодня?</h1><p>ИИ и защита данных. С опорой на документы.</p></div>${form}${prompts()}</section>`;
  }
  function renderSaved() {
    if (!user) return heading('Ваша подборка', 'Избранное', 'Полезные ответы и статьи, к которым хочется вернуться.') + `<div class="empty-state"><span class="empty-icon" aria-hidden="true">${icon('star')}</span><h2>Избранное в вашем аккаунте</h2><p>Войдите, чтобы сохранять ответы и статьи и открывать их на любом устройстве.</p><button class="button button-primary" data-auth="login">Войти</button></div>`;
    if (!workspaceReady) return heading('Ваша подборка', 'Избранное', 'Загружаем сохранённые ответы и статьи…');
    const selected = articles.filter(article => state.favoriteArticles.includes(article.id));
    const tabs = `<div class="tab-list" aria-label="Тип избранного"><button class="filter-button ${savedTab === 'answers' ? 'is-active' : ''}" aria-pressed="${savedTab === 'answers'}" data-saved-tab="answers">Ответы · ${state.favoriteAnswers.length}</button><button class="filter-button ${savedTab === 'articles' ? 'is-active' : ''}" aria-pressed="${savedTab === 'articles'}" data-saved-tab="articles">Статьи · ${selected.length}</button></div>`;
    const empty = `<div class="empty-state"><span class="empty-icon" aria-hidden="true">${icon('star')}</span><h2>${savedTab === 'answers' ? 'Сохраните полезный ответ' : 'Соберите нужные статьи'}</h2><p>${savedTab === 'answers' ? 'Нажмите «В избранное» под ответом в чате, чтобы быстро вернуться к нему.' : 'Нажмите на звёздочку у статьи в разделе «Источники».'}</p><button class="button button-secondary" data-nav="${savedTab === 'answers' ? 'chat' : 'sources'}">${savedTab === 'answers' ? 'Открыть чат' : 'Перейти к источникам'} →</button></div>`;
    let content;
    if (savedTab === 'articles') content = selected.length ? `<div class="article-list">${selected.map(articleCard).join('')}</div>` : empty;
    else content = state.favoriteAnswers.length ? `<div class="favorite-list">${state.favoriteAnswers.map(item => `<article class="favorite-card"><div class="favorite-heading"><div><p>${shortDate(item.savedAt)} · Ответ навигатора</p><h2>${escape(item.question)}</h2></div><button class="save-button is-saved" data-remove-answer="${escape(item.message.id)}" ${favoriteOperations.has('answer:' + item.message.id) ? 'disabled aria-busy="true"' : ''} aria-label="Убрать ответ из избранного">${icon('star')}</button></div><div class="message-content">${renderAnswerText(item.message)}</div>${renderCitations(item.message.citations, item.message.id)}${state.chats.some(chat => chat.id === item.chatId) ? `<button class="text-button" data-open-chat="${escape(item.chatId)}" data-message="${escape(item.message.id)}">Перейти к диалогу →</button>` : ''}</article>`).join('')}</div>` : empty;
    return heading('Ваша подборка', 'Избранное', 'Полезные ответы и статьи, к которым хочется вернуться.') + tabs + content;
  }

  function parseReply(response) {
    if (!response || !['ok', 'need_clarification', 'insufficient'].includes(response.status)) throw Object.assign(new Error('Invalid chat response'), { code: 'format' });
    const text = response.status === 'need_clarification' ? response.clarification_question : response.answer || (response.status === 'insufficient' ? 'В документах нет информации по этому вопросу' : '');
    if (typeof text !== 'string' || !text.trim()) throw Object.assign(new Error('Empty answer'), { code: 'format' });
    return { text, replyStatus: response.status, citations: Array.isArray(response.citations) ? response.citations.filter(item => item && typeof item.doc_title === 'string').map(item => ({ ...item })) : [] };
  }
  async function receiveAnswer(chat, message) {
    if (pending.has(chat.id)) return;
    const controller = new AbortController();
    pending.set(chat.id, controller);
    message.status = 'pending';
    delete message.errorText;
    persist();
    saveChatToServer(chat);
    render();
    document.getElementById('chat-scroll')?.scrollTo({ top: 1000000 });
    try {
      const response = await api.chat({ query: message.text, jurisdiction: message.jurisdiction ?? null }, controller.signal);
      const reply = parseReply(response);
      if (controller.signal.aborted || !state.chats.includes(chat)) return;
      message.status = 'sent';
      chat.messages.splice(chat.messages.indexOf(message) + 1, 0, { id: id(), role: 'assistant', text: reply.text, citations: reply.citations, replyStatus: reply.replyStatus, createdAt: new Date().toISOString() });
    } catch (error) {
      message.status = error.code === 'cancelled' ? 'interrupted' : 'error';
      message.errorText = error.code === 'cancelled' ? 'Получение ответа остановлено. Можно повторить запрос.' : error.code === 'timeout' ? 'Ответ не пришёл за отведённое время. Попробуйте ещё раз.' : error.code === 'network' ? 'Нет связи с сервером. Проверьте подключение и повторите запрос.' : error.status === 422 ? 'Запрос не принят. Введите вопрос длиной от 1 до 2000 символов.' : error.status === 502 ? 'Не удалось выполнить поиск или получить ответ модели. Попробуйте ещё раз.' : error.code === 'format' ? 'Сервер вернул ответ в неподдерживаемом формате. Попробуйте ещё раз.' : 'Не удалось получить ответ. Попробуйте ещё раз.';
    } finally {
      pending.delete(chat.id);
      if (state.chats.includes(chat)) {
        chat.updatedAt = new Date().toISOString();
        persist();
        saveChatToServer(chat);
        if (page === 'chat' && state.activeChatId === chat.id) {
          const scroller = document.getElementById('chat-scroll');
          const nearBottom = scroller && scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 140;
          captureDraft();
          render();
          if (nearBottom) document.getElementById('chat-scroll')?.scrollTo({ top: 1000000 });
        } else renderShell();
      }
    }
  }
  async function sendMessage(form) {
    if (!canEditWorkspace() || deletingChats.has(state.activeChatId)) return;
    const text = form.elements.message.value.trim();
    if (!text || text.length > 2000) { const error = form.querySelector('#composer-error'); error.hidden = false; error.textContent = text.length > 2000 ? 'Вопрос должен быть не длиннее 2000 символов.' : 'Введите вопрос.'; form.elements.message.setAttribute('aria-invalid', 'true'); form.elements.message.focus(); return; }
    const jurisdiction = form.elements.jurisdiction.value;
    if (activeChat()?.messages.length > 198) { const error = form.querySelector('#composer-error'); error.hidden = false; error.textContent = 'В чате достигнут лимит 200 сообщений. Начните новый диалог.'; return; }
    if (!activeChat()) newChat();
    const chat = activeChat();
    if (pending.has(chat.id)) return;
    chat.jurisdiction = jurisdiction;
    chat.draft = '';
    const message = { id: id(), role: 'user', text, jurisdiction: jurisdiction || null, createdAt: new Date().toISOString(), status: 'pending' };
    chat.messages.push(message);
    if (chat.messages.length === 1) chat.title = text.length > 65 ? text.slice(0, 65) + '…' : text;
    await receiveAnswer(chat, message);
  }
  async function saveArticle(key) {
    if (!articles.some(article => article.id === key) || !requireAccount('article', key)) return;
    const operation = 'article:' + key;
    if (favoriteOperations.has(operation)) return;
    favoriteOperations.add(operation);
    captureDraft();
    const saved = state.favoriteArticles.includes(key);
    render();
    const success = await queueWrite(operation, () => api.article(key, !saved), () => {
      state.favoriteArticles = saved ? state.favoriteArticles.filter(item => item !== key) : [...new Set([...state.favoriteArticles, key])];
      render();
    });
    favoriteOperations.delete(operation);
    render();
    if (success) notify(saved ? 'Статья убрана из избранного' : 'Статья добавлена в избранное');
  }
  async function saveAnswer(key) {
    if (!requireAccount('answer', key)) return;
    const operation = 'answer:' + key;
    if (favoriteOperations.has(operation)) return;
    favoriteOperations.add(operation);
    captureDraft();
    const existing = state.favoriteAnswers.some(item => item.message.id === key);
    let favorite = null;
    if (!existing) {
      const chat = state.chats.find(chat => chat.messages.some(message => message.id === key && message.role === 'assistant'));
      if (!chat) { favoriteOperations.delete(operation); return; }
      const index = chat.messages.findIndex(message => message.id === key);
      const question = chat.messages.slice(0, index).reverse().find(message => message.role === 'user')?.text || chat.title;
      favorite = { chatId: chat.id, question, message: JSON.parse(JSON.stringify(chat.messages[index])), savedAt: new Date().toISOString() };
    }
    render();
    const success = await queueWrite(operation, () => api.answer(key, favorite), () => {
      state.favoriteAnswers = state.favoriteAnswers.filter(item => item.message.id !== key);
      if (favorite) state.favoriteAnswers.unshift(favorite);
      render();
    });
    favoriteOperations.delete(operation);
    render();
    if (success) notify(existing ? 'Ответ убран из избранного' : 'Ответ добавлен в избранное');
  }
  function openChat(key, messageId) {
    if (!state.chats.some(chat => chat.id === key)) return;
    captureDraft();
    state.activeChatId = key;
    persist();
    page = 'chat'; history.replaceState(null, '', '#chat'); closeMenu(); render();
    if (messageId) document.getElementById('message-' + messageId)?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    else document.getElementById('chat-scroll')?.scrollTo({ top: 1000000 });
    view.focus({ preventScroll: true });
  }
  async function deleteChat(key) {
    if (!canEditWorkspace() || deletingChats.has(key)) return;
    const chat = state.chats.find(item => item.id === key);
    if (!chat || !window.confirm('Удалить этот чат? Избранные ответы сохранятся.')) return;
    captureDraft();
    deletingChats.add(key);
    pending.get(key)?.abort();
    pending.delete(key);
    const remove = () => {
      state.chats = state.chats.filter(item => item.id !== key);
      if (state.activeChatId === key) state.activeChatId = null;
      persist(); render();
    };
    const success = user ? await queueWrite('chat:' + key, () => api.deleteChat(key), remove) : (remove(), true);
    deletingChats.delete(key);
    if (success) notify('Чат удалён');
  }
  async function logout() {
    if (transitionBusy) return;
    captureDraft();
    cancelAnswers();
    for (const chat of state.chats) if (chat.messages.length) saveChatToServer(chat);
    transitionBusy = true;
    render();
    try {
      await writeQueue;
      if (!user) return;
      await api.logout();
      const unsaved = failedWrites.size;
      sessionEpoch++;
      user = null;
      state = emptyState();
      guestImport = [];
      guestSelection = null;
      failedWrites.clear();
      latestWrites.clear();
      workspaceReady = true;
      showNotice(null);
      notify(unsaved ? 'Вы вышли. Часть изменений не удалось сохранить.' : 'Вы вышли из аккаунта');
    } catch (error) { storageError(error, sessionEpoch); }
    finally { transitionBusy = false; render(); }
  }

  function openAuth(mode = 'login') {
    if (authBusy) return;
    const wasOpen = dialog.open;
    const currentForm = dialog.querySelector('[data-auth-form]');
    if (wasOpen && currentForm?.dataset.authForm === mode && !authCloseAnimation) return;
    const previousHeight = wasOpen ? dialog.getBoundingClientRect().height : 0;
    const previousTab = dialog.querySelector('.auth-tab.is-active');
    const previousIndicator = previousTab ? { left: previousTab.offsetLeft, width: previousTab.offsetWidth } : null;
    const savedEmail = currentForm?.elements.email.value || '';
    const savedName = currentForm?.elements.name?.value || '';
    if (authLayoutAnimation) { authLayoutAnimation.onfinish = null; authLayoutAnimation.cancel(); authLayoutAnimation = null; }
    dialog.classList.remove('is-switching');
    if (authCloseAnimation) { authCloseAnimation.onfinish = null; authCloseAnimation.cancel(); authCloseAnimation = null; }
    dialog.classList.remove('is-closing');
    const register = mode === 'register';
    dialog.innerHTML = `<button class="icon-button dialog-close" data-close-auth aria-label="Закрыть окно">${icon('close')}</button><div class="auth-mark" aria-hidden="true">${icon('mark')}</div><h2 id="auth-title">${register ? 'Создать аккаунт' : 'С возвращением'}</h2><p>${register ? 'Ваш личный навигатор.' : 'Войдите в личный кабинет навигатора.'}</p><div class="auth-tabs" aria-label="Вход или регистрация"><button class="auth-tab ${!register ? 'is-active' : ''}" aria-pressed="${!register}" data-auth="login">Вход</button><button class="auth-tab ${register ? 'is-active' : ''}" aria-pressed="${register}" data-auth="register">Регистрация</button><span class="auth-tab-indicator" aria-hidden="true"></span></div>
      <form data-auth-form="${mode}">${register ? '<label class="field">Имя<input name="name" autocomplete="name" maxlength="100" required placeholder="Как к вам обращаться" /></label>' : ''}<label class="field">Электронная почта<input type="email" name="email" autocomplete="username" required placeholder="you@example.com" /></label><label class="field">Пароль<span class="password-field"><input type="password" id="auth-password" name="password" autocomplete="${register ? 'new-password' : 'current-password'}" ${register ? 'minlength="8"' : ''} maxlength="128" required ${register ? 'aria-describedby="password-hint"' : ''} /><button class="password-toggle" type="button" data-toggle-password="auth-password" aria-pressed="false">Показать</button></span>${register ? '<small class="field-hint" id="password-hint">Не менее 8 символов</small>' : ''}</label>${register ? '<label class="field">Повторите пароль<input type="password" name="passwordConfirmation" autocomplete="new-password" required minlength="8" maxlength="128" /></label>' : ''}<div class="form-error" id="auth-error" role="alert" hidden></div><button class="button button-primary auth-submit" type="submit">${register ? 'Создать аккаунт' : 'Войти'}</button></form>`;
    if (!dialog.open) dialog.showModal();
    const form = dialog.querySelector('[data-auth-form]');
    form.elements.email.value = savedEmail;
    if (form.elements.name) form.elements.name.value = savedName;
    const activeTab = dialog.querySelector('.auth-tab.is-active');
    const indicator = dialog.querySelector('.auth-tab-indicator');
    indicator.style.left = activeTab.offsetLeft + 'px';
    indicator.style.width = activeTab.offsetWidth + 'px';
    if (!reducedMotion.matches && dialog.animate) {
      if (wasOpen) {
        const targetHeight = dialog.getBoundingClientRect().height;
        dialog.classList.add('is-switching');
        const animation = dialog.animate([{ height: previousHeight + 'px' }, { height: targetHeight + 'px' }], { duration: 280, easing: 'cubic-bezier(.22, 1, .36, 1)' });
        authLayoutAnimation = animation;
        animation.onfinish = () => {
          if (authLayoutAnimation === animation) { authLayoutAnimation = null; dialog.classList.remove('is-switching'); }
        };
        form.animate([{ opacity: 0, transform: `translateX(${register ? 10 : -10}px)` }, { opacity: 1, transform: 'translateX(0)' }], { duration: 230, easing: 'ease-out' });
        if (previousIndicator) indicator.animate([
          { transform: `translateX(${previousIndicator.left - activeTab.offsetLeft}px) scaleX(${previousIndicator.width / activeTab.offsetWidth})` },
          { transform: 'translateX(0) scaleX(1)' }
        ], { duration: 260, easing: 'cubic-bezier(.22, 1, .36, 1)' });
        reveal(dialog.querySelector('#auth-title'), 200, 3);
      } else {
        dialog.animate([{ opacity: 0, transform: 'translateY(12px) scale(.98)' }, { opacity: 1, transform: 'translateY(0) scale(1)' }], { duration: 260, easing: 'cubic-bezier(.22, 1, .36, 1)' });
      }
    }
    dialog.querySelector('input')?.focus();
  }
  function closeAuth(force = false) {
    if (!dialog.open || authBusy && !force || authCloseAnimation) return;
    if (authLayoutAnimation) { authLayoutAnimation.onfinish = null; authLayoutAnimation.cancel(); authLayoutAnimation = null; }
    dialog.classList.remove('is-switching');
    if (reducedMotion.matches || !dialog.animate) { dialog.close(); return; }
    dialog.getAnimations().forEach(animation => animation.cancel());
    dialog.classList.add('is-closing');
    authCloseAnimation = dialog.animate([
      { opacity: 1, transform: 'translateY(0) scale(1)' },
      { opacity: 0, transform: 'translateY(6px) scale(.985)' }
    ], { duration: 150, easing: 'ease-in', fill: 'forwards' });
    authCloseAnimation.onfinish = () => {
      const animation = authCloseAnimation;
      authCloseAnimation = null;
      animation.onfinish = null;
      animation.cancel();
      dialog.classList.remove('is-closing');
      dialog.close();
    };
  }
  async function submitAuth(form) {
    if (authBusy) return;
    const fields = new FormData(form);
    const mode = form.dataset.authForm;
    const error = document.getElementById('auth-error');
    const showError = message => { error.textContent = message; error.hidden = false; };
    if (mode === 'register' && fields.get('password') !== fields.get('passwordConfirmation')) {
      showError('Пароли не совпадают.'); form.elements.passwordConfirmation.focus(); return;
    }
    authBusy = true;
    error.hidden = true;
    const buttons = dialog.querySelectorAll('button');
    buttons.forEach(button => { button.disabled = true; });
    const submit = form.querySelector('[type="submit"]');
    const label = submit.textContent;
    submit.textContent = mode === 'register' ? 'Создаём аккаунт…' : 'Входим…';
    try {
      const nextUser = await api.authenticate(mode, { email: fields.get('email').trim(), password: fields.get('password'), ...(mode === 'register' ? { name: fields.get('name').trim() } : {}) });
      const loaded = await enterAccount(nextUser);
      closeAuth(true);
      if (loaded) notify('Вы вошли в аккаунт');
    } catch (failure) {
      showError(failure.status === 401 ? 'Неверная почта или пароль.' : failure.status === 409 ? 'Эта почта уже зарегистрирована. Войдите в аккаунт.' : failure.status === 422 ? 'Проверьте имя, почту и пароль (от 8 до 128 символов).' : failure.status === 503 ? 'Вход временно недоступен. Попробуйте позже. Чатом можно пользоваться без входа.' : 'Не удалось связаться с сервисом входа. Попробуйте ещё раз.');
    } finally {
      authBusy = false;
      buttons.forEach(button => { button.disabled = false; });
      submit.textContent = label;
      form.elements.password.value = '';
      if (form.elements.passwordConfirmation) form.elements.passwordConfirmation.value = '';
    }
  }

  document.addEventListener('click', event => {
    const summary = event.target.closest('.citation-card > summary');
    if (summary) {
      event.preventDefault();
      const card = summary.parentElement;
      const expanded = card.dataset.expanded === 'true' || card.dataset.expanded === undefined && card.open;
      setCitationOpen(card, !expanded);
      return;
    }
    const target = event.target.closest('button, a');
    if (!target) return;
    if (target.hasAttribute('data-retry-sync')) { void retrySync(); return; }
    if (target.hasAttribute('data-new-chat')) { newChat(); return; }
    if (target.dataset.nav) { event.preventDefault(); navTo(target.dataset.nav); return; }
    if (target.dataset.topic) { newChat(target.dataset.topic); return; }
    if (target.dataset.document) { sourceFilter = target.dataset.document; navTo('sources'); return; }
    if (target.dataset.filter) { sourceFilter = target.dataset.filter; render(); return; }
    if (target.dataset.saveArticle) { saveArticle(target.dataset.saveArticle); return; }
    if (target.dataset.saveAnswer) { saveAnswer(target.dataset.saveAnswer); return; }
    if (target.dataset.removeAnswer) { saveAnswer(target.dataset.removeAnswer); return; }
    if (target.dataset.savedTab) { savedTab = target.dataset.savedTab; render(); return; }
    if (target.dataset.openChat) { openChat(target.dataset.openChat, target.dataset.message); return; }
    if (target.dataset.deleteChat) { deleteChat(target.dataset.deleteChat); return; }
    if (target.hasAttribute('data-stop-answer')) { pending.get(state.activeChatId)?.abort(); return; }
    if (target.dataset.citation) { const card = document.getElementById('citation-' + target.dataset.citation); if (card) { setCitationOpen(card, true); card.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); card.querySelector('summary')?.focus({ preventScroll: true }); } return; }
    if (target.dataset.copyAnswer) { const message = state.chats.flatMap(chat => chat.messages).find(message => message.id === target.dataset.copyAnswer); if (message) navigator.clipboard.writeText(message.text).then(() => notify('Ответ скопирован')).catch(() => notify('Не удалось скопировать ответ')); return; }
    if (target.dataset.retry) {
      const chat = activeChat(); const message = chat?.messages.find(item => item.id === target.dataset.retry);
      if (message && canEditWorkspace()) { captureDraft(); void receiveAnswer(chat, message); } return;
    }
    if (target.dataset.auth) { closeMenu(); openAuth(target.dataset.auth); return; }
    if (target.hasAttribute('data-close-auth')) { closeAuth(); return; }
    if (target.dataset.togglePassword) {
      const field = document.getElementById(target.dataset.togglePassword);
      field.type = field.type === 'password' ? 'text' : 'password';
      target.textContent = field.type === 'password' ? 'Показать' : 'Скрыть';
      target.setAttribute('aria-pressed', String(field.type === 'text')); return;
    }
    if (target.hasAttribute('data-logout')) {
      void logout();
    }
  });
  document.addEventListener('submit', event => {
    if (event.target.matches('[data-composer]')) { event.preventDefault(); void sendMessage(event.target); }
    if (event.target.matches('[data-auth-form]')) { event.preventDefault(); void submitAuth(event.target); }
  });
  document.addEventListener('input', event => {
    if (event.target.matches('textarea[name="message"]')) { const error = document.getElementById('composer-error'); if (error) error.hidden = true; event.target.removeAttribute('aria-invalid'); captureDraft(); event.target.style.height = 'auto'; event.target.style.height = Math.min(event.target.scrollHeight, 200) + 'px'; }
  });
  document.addEventListener('change', event => {
    if (event.target.matches('[data-composer] select') && activeChat() && page === 'chat') {
      activeChat().jurisdiction = event.target.value; persist();
    }
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeMenu();
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.target.matches('textarea[name="message"]')) {
      event.preventDefault(); const form = event.target.form;
      if (form.querySelector('[type="submit"]') && !form.querySelector('[type="submit"]').disabled) form.requestSubmit();
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k' && !dialog.open) {
      event.preventDefault(); newChat();
    }
  });
  document.getElementById('mobile-menu').addEventListener('click', () => {
    if (document.getElementById('sidebar').classList.contains('is-open')) closeMenu();
    else {
      if (menuAnimation) { menuAnimation.onfinish = null; menuAnimation.cancel(); menuAnimation = null; }
      document.getElementById('sidebar').classList.add('is-open');
      document.getElementById('sidebar').inert = false;
      const backdrop = document.getElementById('sidebar-backdrop');
      backdrop.hidden = false;
      backdrop.style.pointerEvents = '';
      if (!reducedMotion.matches && backdrop.animate) menuAnimation = backdrop.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 220 });
      document.getElementById('mobile-menu').setAttribute('aria-expanded', 'true');
      document.body.classList.add('menu-open');
      document.querySelector('.new-chat-button').focus();
    }
  });
  document.getElementById('sidebar-backdrop').addEventListener('click', closeMenu);
  window.matchMedia('(max-width: 980px)').addEventListener('change', closeMenu);
  dialog.addEventListener('cancel', event => { event.preventDefault(); closeAuth(); });
  dialog.addEventListener('close', () => {
    if (authCloseAnimation) { authCloseAnimation.onfinish = null; authCloseAnimation.cancel(); authCloseAnimation = null; }
    if (authLayoutAnimation) { authLayoutAnimation.onfinish = null; authLayoutAnimation.cancel(); authLayoutAnimation = null; }
    dialog.classList.remove('is-closing', 'is-switching');
    dialog.innerHTML = '';
    if (!user) authIntent = null;
  });
  dialog.addEventListener('click', event => { if (event.target === dialog && !authBusy) { const box = dialog.getBoundingClientRect(); if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) closeAuth(); } });
  window.addEventListener('hashchange', () => {
    const next = location.hash.slice(1);
    if (['chat', 'sources', 'compare', 'saved'].includes(next)) navTo(next);
  });
  window.addEventListener('pagehide', captureDraft);
  render();
  api.catalog().then(catalog => { if (catalog) applyCatalog(catalog); }).catch(() => { notify('Не удалось обновить каталог. Попробуйте перезагрузить страницу.'); });
  void initializeSession();
})();
