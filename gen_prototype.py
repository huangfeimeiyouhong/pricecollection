# -*- coding: utf-8 -*-
"""生成价格采集前端 + 初始化快照。
- 写 price-collector.html（API 驱动：启动时 GET /api/data，更新时 POST /api/update）
- 调用 collect.seed() 用已缓存真实数据生成厦门 2026-07-24 初始快照（不联网）
真实抓取由 server.py 的 /api/update 完成（collect.update）。
"""
import os
import collect

ROOT = os.path.dirname(__file__)

TPL = '''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>价格采集 · 多平台比价（菜亿箩/厦门发改委/闽南果蔬）</title><style>
:root{--green:#07c160;--blue:#1989fa;--orange:#ff9f43;--bg:#f5f6f8;--card:#fff;--line:#ebeef5;--text:#1f2329;--sub:#8a8f99;}
*{box-sizing:border-box;margin:0;padding:0;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;}
body{background:var(--bg);color:var(--text);font-size:14px;padding:16px;max-width:1180px;margin:0 auto;}
.topbar h1{font-size:20px}.topbar .hint{color:var(--sub);font-size:12px;margin-top:4px;line-height:1.5;}
.controls{display:flex;gap:14px;align-items:flex-end;flex-wrap:wrap;background:var(--card);border-radius:10px;padding:12px 14px;margin:12px 0;box-shadow:0 1px 3px rgba(0,0,0,.04);}
.ctl{display:flex;flex-direction:column;gap:4px;}.ctl label{font-size:12px;color:var(--sub);}
.ctl select{border:1px solid var(--line);border-radius:8px;padding:7px 10px;font-size:13px;outline:none;min-width:130px;background:#fff;}
.ctl select:focus{border-color:var(--green);}.ctl select:disabled{color:var(--sub);background:#fafafa;}
.btn-update{border:1px solid var(--green);background:#fff;color:var(--green);border-radius:8px;padding:8px 16px;font-size:13px;cursor:pointer;font-weight:600;align-self:flex-end;min-width:96px;position:relative;}
.btn-update:hover{background:#f0fbf4;}.btn-update:disabled{opacity:.6;cursor:default;}
.btn-update.loading{color:transparent;}.btn-update.loading::after{content:'';position:absolute;left:50%;top:50%;width:14px;height:14px;margin:-7px 0 0 -7px;border:2px solid var(--green);border-top-color:transparent;border-radius:50%;animation:spin .7s linear infinite;}
@keyframes spin{to{transform:rotate(360deg);}}
.summary{display:flex;gap:12px;margin:14px 0;flex-wrap:wrap;}
.stat{flex:1;min-width:120px;background:var(--card);border-radius:10px;padding:12px 14px;box-shadow:0 1px 3px rgba(0,0,0,.04);}
.stat .n{font-size:22px;font-weight:600}.stat .l{color:var(--sub);font-size:12px;margin-top:2px;}
.filters{background:var(--card);border-radius:10px;padding:12px 14px;margin-bottom:14px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;}
.filters input,.filters select{border:1px solid var(--line);border-radius:8px;padding:7px 10px;font-size:13px;outline:none;}
.filters input:focus,.filters select:focus{border-color:var(--green);}
.chips{display:flex;gap:8px;flex-wrap:wrap;}.chip{border:1px solid var(--line);border-radius:16px;padding:5px 12px;cursor:pointer;font-size:13px;user-select:none;background:#fff;}
.chip.on{background:var(--green);color:#fff;border-color:var(--green);}
.sec-title{font-size:15px;font-weight:600;margin:18px 4px 10px;display:flex;align-items:center;gap:8px;}
.sec-title .tag{font-size:12px;font-weight:400;color:#fff;background:#ff9f43;border-radius:10px;padding:1px 8px;}
.acc{border:1px solid var(--line);border-radius:10px;background:var(--card);margin-bottom:8px;overflow:hidden;}
.acc-head{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;cursor:pointer;}
.acc-head:hover{background:#fafafa;}.acc-head .nm{font-weight:600;}.acc-head .cat{color:var(--sub);font-size:12px;margin-left:8px;}
.arrow{transition:transform .2s;color:var(--sub);}.acc.open .arrow{transform:rotate(90deg);}
.acc-body{display:none;border-top:1px solid var(--line);padding:12px 14px;}.acc.open .acc-body{display:block;}
.pcards{display:flex;gap:10px;flex-wrap:wrap;}
.pcard{border:1px solid var(--line);border-radius:10px;padding:10px 12px;min-width:180px;flex:1;position:relative;}
.pcard.best{border-color:var(--green);background:#f0fbf4;}.pcard.nodata{background:#fafafa;color:var(--sub);}
.pcard .plat{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--sub);}
.dot{width:8px;height:8px;border-radius:50%;}.pcard .pr{font-size:20px;font-weight:700;margin:4px 0;}
.pcard .pr .u{font-size:12px;font-weight:400;color:var(--sub);}.pcard .meta{font-size:12px;color:var(--sub);}
.badge{font-size:11px;padding:1px 7px;border-radius:8px;}.b-ok{background:#e8f8ee;color:#07a050;}.badge.best{background:var(--green);color:#fff;}
.pending-item{border:1px dashed #ffb870;background:#fffaf3;border-radius:10px;padding:12px 14px;margin-bottom:10px;}
.pending-item .row1{display:flex;align-items:center;justify-content:space-between;gap:10px;}
.pending-item .pname{font-weight:600;}.pending-item .src{color:var(--sub);font-size:12px;}
.sug{display:flex;align-items:center;gap:10px;background:#fff;border:1px solid var(--line);border-radius:8px;padding:7px 10px;cursor:pointer;margin-top:6px;}
.sug:hover{border-color:var(--blue);background:#f5faff;}.sug .sc{font-size:11px;padding:1px 6px;border-radius:6px;}
.sc-h{background:#e8f8ee;color:#07a050;}.sc-m{background:#fff3e0;color:#e08a00;}.sc-l{background:#f0f0f0;color:#888;}
.sug .act{margin-left:auto;color:var(--blue);font-size:12px;}
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#323233;color:#fff;padding:10px 18px;border-radius:8px;font-size:13px;opacity:0;transition:opacity .25s;pointer-events:none;max-width:90vw;text-align:center;}
.toast.show{opacity:1;}.empty{color:var(--sub);padding:20px;text-align:center;}
.note{font-size:12px;color:var(--sub);background:#fff;border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin:0 0 14px;line-height:1.7;}
.note b{color:var(--text);}
</style></head><body>
<div class="topbar"><div><h1>价格采集 · 多平台比价</h1><div class="hint" id="hint">加载中…</div></div></div>
<div class="controls"><div class="ctl"><label>城市</label><select id="fCity"></select></div><div class="ctl"><label>数据日期</label><select id="fDate"></select></div><button id="btnUpdate" class="btn-update">更新数据</button></div>
<div class="summary"><div class="stat"><div class="n" id="s-plat">0</div><div class="l">接入平台</div></div><div class="stat"><div class="n" id="s-prod">0</div><div class="l">基准商品</div></div><div class="stat"><div class="n" id="s-ok">0</div><div class="l">已对齐</div></div><div class="stat"><div class="n" style="color:#ff9f43" id="s-pend">0</div><div class="l">待映射</div></div></div>
<div class="note">映射引擎自动对齐：归一化同名→自动对齐；同义词库（上海青↔大青菜、马铃薯↔土豆、番茄↔西红柿、菜椒↔青椒、老姜↔生姜、鲜鸡蛋↔鸡蛋，<b>双向匹配</b>）→高置信建议；其余进入「待映射 / 人工校正」（菜亿箩确有该商品但名称与基准库不一致，点建议即对齐）。闽南果蔬原始元/公斤已÷2为元/斤（卡片内标注原始价）。点击「更新数据」会<b>实时抓取</b>所选城市各平台当日价格并落盘，日期选择器可回看历史快照。</div>
<div class="filters"><div class="chips" id="platChips"></div><select id="fCat"><option value="">全部分类</option></select><input id="fKw" placeholder="搜索商品名称…" style="width:180px"></div>
<div class="sec-title">商品比价 <span class="tag" id="cntTag">0</span></div><div id="list"></div>
<div class="sec-title">待映射 / 人工校正 <span class="tag" id="pendTag">0</span></div><div id="pending"></div>
<div class="toast" id="toast"></div>
<script>
const $=s=>document.querySelector(s);
let DATA=null;let currentCity=null;let currentDate=null;let activePlats=new Set();
function platformsOfCity(c){return DATA.platforms.filter(p=>p.city===c);}
function cityName(c){const x=DATA.cities.find(z=>z.id===c);return x?x.name:c;}
function datesOfCity(c){return (DATA.dates&&DATA.dates[c])||[];}
function snap(){return (DATA.snaps[currentCity]&&DATA.snaps[currentCity][currentDate])||null;}
function snapDemo(d){return !!(DATA.snaps[currentCity][d]&&DATA.snaps[currentCity][d].demo);}
function buildCityOptions(){const sel=$('#fCity');sel.innerHTML='';DATA.cities.forEach(c=>{const o=document.createElement('option');o.value=c.id;o.textContent=c.name;sel.appendChild(o);});sel.value=currentCity;sel.onchange=()=>{currentCity=sel.value;currentDate=datesOfCity(currentCity)[0]||null;buildDateOptions();buildPlatChips();render();};}
function buildDateOptions(){const sel=$('#fDate');sel.innerHTML='';const ds=datesOfCity(currentCity);if(!ds.length){const o=document.createElement('option');o.value='';o.textContent='无数据';sel.appendChild(o);sel.disabled=true;return;}sel.disabled=false;ds.forEach(d=>{const o=document.createElement('option');o.value=d;o.textContent=d+(snapDemo(d)?'（示例）':'');sel.appendChild(o);});sel.value=currentDate||ds[0];sel.onchange=()=>{currentDate=sel.value;render();};}
function buildPlatChips(){const box=$('#platChips');box.innerHTML='';const ps=platformsOfCity(currentCity);activePlats=new Set(ps.map(p=>p.id));ps.forEach(p=>{const c=document.createElement('div');c.className='chip on';c.textContent=p.name;c.onclick=()=>{c.classList.toggle('on');if(activePlats.has(p.id))activePlats.delete(p.id);else activePlats.add(p.id);render();};box.appendChild(c);});}
function updateHint(){const ps=platformsOfCity(currentCity);const names=ps.map(p=>p.name).join('、')||'（暂无接入平台）';const d=currentDate?('｜ 数据日期：'+currentDate+(snapDemo(currentDate)?'（示例）':'')):'｜ 暂无数据';$('#hint').innerHTML='当前城市：<b>'+cityName(currentCity)+'</b> ｜ 接入平台：'+names+d+'。单位统一为元/斤。';}
const SYN={'上海青':'大青菜','马铃薯':'土豆','番茄':'西红柿','菜椒':'青椒','老姜':'生姜','鲜鸡蛋':'鸡蛋'};
function toast(msg){const t=$('#toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2600);}
function mapPendingTo(i){const dt=snap();if(!dt)return;const r=dt.pending[i];if(!r)return;const t=dt.canonical.find(c=>c.name===r.target);if(!t){toast('基准商品不存在');return;}if(t.prices.some(pr=>pr.pid===r.pid)){dt.pending.splice(i,1);render();toast('「'+r.target+'」已含菜亿箩价，标记已校正');return;}t.prices.push({pid:r.pid,price:r.price,time:currentDate+' 13:58',mapped:'自动(同义词)'});dt.pending.splice(i,1);render();toast('已对齐：菜亿箩「'+r.pname+'」 → 基准「'+r.target+'」');}
async function doUpdate(){const btn=$('#btnUpdate');if(btn.disabled)return;const old=btn.textContent;btn.disabled=true;btn.textContent='更新中…';btn.classList.add('loading');
 try{const resp=await fetch('/api/update?city='+currentCity,{method:'POST'});const d=await resp.json();if(d.error){toast('更新失败：'+d.error);}else{DATA=d;currentDate=datesOfCity(currentCity)[0]||null;buildDateOptions();buildPlatChips();render();const m=(DATA.snaps[currentCity][currentDate]&&DATA.snaps[currentCity][currentDate]._msg)||'更新完成';toast(m+' ｜ 数据日期：'+(currentDate||'无'));}}
 catch(e){toast('更新请求失败：'+e.message);}finally{btn.disabled=false;btn.textContent=old;btn.classList.remove('loading');}}
$('#btnUpdate').onclick=doUpdate;
function render(){
 const dt=snap();const catSel=$('#fCat');const prev=catSel.value;catSel.innerHTML='<option value="">全部分类</option>';
 if(dt){dt.cats.forEach(c=>{const o=document.createElement('option');o.value=c;o.textContent=c;catSel.appendChild(o);});if([...catSel.options].some(o=>o.value===prev))catSel.value=prev;}
 const kw=catSel.value!==undefined?$('#fKw').value.trim():'';const cat=catSel.value;
 updateHint();
 if(!dt){
  $('#list').innerHTML='<div class="empty">该城市暂未配置平台或暂无数据存档。请在 collect.py 的 CITY_PLATFORMS 中为其添加平台，并运行更新（POST /api/update）。</div>';
  $('#pending').innerHTML='';$('#s-plat').textContent=platformsOfCity(currentCity).length;
  $('#s-prod').textContent=0;$('#s-ok').textContent=0;$('#s-pend').textContent=0;$('#cntTag').textContent=0;$('#pendTag').textContent=0;return;
 }
 const cityPids=new Set(platformsOfCity(currentCity).map(p=>p.id));
 const inCity=c=>c.prices.some(pr=>cityPids.has(pr.pid));
 let list=dt.canonical.filter(c=>{if(!inCity(c))return false;if(cat&&c.cat1!==cat)return false;if(kw&&c.name.indexOf(kw)<0)return false;return true;});
 const cityCanon=dt.canonical.filter(inCity);
 $('#s-plat').textContent=platformsOfCity(currentCity).length;$('#s-prod').textContent=cityCanon.length;$('#s-ok').textContent=cityCanon.filter(c=>c.prices.some(pr=>cityPids.has(pr.pid))).length;$('#s-pend').textContent=dt.pending.filter(r=>cityPids.has(r.pid)).length;$('#cntTag').textContent=list.length;$('#pendTag').textContent=dt.pending.filter(r=>cityPids.has(r.pid)).length;
 const box=$('#list');box.innerHTML='';if(!list.length){box.innerHTML='<div class="empty">无匹配商品</div>';}
 list.forEach(c=>{const vis=c.prices.filter(pr=>activePlats.has(pr.pid));const prices=vis.map(pr=>pr.price).filter(x=>x!=null&&x!=='—');const minP=prices.length?Math.min(...prices):null;
  const div=document.createElement('div');div.className='acc';
  const ph=vis.length?vis.map(pr=>{const best=pr.price===minP&&minP!=null?'best':'';const pi=DATA.platforms.find(p=>p.id===pr.pid);const tag=pr.mapped?' <span class="badge b-ok">'+pr.mapped+'</span>':'';const raw=pr.kg?` <span class="meta">原始 ${pr.kg}元/公斤</span>`:'';
   return `<div class="pcard ${best}"><div class="plat"><span class="dot" style="background:${pi.color}"></span>${pi.name} ${best?'<span class="badge best">最低价</span>':''}${tag}</div><div class="pr">¥${pr.price}<span class="u">/斤</span></div><div class="meta">${pr.spec||''} ｜ 采集:${pr.time}</div>${raw}</div>`;}).join(''):'<div class="pcard nodata">该平台未采集此商品</div>';
  const diff=prices.length>1?`价差 ¥${(Math.max(...prices)-minP).toFixed(2)}/斤`:'';
  div.innerHTML=`<div class="acc-head"><div><span class="nm">${c.name}</span><span class="cat">${c.cat1} › ${c.cat2}</span></div><div style="display:flex;align-items:center;gap:10px"><span class="cat">${diff}</span><span class="arrow">▶</span></div></div><div class="acc-body"><div class="pcards">${ph}</div></div>`;
  div.querySelector('.acc-head').onclick=()=>div.classList.toggle('open');box.appendChild(div);});
 const pb=$('#pending');pb.innerHTML='';if(!dt.pending.some(r=>cityPids.has(r.pid))){pb.innerHTML='<div class="empty">全部已对齐 🎉</div>';}
 dt.pending.forEach((r,i)=>{if(!cityPids.has(r.pid))return;const pi=DATA.platforms.find(p=>p.id===r.pid);const div=document.createElement('div');div.className='pending-item';
  div.innerHTML=`<div class="row1"><div><span class="dot" style="background:${pi.color};display:inline-block"></span> <span class="pname">菜亿箩「${r.pname}」</span> <span class="src">（¥${r.price}/斤）名称与基准库不一致</span></div></div><div class="sug" onclick="mapPendingTo(${i})"><span class="dot" style="background:var(--blue)"></span><b>建议对齐 → 基准「${r.target}」</b><span class="sc sc-h">同义词 95%</span><span class="act">点击对齐 →</span></div></div>`;pb.appendChild(div);});}
async function boot(){try{const resp=await fetch('/api/data');DATA=await resp.json();currentCity=DATA.cities[0].id;currentDate=datesOfCity(currentCity)[0]||null;buildCityOptions();buildDateOptions();buildPlatChips();render();}catch(e){document.getElementById('hint').textContent='加载数据失败：'+e.message;}}
boot();
</script></body></html>'''

out = os.path.join(ROOT, "price-collector.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(TPL)
print("前端已生成:", out, len(TPL), "字节")

# 初始化快照（用缓存真实数据；已存在则跳过，避免覆盖真实更新结果）
collect.seed()
