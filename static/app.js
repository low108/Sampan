/* Sampan — one app, two generations.
 *
 * State is a single object, as in the approved prototype:
 *   { tab, member, memberTab, story, sheet, rec }
 * Everything renders from it, so there is one place to reason about where you
 * are and no screen can drift out of sync with another.
 */

const params = new URLSearchParams(location.search);
const KEY = params.get('key') || '';
const ME = params.get('user') || 'ah_khim';

const S = {
  tab: 'map', member: null, memberTab: 'chat',
  story: null, sheet: null, rec: 'idle',
  data: null, bell: null, chat: [], recQuestion: null,
};

const api = async (path, opts = {}) => {
  const res = await fetch(path, {
    ...opts,
    headers: { 'X-Sampan-Key': KEY, 'Content-Type': 'application/json', ...(opts.headers || {}) },
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
};

const esc = (s) => (s ?? '').replace(/[&<>"]/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const given = (name) => (name || '').split(' ')[0];
const initial = (name) => (name || '?').trim()[0];

const nav = (patch) => { Object.assign(S, patch); render(); };

/* ── data ──────────────────────────────────────────────────────── */

async function load() {
  const [house, bell] = await Promise.all([
    api('/api/household'),
    api(`/api/bell/${encodeURIComponent(ME)}`).catch(() => ({ unseen: 0, notifications: [] })),
  ]);
  S.data = house;
  S.bell = bell;
  render();
  syncPins();
}

const memberOf = (id) => (S.data?.members || []).find((m) => m.narrator_id === id);
const pinsFor = (id) => (S.data?.pins || []).filter((p) => !id || p.narrator_id === id);
const storyById = (id) => (S.data?.pins || []).find((p) => p.id === id);

/* ── map ───────────────────────────────────────────────────────── */

let mapEl = null;

function syncPins() {
  if (!mapEl || !S.data) return;
  const scope = S.tab === 'family' && S.member ? S.member : null;
  mapEl.setPins(pinsFor(scope));
  if (S.story) mapEl.select(S.story); else mapEl.select(null);
}

function mountMap(host) {
  if (!mapEl) {
    mapEl = document.createElement('sampan-map');
    mapEl.addEventListener('sampan-pin', (e) => nav({ story: e.detail.id }));
    mapEl.addEventListener('sampan-blank', () => nav({ story: null }));
  }
  if (mapEl.parentElement !== host) host.appendChild(mapEl);
  requestAnimationFrame(syncPins);
}

/* ── rendering ─────────────────────────────────────────────────── */

function render() {
  const app = document.getElementById('app');
  app.innerHTML = `
    ${topBar()}
    <main class="${S.tab === 'map' || (S.member && S.memberTab === 'map') ? 'nopad' : ''}"
          id="main">${body()}</main>
    ${S.member ? '' : tabs()}
    ${S.story ? storySheet() : ''}
    ${S.sheet === 'unplaced' ? unplacedSheet() : ''}
    ${S.sheet === 'notifs' ? bellSheet() : ''}`;
  wire();
}

const topBar = () => {
  const person = S.member ? memberOf(S.member) : null;
  return `<header class="top">
    ${person
      ? `<button class="bell" data-back>‹</button>
         <h1>${esc(given(person.display_name))}<small>${esc(person.relation)}</small></h1>`
      : `<h1>小船<small>Sampan</small></h1>`}
    <button class="bell" data-bell>🔔${
      S.bell?.unseen ? `<b>${S.bell.unseen}</b>` : ''}</button>
  </header>`;
};

const tabs = () => `<nav class="tabs">
  ${[['map', '🗺', '地图', 'Map'], ['record', '🎙', '讲故事', 'Record'],
     ['family', '👵', '家人', 'Family']].map(([id, icon, zh]) =>
    `<button data-tab="${id}" aria-current="${S.tab === id}"><i>${icon}</i>${zh}</button>`
  ).join('')}
</nav>`;

function body() {
  if (S.member) return memberPage();
  if (S.tab === 'map') return mapPage();
  if (S.tab === 'record') return recordPage();
  return familyPage();
}

/* ── map tab ───────────────────────────────────────────────────── */

function mapPage() {
  const unplaced = S.data?.unplaced || [];
  return `<div class="maprap" id="maphost"></div>
    ${unplaced.length ? `<button class="unplaced-bar" data-unplaced>
        ${unplaced.length} 个故事没有地方
        <span class="en">— only say「家里」, not placed</span>
      </button>` : ''}`;
}

/* Absence is a place on the page: a permanent, tappable line, never a silent omission. */
const unplacedSheet = () => {
  const list = S.data?.unplaced || [];
  return sheet(`
    <h2>没有地方的故事</h2>
    <p class="en">Stories with nowhere to sit — not lost, just not placed.</p>
    ${list.map((c) => `<article class="card">
      <h3>${esc(c.title)}</h3>
      <div class="meta"><span>${esc(c.narrator_name)}</span>
        <span>只说了「${esc(c.where_said)}」</span></div>
      ${c.sense_detail ? `<p class="said">${esc(c.sense_detail)}</p>` : ''}
      <p class="gap">四通电话里她都没讲是哪一间屋。小船不猜。
        <span class="en">She never said which house. 小船 doesn't guess.</span></p>
      <div class="row"><button class="btn ghost small" data-know="${esc(c.where_said)}">
        我知道是哪间屋</button></div>
    </article>`).join('')}`);
};

/* ── story card ────────────────────────────────────────────────── */

function storySheet() {
  const pin = storyById(S.story);
  if (!pin) return '';
  const guess = ['town', 'region'].includes(pin.precision);
  return sheet(`
    <h2>${esc(pin.title)}</h2>
    <div class="meta">
      <span>${pin.year || '年份还没讲'}</span>
      <span>${esc(pin.narrator_name)}</span>
      <span class="certainty ${guess ? 'guess' : ''}"><s></s>${
        guess ? '这个地点是小船猜的' : '她说的地方'}</span>
    </div>
    ${pin.linked ? `<details class="more">
      <summary>为什么在这里 · why this pin is here</summary>
      <p class="narr" id="why-${esc(pin.id)}">…</p>
    </details>` : ''}
    ${guess ? `<div class="row">
      <button class="btn ghost small" data-right="${esc(pin.id)}">对的</button>
      <button class="btn ghost small" data-wrong="${esc(pin.id)}">不对，我改</button>
    </div>` : ''}
    <details class="more"><summary>她说了什么 · her words</summary>
      <p class="narr" id="full-${esc(pin.id)}">…</p></details>`);
}

/* ── record tab ────────────────────────────────────────────────── */

function recordPage() {
  const on = S.rec === 'live';
  const q = S.recQuestion;
  return `<div class="rec">
    ${q ? `<div class="asked">
        <div class="who">${esc(q.from_name)}问你</div>
        <p>${esc(q.question)}</p>
      </div>` : `<p>想到什么就讲，随时都可以。<br>
        <span class="en">Say anything, any time.</span></p>`}
    <button class="bigbtn" data-rec data-on="${on}">${on ? '讲完了' : '讲故事'}</button>
    <p id="recsay" class="en">${on ? '小船在听' : ''}</p>
  </div>`;
}

/* ── family tab ────────────────────────────────────────────────── */

const familyPage = () => `<div class="pad">
  ${(S.data?.members || []).map((m) => `<div class="person" data-member="${esc(m.narrator_id)}">
    <div class="face">${esc(initial(m.display_name))}</div>
    <div>
      <div class="who">${esc(m.display_name)}</div>
      <div class="meta"><span>${esc(m.relation)}</span>
        <span>${m.story_count ? `${m.story_count} 个故事` : '还没讲过'}</span></div>
    </div>
  </div>`).join('')}
</div>`;

function memberPage() {
  const person = memberOf(S.member);
  const tabsHtml = `<div class="subtabs">
    ${[['chat', '问问她'], ['map', '她的地图'], ['ask', '问她一句']].map(([id, zh]) =>
      `<button data-mtab="${id}" aria-current="${S.memberTab === id}">${zh}</button>`).join('')}
  </div>`;

  if (S.memberTab === 'map') {
    return `${tabsHtml}<div class="maprap" id="maphost" style="height:calc(100% - 4rem)"></div>`;
  }
  if (S.memberTab === 'ask') {
    return `<div class="pad">${tabsHtml}
      <p>留一句话给${esc(given(person.display_name))}。小船下次打给她的时候会替你问，讲你的名字。</p>
      <p class="en">Leave a question. 小船 raises it on the next call — and says who asked.</p>
      <label>你是谁</label><input id="askfrom" placeholder="伟伦">
      <label>想问什么</label><textarea id="askq" placeholder="阿公有没有留下什么东西?"></textarea>
      <div class="row"><button class="btn" data-send>送出</button></div>
      <p class="en" id="asksent"></p></div>`;
  }
  return `<div class="pad">${tabsHtml}
    ${S.chat.length ? S.chat.map((m) => `<div class="bubble ${m.mine ? 'mine' : ''}">
        ${esc(m.text)}
        ${m.en ? `<p class="en">${esc(m.en)}</p>` : ''}
        ${m.follow ? `<p class="gap"><b>下次替我问她</b> · ${esc(m.follow)}</p>
          <button class="btn ghost small" data-queue="${esc(m.follow)}">
            下次替我问她 ›</button>` : ''}
      </div>`).join('')
      : `<p class="empty">想知道${esc(given(person.display_name))}什么?<br>
         <span class="en">Ask anything about her.</span></p>`}
    <label>问问她</label>
    <input id="q" placeholder="她爸爸做什么工的？">
    <div class="row">
      <button class="btn" data-askabout>问</button>
      <button class="btn ghost" data-timeline>做一张她的时间线</button>
    </div>`;
}

/* ── bell ──────────────────────────────────────────────────────── */

const bellSheet = () => sheet(`
  <h2>信 · Messages</h2>
  ${(S.bell?.notifications || []).map((n) => `<article class="card"
      data-notif="${esc(n.id)}" data-opens="${esc(n.opens)}" data-target="${esc(n.target)}">
    <h3>${esc(n.title)}</h3>
    <div class="meta"><span class="en">${esc(n.subtitle)}</span></div>
    ${n.opens === 'record'
      ? `<p class="gap"><b>按一下就可以开始讲</b> · tap to answer her</p>` : ''}
  </article>`).join('') || `<p class="empty">没有新的。</p>`}`);

const sheet = (inner) => `<div class="scrim" data-close></div>
  <div class="sheet"><div class="grab"></div>${inner}</div>`;

/* ── behaviour ─────────────────────────────────────────────────── */

function wire() {
  const host = document.getElementById('maphost');
  if (host) mountMap(host);

  const on = (sel, fn) => document.querySelectorAll(sel).forEach((el) =>
    el.addEventListener('click', () => fn(el)));

  on('[data-tab]', (el) => nav({ tab: el.dataset.tab, member: null, story: null }));
  on('[data-member]', (el) => nav({ member: el.dataset.member, memberTab: 'chat', story: null }));
  on('[data-mtab]', (el) => nav({ memberTab: el.dataset.mtab, story: null }));
  on('[data-back]', () => nav({ member: null, story: null, chat: [] }));
  on('[data-bell]', () => nav({ sheet: 'notifs' }));
  on('[data-unplaced]', () => nav({ sheet: 'unplaced' }));
  on('[data-close]', () => nav({ sheet: null, story: null }));

  on('[data-notif]', async (el) => {
    await api(`/api/bell/${encodeURIComponent(ME)}/seen`,
      { method: 'POST', body: JSON.stringify({ ids: [el.dataset.notif] }) }).catch(() => {});
    const { opens, target } = el.dataset;
    if (opens === 'record') {
      const p = await api(`/api/talk/${encodeURIComponent(ME)}/pending`).catch(() => null);
      nav({ sheet: null, tab: 'record', member: null,
            recQuestion: p?.waiting ? { from_name: p.from_name, question: p.question } : null });
    } else if (opens === 'member') {
      nav({ sheet: null, tab: 'family', member: target, memberTab: 'chat' });
    } else {
      nav({ sheet: null, tab: 'map', story: target });
    }
    api(`/api/bell/${encodeURIComponent(ME)}`).then((b) => { S.bell = b; });
  });

  on('[data-rec]', () => toggleRecord());
  on('[data-askabout]', () => askAbout());
  on('[data-timeline]', () => makeTimeline());
  on('[data-send]', () => sendAsk());
  on('[data-queue]', (el) => queueFollowUp(el.dataset.queue));
  on('[data-wrong]', (el) => correctPlace(el.dataset.wrong));
  on('[data-right]', (el) => { el.textContent = '谢谢'; el.disabled = true; });
  on('[data-know]', (el) => correctPlaceByName(el.dataset.know));

  fillStoryDetail();
}

/* Story detail is fetched lazily so the sheet opens instantly. */
async function fillStoryDetail() {
  const pin = S.story && storyById(S.story);
  if (!pin) return;
  const d = await api(`/api/family/${encodeURIComponent(pin.narrator_id)}?view=feed`)
    .catch(() => null);
  const card = d?.stories?.find((s) => s.story_id === pin.id);
  const full = document.getElementById(`full-${pin.id}`);
  if (full && card) {
    full.innerHTML = `${card.sense_detail
      ? `<span class="said" style="display:block;border:0;padding:0;margin:0 0 .7rem">
           ${esc(card.sense_detail)}</span>` : ''}${esc(card.narrative)}`;
  }
  const why = document.getElementById(`why-${pin.id}`);
  if (why) {
    const map = await api(`/api/family/${encodeURIComponent(pin.narrator_id)}?view=map`)
      .catch(() => null);
    const place = map?.map?.pins
      ?.map((p) => p.place)?.find((p) => p.linked_evidence);
    why.textContent = place?.linked_evidence
      ? `她讲过:「${place.linked_evidence}」` : '她在另一次聊天里讲过这个地方。';
  }
}

async function askAbout() {
  const input = document.getElementById('q');
  const question = input.value.trim();
  if (!question) return;
  S.chat.push({ text: question, mine: true });
  input.value = '';
  render();
  try {
    const d = await api(`/api/family/${encodeURIComponent(S.member)}/about`,
      { method: 'POST', body: JSON.stringify({ question }) });
    S.chat.push({ text: d.answer, en: d.answer_en, follow: d.follow_up });
  } catch {
    S.chat.push({ text: '一时问不到，等一下再试。' });
  }
  render();
}

/* Timeline on demand: it is a request, and it should feel like one. */
async function makeTimeline() {
  S.chat.push({ text: '做一张她的时间线', mine: true });
  S.chat.push({ text: '小船在排…' });
  render();
  try {
    const d = await api(`/api/family/${encodeURIComponent(S.member)}?view=timeline`);
    const lines = d.stories.map((s) => {
      const y = s.year_from || s.year_to;
      return `${y || '年份还没讲'} · ${s.title}`;
    });
    S.chat[S.chat.length - 1] = { text: `${given(memberOf(S.member).display_name)}的时间线\n\n${lines.join('\n')}` };
  } catch {
    S.chat[S.chat.length - 1] = { text: '排不出来，等一下再试。' };
  }
  render();
}

async function queueFollowUp(question) {
  await api(`/api/family/${encodeURIComponent(S.member)}/ask`, {
    method: 'POST',
    body: JSON.stringify({ from_name: given(memberOf(ME)?.display_name || '家人'), question }),
  }).catch(() => {});
  S.chat.push({ text: '好，小船下次会替你问她。' });
  render();
}

async function sendAsk() {
  const from = document.getElementById('askfrom').value.trim();
  const question = document.getElementById('askq').value.trim();
  const out = document.getElementById('asksent');
  if (!from || !question) { out.textContent = '名字和问题都要填'; return; }
  try {
    await api(`/api/family/${encodeURIComponent(S.member)}/ask`,
      { method: 'POST', body: JSON.stringify({ from_name: from, question }) });
    out.textContent = '送出了。她下次接电话就会听到。';
  } catch { out.textContent = '送不出，等一下再试。'; }
}

/* Correction lives inside the thing: no admin screen, ever. */
async function correctPlace(storyId) {
  const pin = storyById(storyId);
  if (!pin) return;
  const d = await api(`/api/family/${encodeURIComponent(pin.narrator_id)}?view=map`)
    .catch(() => null);
  const name = d?.map?.pins?.find((p) => p.stories.some((s) => s.story_id === storyId))
    ?.place?.raw_name;
  if (name) correctPlaceByName(name, pin.narrator_id);
}

async function correctPlaceByName(rawName, narratorId) {
  const value = prompt(`「${rawName}」是哪里?`, '');
  if (!value) return;
  await api(`/api/family/${encodeURIComponent(narratorId || S.member || ME)}/corrections`, {
    method: 'POST',
    body: JSON.stringify({ kind: 'place', target: rawName, value, by: ME }),
  }).catch(() => {});
  await load();
}

/* ── recording ─────────────────────────────────────────────────── */

let ws, ctx, node, stream, playCtx, playAt = 0;

async function toggleRecord() {
  if (S.rec === 'live') return stopRecord();
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });
  } catch (err) { say('开不了麦克风:' + err.message); return; }

  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/talk?key=${
    encodeURIComponent(KEY)}&user=${encodeURIComponent(ME)}`);
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.audio) play(Uint8Array.from(atob(m.audio), (c) => c.charCodeAt(0)), m.sample_rate || 24000);
    if (m.agent_transcript) say('小船:' + m.agent_transcript);
    if (m.user_transcript) say(m.user_transcript);
    if (m.interrupted) playAt = 0;
  };
  ws.onclose = () => stopRecord();

  ctx = new AudioContext({ sampleRate: 16000 });
  await ctx.audioWorklet.addModule('worklet.js');
  node = new AudioWorkletNode(ctx, 'pcm-capture');
  node.port.onmessage = (e) => { if (ws?.readyState === 1) ws.send(e.data); };
  ctx.createMediaStreamSource(stream).connect(node);
  node.connect(ctx.destination);

  S.rec = 'live';
  render();
}

function stopRecord() {
  S.rec = 'idle';
  ws?.close(); ctx?.close(); playCtx?.close();
  stream?.getTracks().forEach((t) => t.stop());
  ws = ctx = playCtx = stream = null; playAt = 0;
  render();
  const el = document.getElementById('recsay');
  if (el) el.textContent = '收好了。小船晚点会再听一遍。';
  load();
}

function say(text) {
  const el = document.getElementById('recsay');
  if (el) el.textContent = text;
}

function play(bytes, rate) {
  playCtx ||= new AudioContext();
  const pcm = new Int16Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 2);
  const buf = playCtx.createBuffer(1, pcm.length, rate);
  const ch = buf.getChannelData(0);
  for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 32768;
  const src = playCtx.createBufferSource();
  src.buffer = buf; src.connect(playCtx.destination);
  playAt = Math.max(playAt, playCtx.currentTime);
  src.start(playAt); playAt += buf.duration;
}

load();
