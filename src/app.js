'use strict';
/* JKAM Social — a Vista Social–style social media management tool.
   Static app, all data persisted in localStorage (demo; no real network APIs). */

const NETS = {
  linkedin:{n:'LinkedIn',c:'#0a66c2',l:'in',max:3000},
  x:{n:'X',c:'#111',l:'X',max:280},
  facebook:{n:'Facebook',c:'#1877f2',l:'f',max:63206},
  instagram:{n:'Instagram',c:'#c13584',l:'ig',max:2200},
  youtube:{n:'YouTube',c:'#e00',l:'▶',max:5000},
  tiktok:{n:'TikTok',c:'#010101',l:'♪',max:2200},
  threads:{n:'Threads',c:'#333',l:'@',max:500},
};
const BEST = {linkedin:[9,12],x:[8,17],facebook:[13,15],instagram:[11,19],youtube:[15,17],tiktok:[19,21],threads:[12,20]};
const RISKY = [/guarantee[ds]?/i,/risk[- ]free/i,/can'?t lose/i,/no risk/i,/sure thing/i,/double your money/i,/get rich/i,/100% (return|profit)/i];
const DISCLAIMER = '\n\nInvesting involves risk, including loss of principal. Past performance does not guarantee future results. Not investment advice.';
const KEY = 'jkam-social-v1';
const $ = (s, r=document) => r.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const uid = () => Math.random().toString(36).slice(2, 10);
const fmt = n => n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e3 ? (n/1e3).toFixed(1)+'k' : String(n);
const dt = d => new Date(d).toLocaleString([], {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
const toLocalInput = d => { const x = new Date(d); x.setMinutes(x.getMinutes()-x.getTimezoneOffset()); return x.toISOString().slice(0,16); };

/* ---------- state ---------- */
function seed() {
  const day = 864e5, now = Date.now();
  const at = (d, h) => { const x = new Date(now + d*day); x.setHours(h,0,0,0); return x.toISOString(); };
  const profiles = [
    {id:'p1',net:'linkedin',name:'JKAM Investments',handle:'company/jkam',followers:12480},
    {id:'p2',net:'x',name:'JKAM Investments',handle:'@jkaminvest',followers:8310},
    {id:'p3',net:'facebook',name:'JKAM Investments',handle:'jkaminvestments',followers:5920},
    {id:'p4',net:'instagram',name:'JKAM Investments',handle:'@jkaminvestments',followers:7140},
    {id:'p5',net:'youtube',name:'JKAM Insights',handle:'@jkaminsights',followers:3260},
  ].map(p => ({...p, connected:true}));
  const posts = [
    {text:'Q3 market recap: what moved portfolios and what we are watching into year-end. Full commentary on our site.',nets:['p1','p2'],status:'published',date:at(-3,9),author:'Admin'},
    {text:'Diversification 101: why spreading exposure across asset classes matters.'+DISCLAIMER,nets:['p1','p3','p4'],status:'published',date:at(-1,12),author:'Editor'},
    {text:'Join our live Q&A on retirement planning this Thursday at 2pm ET.',nets:['p1','p2','p3'],status:'scheduled',date:at(1,14),author:'Admin'},
    {text:'Meet the JKAM research team — a look behind the scenes.',nets:['p4','p5'],status:'scheduled',date:at(3,11),author:'Editor'},
    {text:'Interest rates explained in 60 seconds.',nets:['p5','p4'],status:'pending',date:at(5,10),author:'Editor'},
    {text:'Draft: year-end tax-loss harvesting checklist',nets:['p1'],status:'draft',date:at(8,9),author:'Editor'},
  ].map(p => ({id:uid(), media:'', tags:[], ...p}));
  const inbox = [
    {id:uid(),pid:'p1',from:'Dana R.',text:'Do you offer separately managed accounts for under $250k?',time:at(0,-2),read:false,replies:[]},
    {id:uid(),pid:'p2',from:'@marketwatcher',text:'Great thread on rate cuts. Any thoughts on duration risk?',time:at(-1,18),read:false,replies:[]},
    {id:uid(),pid:'p3',from:'Luis M.',text:'How do I schedule a consultation?',time:at(-2,10),read:true,replies:[{me:true,text:'Hi Luis! You can book at our website or DM us a good time.'}]},
    {id:uid(),pid:'p4',from:'finlit_jane',text:'Loved the diversification post!',time:at(-1,13),read:true,replies:[]},
  ];
  return {profiles, posts, inbox, role:'Admin', compliance:true};
}
let S;
try { S = JSON.parse(localStorage.getItem(KEY)); } catch { S = null; }
if (!S) S = seed();
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch {} };
const prof = id => S.profiles.find(p => p.id === id);
const isAdmin = () => S.role === 'Admin';

function toast(m) { const t = $('#toast'); t.textContent = m; t.classList.remove('hidden'); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.add('hidden'), 2400); }
const badge = id => { const p = prof(id); if (!p) return ''; const n = NETS[p.net]; return `<span class="net" style="background:${n.c}" title="${esc(n.n)} · ${esc(p.handle)}">${n.l}</span>`; };

/* deterministic pseudo-random for analytics */
function rng(seedStr) { let h = 2166136261; for (const c of seedStr) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return () => (h = Math.imul(h ^ h >>> 15, 2246822507) >>> 0, (h % 10000) / 10000); }
function series(p, days) {
  const r = rng(p.id + p.net); let f = p.followers - days*6; const out = [];
  for (let i = 0; i < days; i++) { f += Math.round(r()*14 - 2); const imp = Math.round(f*(0.4+r()*0.5)); out.push({f, imp, eng: Math.round(imp*(0.02+r()*0.04))}); }
  return out;
}

/* auto-publish scheduled posts whose time has come */
function tick() {
  let ch = false;
  S.posts.forEach(p => { if (p.status === 'scheduled' && new Date(p.date) <= new Date()) { p.status = 'published'; ch = true; } });
  if (ch) { save(); if (['#/dashboard','#/calendar','#/queue'].includes(location.hash)) render(); }
}
setInterval(tick, 30000);

/* ---------- routing ---------- */
const ROUTES = {
  dashboard:['🏠','Dashboard',vDashboard], calendar:['📅','Calendar',vCalendar], queue:['📝','Content & Approvals',vQueue],
  inbox:['💬','Inbox',vInbox], analytics:['📈','Analytics',vAnalytics], profiles:['🔗','Social Profiles',vProfiles], settings:['⚙️','Settings',vSettings],
};
function render() {
  tick();
  const k = (location.hash.slice(2) || 'dashboard'), r = ROUTES[k] || ROUTES.dashboard;
  $('#nav').innerHTML = Object.entries(ROUTES).map(([id,[i,t]]) => {
    const badgeN = id==='inbox' ? S.inbox.filter(m=>!m.read).length : id==='queue' ? S.posts.filter(p=>p.status==='pending').length : 0;
    return `<a href="#/${id}" class="${id===(ROUTES[k]?k:'dashboard')?'active':''}">${i} ${t}${badgeN?` <span class="pill" style="margin-left:auto">${badgeN}</span>`:''}</a>`;
  }).join('');
  $('#title').textContent = r[1];
  $('#role').value = S.role;
  $('#view').innerHTML = r[2]();
  if (r[3]) r[3]();
  wire();
}
window.addEventListener('hashchange', render);

/* ---------- views ---------- */
function vDashboard() {
  const pub = S.posts.filter(p=>p.status==='published').length, sch = S.posts.filter(p=>p.status==='scheduled').length;
  const pend = S.posts.filter(p=>p.status==='pending').length, unread = S.inbox.filter(m=>!m.read).length;
  const fol = S.profiles.reduce((a,p)=>a+p.followers,0);
  const upcoming = S.posts.filter(p=>['scheduled','pending','approved'].includes(p.status)).sort((a,b)=>a.date.localeCompare(b.date)).slice(0,5);
  return `<div class="grid g4">
    ${[['Total followers',fmt(fol),'+2.4% vs last 30d'],['Published posts',pub,''],['Scheduled',sch,''],['Awaiting approval',pend,''],['Unread messages',unread,'']]
      .map(([a,b,c])=>`<div class="card kpi"><span>${a}</span><b>${b}</b><span class="up">${c}</span></div>`).join('')}
  </div>
  <div class="grid g2" style="margin-top:16px">
    <div class="card"><h3>Upcoming posts</h3>${upcoming.length?`<table>${upcoming.map(p=>`<tr data-edit="${p.id}" style="cursor:pointer"><td>${p.nets.map(badge).join('')}</td><td>${esc(p.text.slice(0,70))}…</td><td>${dt(p.date)}</td><td><span class="pill ${p.status}">${p.status}</span></td></tr>`).join('')}</table>`:'<p class="count">Nothing queued.</p>'}</div>
    <div class="card"><h3>Followers — last 30 days</h3>${lineChart(combined(30,'f'))}</div>
  </div>
  <div class="card" style="margin-top:16px"><h3>Connected profiles</h3><div class="row">${S.profiles.map(p=>`<span class="sel on">${badge(p.id)} ${esc(p.name)} <small class="count">&nbsp;${fmt(p.followers)}</small></span>`).join('')}</div></div>`;
}
function combined(days, key) {
  const all = S.profiles.filter(p=>p.connected).map(p=>series(p,days));
  return Array.from({length:days}, (_,i)=>all.reduce((a,s)=>a+s[i][key],0));
}
function lineChart(vals, color='#0b5fff') {
  const W=520,H=170,P=28, mn=Math.min(...vals), mx=Math.max(...vals), span=(mx-mn)||1;
  const pts = vals.map((v,i)=>[P+i*(W-P*2)/(vals.length-1), H-P-(v-mn)/span*(H-P*2)]);
  const path = pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+','+p[1].toFixed(1)).join('');
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Trend chart"><path d="${path}L${pts.at(-1)[0]},${H-P}L${P},${H-P}Z" fill="${color}22"/><path d="${path}" fill="none" stroke="${color}" stroke-width="2"/>
  <text x="2" y="${P}">${fmt(mx)}</text><text x="2" y="${H-P}">${fmt(mn)}</text><text x="${P}" y="${H-6}">30d ago</text><text x="${W-P-22}" y="${H-6}">today</text></svg>`;
}
function barChart(items, color='#0b5fff') {
  const mx = Math.max(...items.map(i=>i[1]),1);
  return items.map(([l,v])=>`<div class="row" style="margin:6px 0"><span style="width:90px">${esc(l)}</span><div style="flex:1;background:#eef1f8;border-radius:6px"><div style="width:${v/mx*100}%;background:${color};height:14px;border-radius:6px"></div></div><b style="width:60px;text-align:right">${fmt(v)}</b></div>`).join('');
}

let calMonth = new Date(); calMonth.setDate(1);
function vCalendar() {
  const y=calMonth.getFullYear(), m=calMonth.getMonth(), first=new Date(y,m,1).getDay(), dim=new Date(y,m+1,0).getDate();
  let cells = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d=>`<div class="h">${d}</div>`).join('');
  const total = Math.ceil((first+dim)/7)*7, today = new Date().toDateString();
  for (let i=0;i<total;i++) {
    const d = new Date(y,m,1-first+i), off = d.getMonth()!==m;
    const ps = S.posts.filter(p=>new Date(p.date).toDateString()===d.toDateString()).sort((a,b)=>a.date.localeCompare(b.date));
    cells += `<div class="d ${off?'off':''} ${d.toDateString()===today?'today':''}" data-day="${d.toISOString()}"><span class="n">${d.getDate()}</span>
      ${ps.map(p=>`<span class="chip ${p.status}" draggable="true" data-drag="${p.id}" data-edit="${p.id}" title="${esc(p.text)}">${new Date(p.date).toLocaleTimeString([], {hour:'numeric',minute:'2-digit'})} ${esc(p.text.slice(0,30))}</span>`).join('')}</div>`;
  }
  return `<div class="row" style="margin-bottom:12px"><button class="btn" id="prev">‹</button><b style="min-width:150px;text-align:center">${calMonth.toLocaleString([], {month:'long',year:'numeric'})}</b><button class="btn" id="next">›</button><button class="btn" id="todayBtn">Today</button><span class="count">Click a day to create a post · drag posts to reschedule</span></div><div class="cal">${cells}</div>`;
}

let qTab = 'all';
function vQueue() {
  const tabs = ['all','draft','pending','approved','scheduled','published','rejected'];
  const list = S.posts.filter(p=>qTab==='all'||p.status===qTab).sort((a,b)=>b.date.localeCompare(a.date));
  return `<div class="tabs">${tabs.map(t=>`<button data-tab="${t}" class="${t===qTab?'on':''}">${t[0].toUpperCase()+t.slice(1)} (${S.posts.filter(p=>t==='all'||p.status===t).length})</button>`).join('')}</div>
  <div class="card"><table><tr><th>Networks</th><th>Content</th><th>When</th><th>Status</th><th>By</th><th></th></tr>
  ${list.map(p=>`<tr><td>${p.nets.map(badge).join('')}</td><td>${esc(p.text.slice(0,110))}${p.text.length>110?'…':''}</td><td>${dt(p.date)}</td><td><span class="pill ${p.status}">${p.status}</span></td><td>${esc(p.author)}</td>
  <td style="white-space:nowrap"><button class="btn sm" data-edit="${p.id}">Edit</button>
  ${p.status==='pending'?`<button class="btn sm" data-approve="${p.id}" ${isAdmin()?'':'disabled title="Admins only"'}>Approve</button><button class="btn sm danger" data-reject="${p.id}" ${isAdmin()?'':'disabled'}>Reject</button>`:''}
  ${p.status==='approved'?`<button class="btn sm" data-sched="${p.id}">Schedule</button>`:''}
  <button class="btn sm danger" data-del="${p.id}">✕</button></td></tr>`).join('')||'<tr><td colspan="6" class="count">No posts.</td></tr>'}</table></div>`;
}

let selMsg = null;
function vInbox() {
  const msgs = [...S.inbox].sort((a,b)=>b.time.localeCompare(a.time));
  if (!selMsg || !S.inbox.find(m=>m.id===selMsg)) selMsg = msgs[0]?.id;
  const m = S.inbox.find(x=>x.id===selMsg);
  return `<div class="inbox"><div class="card" style="padding:0;overflow:auto">${msgs.map(x=>`<div class="msg ${x.read?'':'unread'} ${x.id===selMsg?'on':''}" data-msg="${x.id}">${badge(x.pid)}<b>${esc(x.from)}</b><div class="count">${esc(x.text.slice(0,60))}</div></div>`).join('')}</div>
  <div class="card">${m?`<div class="row">${badge(m.pid)}<b>${esc(m.from)}</b><span class="count">${dt(m.time)}</span></div>
  <div class="bubble">${esc(m.text)}</div>${m.replies.map(r=>`<div class="bubble me">${esc(r.text)}</div>`).join('')}
  <div class="row" style="margin-top:12px"><input id="reply" style="flex:1" placeholder="Write a reply…"><button class="btn primary" id="sendReply">Reply</button></div>
  <div class="alert">Reminder: replies to investor inquiries must not include personalized investment advice.</div>`:'<p class="count">No messages.</p>'}</div></div>`;
}

let anDays = 30;
function vAnalytics() {
  const ps = S.profiles.filter(p=>p.connected);
  const sum = (p,k)=>series(p,anDays).reduce((a,s)=>a+s[k],0);
  const imp = ps.reduce((a,p)=>a+sum(p,'imp'),0), eng = ps.reduce((a,p)=>a+sum(p,'eng'),0);
  const top = S.posts.filter(p=>p.status==='published').map(p=>{const r=rng(p.id);return {p,imp:Math.round(r()*9000+800),eng:Math.round(r()*600+40)}}).sort((a,b)=>b.eng-a.eng);
  return `<div class="row" style="margin-bottom:12px"><select id="anDays">${[7,14,30,60].map(d=>`<option ${d===anDays?'selected':''} value="${d}">Last ${d} days</option>`).join('')}</select><button class="btn" id="exportCsv">Export CSV report</button></div>
  <div class="grid g4"><div class="card kpi"><span>Impressions</span><b>${fmt(imp)}</b></div><div class="card kpi"><span>Engagements</span><b>${fmt(eng)}</b></div><div class="card kpi"><span>Engagement rate</span><b>${(eng/imp*100).toFixed(2)}%</b></div><div class="card kpi"><span>Net follower growth</span><b class="up">+${combined(anDays,'f').at(-1)-combined(anDays,'f')[0]}</b></div></div>
  <div class="grid g2" style="margin-top:16px"><div class="card"><h3>Impressions trend</h3>${lineChart(combined(anDays,'imp'),'#7a3cff')}</div>
  <div class="card"><h3>Engagement by profile</h3>${barChart(ps.map(p=>[NETS[p.net].n,sum(p,'eng')]),'#12a150')}</div></div>
  <div class="card" style="margin-top:16px"><h3>Top published posts</h3><table><tr><th></th><th>Post</th><th>Impressions</th><th>Engagements</th></tr>${top.map(t=>`<tr><td>${t.p.nets.map(badge).join('')}</td><td>${esc(t.p.text.slice(0,80))}</td><td>${fmt(t.imp)}</td><td>${fmt(t.eng)}</td></tr>`).join('')||'<tr><td colspan="4" class="count">No published posts yet.</td></tr>'}</table></div>
  <p class="count">Demo metrics are simulated. Connect real network APIs to replace them.</p>`;
}

function vProfiles() {
  const avail = Object.keys(NETS).filter(n=>!S.profiles.find(p=>p.net===n));
  return `<div class="card"><table><tr><th>Network</th><th>Account</th><th>Followers</th><th>Status</th><th></th></tr>
  ${S.profiles.map(p=>`<tr><td>${badge(p.id)} ${NETS[p.net].n}</td><td>${esc(p.name)} <span class="count">${esc(p.handle)}</span></td><td>${fmt(p.followers)}</td><td><span class="pill ${p.connected?'approved':'draft'}">${p.connected?'connected':'disconnected'}</span></td>
  <td><button class="btn sm" data-toggle="${p.id}">${p.connected?'Disconnect':'Reconnect'}</button> <button class="btn sm danger" data-rmprof="${p.id}">Remove</button></td></tr>`).join('')}</table></div>
  <div class="card" style="margin-top:16px"><h3>Add profile</h3><div class="row"><select id="newNet">${Object.entries(NETS).map(([k,v])=>`<option value="${k}">${v.n}</option>`).join('')}</select><input id="newName" placeholder="Account name"><input id="newHandle" placeholder="@handle"><button class="btn primary" id="addProf">Connect</button></div>
  <p class="count">Demo: this records the profile locally. Real OAuth connections need a backend.</p></div>`;
}

function vSettings() {
  return `<div class="card" style="max-width:640px"><h3>Compliance</h3>
  <label class="row"><input type="checkbox" id="cmp" ${S.compliance?'checked':''}> Require admin approval before scheduling, and flag risky language (e.g. “guaranteed returns”).</label>
  <h3 style="margin-top:20px">Data</h3><div class="row"><button class="btn" id="exportJson">Export data (JSON)</button><button class="btn danger" id="resetBtn">Reset demo data</button></div></div>`;
}

/* ---------- composer ---------- */
function openComposer(post, day) {
  const base = post ? {...post, nets:[...post.nets]} : {id:null,text:'',nets:[],status:'draft',date:day||new Date(Date.now()+36e5).toISOString(),media:'',tags:[],author:S.role};
  const m = $('#modal');
  m.classList.remove('hidden');
  m.innerHTML = `<div class="dlg"><div class="row"><h2 style="margin:0">${post?'Edit post':'Create post'}</h2><div class="spacer"></div><button class="btn" id="cClose">✕</button></div>
  <div class="split" style="margin-top:12px"><div>
    <div class="col"><b>Profiles</b><div>${S.profiles.filter(p=>p.connected).map(p=>`<span class="sel ${base.nets.includes(p.id)?'on':''}" data-pick="${p.id}">${badge(p.id)} ${NETS[p.net].n}</span>`).join('')}</div></div>
    <div class="col"><b>Caption</b><textarea id="cText" rows="8" placeholder="Write your post…">${esc(base.text)}</textarea>
      <div class="row"><button class="btn sm" id="cDisc">＋ Disclaimer</button><button class="btn sm" id="cHash">＋ Hashtags</button><span id="cCounts" class="count"></span></div>
      <div id="cWarn"></div></div>
    <div class="col" style="margin-top:8px"><b>Media URL (optional)</b><input id="cMedia" value="${esc(base.media)}" placeholder="https://…/image.jpg"></div>
    <div class="row" style="margin-top:8px"><div class="col"><b>Schedule</b><input type="datetime-local" id="cDate" value="${toLocalInput(base.date)}"></div><button class="btn sm" id="cBest" style="margin-top:20px">★ Best time</button></div>
  </div><div><b>Preview</b><div id="cPrev" style="margin-top:6px"></div></div></div>
  <div class="row" style="margin-top:16px;justify-content:flex-end"><button class="btn" id="cDraft">Save draft</button>
  ${S.compliance&&!isAdmin()?'<button class="btn primary" id="cSubmit">Submit for approval</button>':'<button class="btn" id="cNow">Publish now</button><button class="btn primary" id="cSched">Schedule</button>'}</div></div>`;
  const st = {...base};
  const refresh = () => {
    st.text = $('#cText').value;
    const over = st.nets.map(id=>prof(id)).filter(p=>p && st.text.length>NETS[p.net].max);
    $('#cCounts').innerHTML = st.text.length+' chars'+st.nets.map(id=>{const p=prof(id),n=NETS[p.net];return ` · <span class="${st.text.length>n.max?'count bad':''}">${n.n} ${n.max-st.text.length}</span>`}).join('');
    const hits = RISKY.filter(r=>r.test(st.text));
    const noDisc = S.compliance && st.text.trim() && !/past performance|not investment advice|risk/i.test(st.text);
    $('#cWarn').innerHTML = (hits.length?`<div class="alert">⚠ Compliance: risky language detected (${hits.map(r=>esc(st.text.match(r)[0])).join(', ')}). Revise before submitting.</div>`:'')+(noDisc?'<div class="alert">Tip: no risk disclaimer found. Consider adding one.</div>':'')+(over.length?`<div class="alert">Over the limit for ${over.map(p=>NETS[p.net].n).join(', ')}.</div>`:'');
    $('#cPrev').innerHTML = st.nets.length ? st.nets.map(id=>{const p=prof(id);return `<div class="preview">${badge(id)}<b>${esc(p.name)}</b> <span class="count">${esc(p.handle)}</span>\n${esc(st.text.slice(0,NETS[p.net].max))||'<i class="count">Your caption…</i>'}${$('#cMedia').value?'<div class="img">🖼 media</div>':''}</div>`}).join('') : '<p class="count">Select a profile to preview.</p>';
    st.risky = hits.length>0; st.over = over.length>0;
  };
  const commit = status => {
    refresh();
    if (!st.nets.length) return toast('Pick at least one profile.');
    if (!st.text.trim()) return toast('Write a caption first.');
    if (status!=='draft' && st.over) return toast('Caption exceeds a network limit.');
    if (status!=='draft' && st.risky && S.compliance) return toast('Remove risky language first.');
    const date = new Date($('#cDate').value).toISOString();
    if (status==='scheduled' && new Date(date)<=new Date()) status='published';
    const rec = {id:base.id||uid(), text:st.text, nets:st.nets, status, date, media:$('#cMedia').value.trim(), tags:(st.text.match(/#\w+/g)||[]), author:base.author||S.role};
    const i = S.posts.findIndex(p=>p.id===rec.id); i>=0 ? S.posts[i]=rec : S.posts.push(rec);
    save(); closeModal(); render(); toast({draft:'Draft saved',pending:'Submitted for approval',scheduled:'Post scheduled',published:'Published (simulated)'}[status]);
  };
  m.onclick = e => {
    const t = e.target, pick = t.closest('[data-pick]');
    if (t===m || t.id==='cClose') return closeModal();
    if (pick) { const id=pick.dataset.pick; st.nets = st.nets.includes(id)?st.nets.filter(x=>x!==id):[...st.nets,id]; pick.classList.toggle('on'); refresh(); }
    else if (t.id==='cDisc') { $('#cText').value += DISCLAIMER; refresh(); }
    else if (t.id==='cHash') { $('#cText').value += '\n\n#investing #markets #wealthmanagement #JKAM'; refresh(); }
    else if (t.id==='cBest') { const n=st.nets[0]?prof(st.nets[0]).net:'linkedin'; const d=new Date(); d.setDate(d.getDate()+1); d.setHours(BEST[n][0],0,0,0); $('#cDate').value=toLocalInput(d); toast(`Best time for ${NETS[n].n}: ${BEST[n][0]}:00`); }
    else if (t.id==='cDraft') commit('draft');
    else if (t.id==='cSubmit') commit('pending');
    else if (t.id==='cSched') commit('scheduled');
    else if (t.id==='cNow') { $('#cDate').value = toLocalInput(new Date(Date.now()-6e4)); commit('scheduled'); }
  };
  m.oninput = refresh; refresh();
}
function closeModal() { const m=$('#modal'); m.classList.add('hidden'); m.innerHTML=''; }

/* ---------- events ---------- */
function download(name, text, type) { const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([text],{type})); a.download=name; a.click(); URL.revokeObjectURL(a.href); }
const setStatus = (id, s) => { const p=S.posts.find(x=>x.id===id); if (p) { p.status=s; save(); render(); } };
function wire() {
  const v = $('#view');
  v.querySelectorAll('[data-edit]').forEach(el => el.onclick = e => { e.stopPropagation(); openComposer(S.posts.find(p=>p.id===el.dataset.edit)); });
  v.querySelectorAll('[data-day]').forEach(el => {
    el.onclick = () => { const d=new Date(el.dataset.day); d.setHours(10,0,0,0); openComposer(null, d.toISOString()); };
    el.ondragover = e => { e.preventDefault(); el.classList.add('over'); };
    el.ondragleave = () => el.classList.remove('over');
    el.ondrop = e => { e.preventDefault(); const p=S.posts.find(x=>x.id===e.dataTransfer.getData('text/plain')); if (!p) return; const o=new Date(p.date), d=new Date(el.dataset.day); d.setHours(o.getHours(),o.getMinutes()); p.date=d.toISOString(); save(); render(); toast('Rescheduled'); };
  });
  v.querySelectorAll('[data-drag]').forEach(el => el.ondragstart = e => e.dataTransfer.setData('text/plain', el.dataset.drag));
  const on = (id, fn) => { const el=$('#'+id); if (el) el.onclick = fn; };
  on('prev',()=>{calMonth.setMonth(calMonth.getMonth()-1);render();}); on('next',()=>{calMonth.setMonth(calMonth.getMonth()+1);render();});
  on('todayBtn',()=>{calMonth=new Date();calMonth.setDate(1);render();});
  v.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{qTab=b.dataset.tab;render();});
  v.querySelectorAll('[data-approve]').forEach(b=>b.onclick=()=>setStatus(b.dataset.approve,'approved'));
  v.querySelectorAll('[data-reject]').forEach(b=>b.onclick=()=>setStatus(b.dataset.reject,'rejected'));
  v.querySelectorAll('[data-sched]').forEach(b=>b.onclick=()=>setStatus(b.dataset.sched,'scheduled'));
  v.querySelectorAll('[data-del]').forEach(b=>b.onclick=()=>{ if (confirm('Delete this post?')) { S.posts=S.posts.filter(p=>p.id!==b.dataset.del); save(); render(); } });
  v.querySelectorAll('[data-msg]').forEach(el=>el.onclick=()=>{selMsg=el.dataset.msg;S.inbox.find(m=>m.id===selMsg).read=true;save();render();});
  on('sendReply',()=>{ const t=$('#reply').value.trim(); if (!t) return; S.inbox.find(m=>m.id===selMsg).replies.push({me:true,text:t}); save(); render(); toast('Reply sent (simulated)'); });
  const dd=$('#anDays'); if (dd) dd.onchange=()=>{anDays=+dd.value;render();};
  on('exportCsv',()=>{ const rows=[['network','account','followers','impressions','engagements']]; S.profiles.forEach(p=>{const s=series(p,anDays);rows.push([NETS[p.net].n,p.name,p.followers,s.reduce((a,x)=>a+x.imp,0),s.reduce((a,x)=>a+x.eng,0)]);}); download('jkam-social-report.csv',rows.map(r=>r.map(c=>`"${String(c).replace(/"/g,'""')}"`).join(',')).join('\n'),'text/csv'); });
  v.querySelectorAll('[data-toggle]').forEach(b=>b.onclick=()=>{const p=prof(b.dataset.toggle);p.connected=!p.connected;save();render();});
  v.querySelectorAll('[data-rmprof]').forEach(b=>b.onclick=()=>{ if (confirm('Remove profile?')) { S.profiles=S.profiles.filter(p=>p.id!==b.dataset.rmprof); S.posts.forEach(p=>p.nets=p.nets.filter(n=>n!==b.dataset.rmprof)); save(); render(); } });
  on('addProf',()=>{ const n=$('#newNet').value,name=$('#newName').value.trim(),h=$('#newHandle').value.trim(); if(!name) return toast('Enter an account name.'); S.profiles.push({id:uid(),net:n,name,handle:h||name,followers:0,connected:true}); save(); render(); });
  const c=$('#cmp'); if (c) c.onchange=()=>{S.compliance=c.checked;save();toast('Saved');};
  on('exportJson',()=>download('jkam-social-data.json',JSON.stringify(S,null,2),'application/json'));
  on('resetBtn',doReset);
}
function doReset() { if (confirm('Reset all demo data?')) { S=seed(); save(); render(); } }
$('#reset').onclick = doReset;
$('#newPost').onclick = () => openComposer();
$('#role').onchange = e => { S.role=e.target.value; save(); render(); };
document.addEventListener('keydown', e => { if (e.key==='Escape') closeModal(); });
render();
