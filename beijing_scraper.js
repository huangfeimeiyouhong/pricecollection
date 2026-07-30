// 北京 6 大农批市场价格抓取（食价搜 21food.cn）
// 该站对部分市场返回 JS 反爬验证页（202 页面加载中），必须用真实浏览器渲染。
// 本脚本用 puppeteer-core 驱动本机 Microsoft Edge（Chromium 内核）渲染并解析。
// 用法: node beijing_scraper.js <marketId> [marketId ...]
// 输出: JSON -> { "<marketId>": [ {name, max, min, avg, date, unit}, ... ], ... }
const puppeteer = require('puppeteer-core');

const EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge';
const PROFILE = '/tmp/edge_bj_profile'; // 持久化档案：保留通过验证后的信任 cookie，避免反复挑战
const BASE = 'https://price.21food.cn/market/';
// 每个市场最多抓取的页数（每页约 30 条）。调大可获取更全，但更慢且更易触发风控。
const MAX_PAGES = parseInt(process.env.FOOD_MAX_PAGES || process.env.BJ_MAX_PAGES || '3', 10);
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36';

function sleep(ms){ return new Promise(r=>setTimeout(r, ms)); }

// 在浏览器内执行：提取当前页所有商品行
function extractRows(){
  const lis = Array.from(document.querySelectorAll('ul li')).filter(li => li.querySelector('a.opu_l4'));
  return lis.map(li => {
    const a = li.querySelector('a.opu_l4');
    const name = a ? a.textContent.trim() : '';
    const allSpans = Array.from(li.querySelectorAll('span')).map(s => s.textContent.trim());
    const priceSpans = allSpans.filter(t => /元\/公斤/.test(t)).map(t => parseFloat(t.replace(/元\/公斤/, '')));
    const date = allSpans.find(t => /^\d{4}-\d{2}-\d{2}$/.test(t)) || '';
    const max = priceSpans[0], min = priceSpans[1], avg = priceSpans[2] != null ? priceSpans[2] : priceSpans[0];
    return { name, max, min, avg, date, unit: '元/公斤' };
  }).filter(r => r.name && !isNaN(r.avg));
}

// 带重试的提取：验证码通过后页面往往会自动重载，期间读取可能抛
// "detached Frame / Execution context destroyed" 错误。这里捕获并重试，
// 直到拿到数据或耗尽重试次数。
async function extractWithRetry(page, times){
  times = times || 6;
  let lastErr = '';
  for (let i = 0; i < times; i++) {
    try {
      const rows = await page.evaluate(extractRows);
      if (rows && rows.length) return rows;
    } catch (e) {
      lastErr = e.message;
    }
    await sleep(1500);
  }
  if (lastErr) process.stderr.write(`extractWithRetry: 多次尝试仍失败 (${lastErr})\n`);
  return [];
}

// ---- 行为验证码处理 ----
// 检测当前页是否出现验证码，返回 {present, type, text}
async function detectCaptcha(page){
  return await page.evaluate(() => {
    const area = document.querySelector('.verify-bar-area');
    // 关键：不仅要判断节点存在，还要判断它「真的可见」。
    // 验证通过后该层往往被隐藏（display:none / 移出布局）但仍在 DOM，
    // 若只判存在会误以为验证码仍在，导致反复等待/重新跳转触发新验证码。
    if (!area) return { present: false };
    const cs = getComputedStyle(area);
    if (cs.display === 'none' || cs.visibility === 'hidden' || area.offsetParent === null) {
      return { present: false };
    }
    const txt = (area.innerText || '').trim();
    let type = 'unknown';
    if (/向右滑动|滑动/.test(txt)) type = 'slider';
    else if (/依次点击|请点击/.test(txt)) type = 'icon';
    return { present: true, type, text: txt };
  });
}

const fs = require('fs');
const path = require('path');

