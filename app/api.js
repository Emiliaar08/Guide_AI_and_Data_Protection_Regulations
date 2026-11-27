// Единственная точка подключения интерфейса к серверу. Контракт: spec/tech/architecture.md.
window.NavigatorApi = (() => {
  const config = window.NAVIGATOR_CONFIG || {};
  class ApiError extends Error {
    constructor(code, status = 0) { super(code); this.code = code; this.status = status; }
  }
  async function request(path, { signal, timeoutMs = 30000, ...options } = {}) {
    const controller = new AbortController();
    let timedOut = false;
    const cancel = () => controller.abort();
    if (signal?.aborted) throw new ApiError('cancelled');
    signal?.addEventListener('abort', cancel, { once: true });
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
    try {
      const response = await fetch(path, { credentials: 'same-origin', ...options, headers: { 'Content-Type': 'application/json', ...options.headers }, signal: controller.signal });
      if (!response.ok) throw new ApiError('http', response.status);
      if (response.status === 204) return null;
      try { return await response.json(); }
      catch { throw new ApiError('format'); }
    } catch (error) {
      if (timedOut) throw new ApiError('timeout');
      if (signal?.aborted) throw new ApiError('cancelled');
      if (error instanceof ApiError) throw error;
      throw new ApiError('network');
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', cancel);
    }
  }
  async function chat({ query, jurisdiction }, signal) {
    return request(config.chatEndpoint || '/api/search', {
      method: 'POST', body: JSON.stringify({ query, jurisdiction: jurisdiction || null }), signal,
      timeoutMs: Number.isFinite(config.chatTimeoutMs) && config.chatTimeoutMs > 0 ? config.chatTimeoutMs : 210000
    });
  }
  // Авторизация использует HttpOnly-cookie; токены не доступны JavaScript.
  async function authenticate(mode, fields) {
    const data = await request(`${config.authBase || '/api/auth'}/${mode === 'register' ? 'register' : 'login'}`, { method: 'POST', body: JSON.stringify(fields) });
    if (!data?.user?.id || !data.user.email) throw new ApiError('format');
    return data.user;
  }
  const catalog = () => config.catalogEndpoint ? request(config.catalogEndpoint) : Promise.resolve(null);
  const logout = () => request(`${config.authBase || '/api/auth'}/logout`, { method: 'POST' });
  const session = () => request(`${config.authBase || '/api/auth'}/me`);
  const workspaceBase = config.workspaceBase || '/api';
  const workspace = () => request(`${workspaceBase}/workspace`);
  const putChat = chat => request(`${workspaceBase}/chats/${encodeURIComponent(chat.id)}`, { method: 'PUT', body: JSON.stringify(chat) });
  const deleteChat = id => request(`${workspaceBase}/chats/${encodeURIComponent(id)}`, { method: 'DELETE' });
  const article = (id, saved) => request(`${workspaceBase}/favorites/articles/${encodeURIComponent(id)}`, { method: saved ? 'PUT' : 'DELETE' });
  const answer = (id, value) => request(`${workspaceBase}/favorites/answers/${encodeURIComponent(id)}`, { method: value ? 'PUT' : 'DELETE', ...(value ? { body: JSON.stringify(value) } : {}) });
  return { chat, authenticate, catalog, logout, session, workspace, putChat, deleteChat, article, answer };
})();
