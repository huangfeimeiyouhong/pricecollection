/* 静态数据加载与本地缓存（无后端依赖，适配 Cloudflare Pages 等纯静态托管）
 * - 数据来自同源的 ./data.json（由后端 gen_static.py 生成）
 * - 首次加载：优先渲染 localStorage 缓存（秒开），再后台拉取最新并比对
 * - 「刷新缓存」按钮：强制重新拉取 data.json 并写回 localStorage
 */
(function () {
  const LS_KEY = 'houchu_price_bundle_v1';
  const BUNDLE = './data.json';

  function readCache() {
    try {
      return JSON.parse(localStorage.getItem(LS_KEY) || 'null');
    } catch (e) {
      return null;
    }
  }

  function writeCache(d) {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(d));
    } catch (e) {
      /* 隐私模式或超额：忽略，仅本次会话有效 */
    }
  }

  async function fetchLatest() {
    const resp = await fetch(BUNDLE + '?t=' + Date.now(), { cache: 'no-store' });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const d = await resp.json();
    writeCache(d);
    return d;
  }

  window.PriceStatic = { LS_KEY, readCache, writeCache, fetchLatest };
})();