// 人工点选模式（AI 不自动处理验证码）：
// 浏览器以有头模式运行，验证码出现时窗口直接弹在用户屏幕上，由用户亲自点选。
// 脚本暂停等待，把要求文本写入 /tmp/CAPTCHA_WAITING.json（status=waiting），
// 轮询检测验证码是否消失（用户点完后页面会自动移除/隐藏验证层），消失即视为通过并继续。
// 若等待期间验证题自动换题，会更新 waiting 文件里的 req，方便用户知悉新题。
const WAITING_FILE = '/tmp/CAPTCHA_WAITING.json';

async function getCaptchaReq(page){
  return await page.evaluate(() => {
    const bar = document.querySelector('.verify-bar-area');
    return bar ? (bar.innerText || '').replace(/\s+/g, ' ').trim() : '';
  });
}
async function solveIconClick(page, mid, attempt){
  let req = await getCaptchaReq(page);
  // 写入等待状态：所有验证均由用户人工完成，脚本只暂停等待，不自动识别/点击
  fs.writeFileSync(WAITING_FILE, JSON.stringify({
    market: mid, attempt, req, status: 'waiting', ts: Date.now(),
    msg: `请在屏幕上的 Edge 浏览器窗口中亲自处理验证码「${req}」（拖动滑块或按顺序点选）。处理完成后脚本会自动检测并通过。`
  }, null, 2));
  process.stderr.write(`market ${mid}: ⏸ 验证码出现「${req}」，等待人工处理…\n`);
  const deadline = Date.now() + 10 * 60 * 1000; // 最多等 10 分钟
  let lastReq = req;
  while (Date.now() < deadline) {
    await sleep(2000);
    const cap = await detectCaptcha(page);
    if (!cap.present) {
      fs.writeFileSync(WAITING_FILE, JSON.stringify({
        market: mid, attempt, req: lastReq, status: 'solved', ts: Date.now(),
        msg: '✓ 已检测到验证码消失，脚本继续。'
      }, null, 2));
      process.stderr.write(`market ${mid}: ✓ 检测到验证码已消失，继续抓取\n`);
      return true;
    }
    const r2 = await getCaptchaReq(page);
    if (r2 && r2 !== lastReq) {
      lastReq = r2;
      fs.writeFileSync(WAITING_FILE, JSON.stringify({
        market: mid, attempt, req: r2, status: 'waiting', ts: Date.now(),
        msg: `验证码已换题，请人工处理「${r2}」`
      }, null, 2));
      process.stderr.write(`market ${mid}: 验证码换题 -> 「${r2}」\n`);
    }
  }
  fs.writeFileSync(WAITING_FILE, JSON.stringify({ market: mid, attempt, req: lastReq, status: 'timeout', ts: Date.now() }, null, 2));
  process.stderr.write(`market ${mid}: 等待人工操作超时（10分钟）\n`);
  return false;
}

// 按商品名去重（同名取首个）
function dedup(rows){
  const seen = new Set();
  const out = [];
  for (const r of rows) {
    if (seen.has(r.name)) continue;
    seen.add(r.name);
    out.push(r);
  }
  return out;
}

// 耐心等待内容出现：验证码通过后会自动重载，期间可能再次弹验证。
// 轮询：遇到验证码就暂停交由用户人工处理，拿到商品行才返回，最多等 totalMs。
// 不「重新跳转页面」——此前正是重新跳转不断触发新验证码，造成「通过还不断弹」。
async function waitForContent(page, mid, totalMs){
  const deadline = Date.now() + (totalMs || 45000);
  let lastReq = '';
  // 智能稳定等待：21food 先显示"页面加载中..."再渲染验证码或商品。
  // 等待页面进入可操作状态（验证码可见 或 有商品行），而非盲等固定秒数。
  await page.evaluate(async () => {
    // 在浏览器内轮询：直到 .verify-bar-area 可见 或 出现商品行
    const start = Date.now();
    while (Date.now() - start < 15000) {
      const bar = document.querySelector('.verify-bar-area');
      if (bar && bar.offsetParent !== null) return; // 验证码已渲染
      const items = document.querySelectorAll('ul li a.opu_l4');
      if (items.length > 3) return; // 商品已加载
      await new Promise(r => setTimeout(r, 500));
    }
  });
  while (Date.now() < deadline) {
    const cap = await detectCaptcha(page);
    if (cap.present) {
      // 所有类型验证码（滑块/图标）一律交由用户人工处理，脚本不自动操作
      await solveIconClick(page, mid, 0);
      lastReq = cap.text;
      continue;
    }
    const rows = await extractWithRetry(page);
    if (rows && rows.length) return rows;
    await sleep(2000);
  }
  if (lastReq) process.stderr.write(`waitForContent ${mid}: 超时仍未拿到数据（最后验证要求「${lastReq}」）\n`);
  return [];
}

async function scrapeMarket(browser, mid){
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });
  await page.setUserAgent(UA);
  const out = [];
  const marketDeadline = Date.now() + 6 * 60 * 1000; // 单市场最多 6 分钟，避免卡死
  const remain = () => Math.max(5000, marketDeadline - Date.now());
  try {
    await page.goto(`${BASE}${mid}.html`, { waitUntil: 'networkidle2', timeout: 45000 });
    // 首屏：耐心等商品出现（期间若再弹验证会自动继续解，不再重新跳转）
    let rows = await waitForContent(page, mid, remain());
    out.push(...rows);
    process.stderr.write(`market ${mid} 首屏: ${rows.length} rows\n`);
    if (!rows.length) { return dedup(out); }
    // 解析分页末页
    let lastPage = 1;
    try {
      lastPage = await page.evaluate(() => {
        const html = document.body.innerHTML;
        const m = html.match(/market\/\d+-p(\d+)\.html/g);
        if (!m) return 1;
        return Math.max(...m.map(x => parseInt(x.match(/p(\d+)/)[1], 10)));
      });
    } catch (e) {}
    const pages = Math.min(lastPage, MAX_PAGES);
    for (let p = 2; p <= pages; p++) {
      if (Date.now() > marketDeadline) break;
      try {
        await page.goto(`${BASE}${mid}-p${p}.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
        const r2 = await waitForContent(page, mid, remain());
        out.push(...r2);
      } catch (e) { /* 单页失败跳过 */ }
    }
  } catch (e) {
    process.stderr.write(`market ${mid} error: ${e.message}\n`);
  } finally {
    await page.close();
  }
  return dedup(out);
}

(async () => {
  const ids = process.argv.slice(2);
  if (!ids.length) { console.error('usage: node beijing_scraper.js <marketId> ...'); process.exit(2); }
  // 清理上次异常退出残留的 SingletonLock，避免「user data directory is already in use」
  try {
    for (const f of ['SingletonLock', 'SingletonCookie', 'SingletonSocket']) {
      const lp = path.join(PROFILE, f);
      if (fs.existsSync(lp)) fs.unlinkSync(lp);
    }
  } catch (e) {}
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: false, // 有头模式：浏览器窗口会直接弹在用户屏幕上，便于人工点选验证码
    userDataDir: PROFILE, // 持久化档案：保留通过验证后的信任 cookie，避免反复弹出验证码
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--window-size=1280,900']
  });
  const result = {};
  try {
    for (let i = 0; i < ids.length; i++) {
      const mid = ids[i];
      if (i) await sleep(2500); // 市场间间隔，降低被风控概率
      result[mid] = await scrapeMarket(browser, mid);
      process.stderr.write(`market ${mid}: ${result[mid].length} rows\n`);
    }
  } finally {
    await browser.close();
  }
  process.stdout.write(JSON.stringify(result, null, 2));
})().catch(e => { process.stderr.write('FATAL ' + e.message + '\n'); process.exit(1); });
