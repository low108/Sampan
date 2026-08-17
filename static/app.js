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
/* Chinese names are surname-first, so the first token of "Lim Siew Khim" is
 * the family name half this household shares. The given name is what follows. */
const given = (name) => {
  const parts = (name || '').trim().split(/\s+/);
  return parts.length < 2 ? (name || '') : parts.slice(1).join(' ');
};
const initial = (name) => (name || '?').trim()[0];

const nav = (patch) => { Object.assign(S, patch); render(); };

/* ── data ──────────────────────────────────────────────────────── */

async function load() {
  let house, bell;
  try {
    [house, bell] = await Promise.all([
      api('/api/household'),
      api(`/api/bell/${encodeURIComponent(ME)}`).catch(() => ({ unseen: 0, notifications: [] })),
    ]);
  } catch (err) {
    /* Without this the first 401 rejected here, render() never ran, and the
     * page stayed blank forever — the same white screen whether the key was
     * missing, the service was down, or the archive was empty. Say which. */
    fail(err.message === '401'
      ? 'This link is missing its access key. Open the URL that ends in <code>?key=…</code>.'
      : `Could not reach the archive (${esc(err.message)}). It may still be starting up — try again in a moment.`);
    return;
  }
  S.data = house;
  S.bell = bell;
  render();
  syncPins();
}

function fail(message) {
  document.getElementById('app').innerHTML = `
    <div class="failed">
      <h1>Sampan</h1>
      <p>${message}</p>
    </div>`;
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
      : `<h1>Sampan<small>Xiao Chuan</small></h1>`}
    <button class="bell" data-bell>🔔${
      S.bell?.unseen ? `<b>${S.bell.unseen}</b>` : ''}</button>
  </header>`;
};

const tabs = () => `<nav class="tabs">
  ${[['map', '🗺', 'Map'], ['record', '🎙', 'Tell a story'],
     ['family', '👵', 'Family']].map(([id, icon, label]) =>
    `<button data-tab="${id}" aria-current="${S.tab === id}"><i>${icon}</i>${label}</button>`
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
        ${unplaced.length} ${unplaced.length === 1 ? 'story has' : 'stories have'} no place
        <span class="en">— they only say "home"</span>
      </button>` : ''}`;
}

/* Absence is a place on the page: a permanent, tappable line, never a silent omission. */
const unplacedSheet = () => {
  const list = S.data?.unplaced || [];
  return sheet(`
    <h2>Stories with no place</h2>
    <p class="en">Stories with nowhere to sit — not lost, just not placed.</p>
    ${list.map((c) => `<article class="card">
      <h3>${esc(c.title)}</h3>
      <div class="meta"><span>${esc(c.narrator_name)}</span>
        <span>only says "${esc(c.where_said)}"</span></div>
      ${c.sense_detail ? `<p class="said">${esc(c.sense_detail)}</p>` : ''}
      <p class="gap">Across four calls she never said which house.
        <span class="en">Xiao Chuan does not guess.</span></p>
      <div class="row"><button class="btn ghost small" data-know="${esc(c.where_said)}">
        I know which one</button></div>
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
      <span>${pin.year || 'year not yet told'}</span>
      <span>${esc(pin.narrator_name)}</span>
      <span class="certainty ${guess ? 'guess' : ''}"><s></s>${
        guess ? 'Xiao Chuan guessed this place' : 'the place she named'}</span>
    </div>
    ${pin.linked ? `<details class="more">
      <summary>Why this pin is here</summary>
      <p class="narr" id="why-${esc(pin.id)}">…</p>
    </details>` : ''}
    ${guess ? `<div class="row">
      <button class="btn ghost small" data-right="${esc(pin.id)}">That's right</button>
      <button class="btn ghost small" data-wrong="${esc(pin.id)}">No — let me fix it</button>
    </div>` : ''}
    <details class="more"><summary>Her words</summary>
      <p class="narr" id="full-${esc(pin.id)}">…</p></details>`);
}

/* ── record tab ────────────────────────────────────────────────── */

function recordPage() {
  const on = S.rec === 'live';
  const q = S.recQuestion;
  return `<div class="rec">
    ${q ? `<div class="asked">
        <div class="who">${esc(q.from_name)} asked you</div>
        <p>${esc(q.question)}</p>
      </div>` : `<p>Say whatever comes to mind, any time.</p>`}
    <button class="bigbtn" data-rec data-on="${on}">${on ? "That's enough" : 'Tell a story'}</button>
    <p id="recsay" class="en">${on ? 'Xiao Chuan is listening' : ''}</p>
  </div>`;
}

/* ── family tab ────────────────────────────────────────────────── */

const familyPage = () => `<div class="pad">
  ${(S.data?.members || []).map((m) => `<div class="person" data-member="${esc(m.narrator_id)}">
    <div class="face">${esc(initial(m.display_name))}</div>
    <div>
      <div class="who">${esc(m.display_name)}</div>
      <div class="meta"><span>${esc(m.relation)}</span>
        <span>${m.story_count ? `${m.story_count} ${m.story_count === 1 ? 'story' : 'stories'}` : 'nothing told yet'}</span></div>
    </div>
  </div>`).join('')}
</div>`;

function memberPage() {
  const person = memberOf(S.member);
  const tabsHtml = `<div class="subtabs">
    ${[['chat', 'Ask about her'], ['map', 'Her map'], ['ask', 'Leave a question']].map(([id, zh]) =>
      `<button data-mtab="${id}" aria-current="${S.memberTab === id}">${zh}</button>`).join('')}
  </div>`;

  if (S.memberTab === 'map') {
    return `${tabsHtml}<div class="maprap" id="maphost" style="top:4rem"></div>`;
  }
  if (S.memberTab === 'ask') {
    return `<div class="pad">${tabsHtml}
      <p>Leave a question for ${esc(given(person.display_name))}. Xiao Chuan will
      ask it on the next call — and say that it came from you.</p>
      <label>Who are you</label><input id="askfrom" placeholder="Wei Lun">
      <label>What would you like to ask</label><textarea id="askq"
        placeholder="Did Ah Gong leave anything behind?"></textarea>
      <div class="row"><button class="btn" data-send>Send</button></div>
      <p class="en" id="asksent"></p></div>`;
  }
  return `<div class="pad">${tabsHtml}
    ${S.chat.length ? S.chat.map((m) => `<div class="bubble ${m.mine ? 'mine' : ''}">
        ${esc(m.text)}
        ${m.en ? `<p class="en">${esc(m.en)}</p>` : ''}
        ${m.follow ? `<p class="gap"><b>Worth asking her</b> · ${esc(m.follow)}</p>
          <button class="btn ghost small" data-queue="${esc(m.follow)}">
            Ask her this next call ›</button>` : ''}
      </div>`).join('')
      : `<p class="empty">Ask anything about ${esc(given(person.display_name))}.</p>`}
    <label>Ask about her</label>
    <input id="q" placeholder="What did her father do for a living?">
    <div class="row">
      <button class="btn" data-askabout>Ask</button>
      <button class="btn ghost" data-timeline>Make her timeline</button>
    </div>`;
}

/* ── bell ──────────────────────────────────────────────────────── */

const bellSheet = () => sheet(`
  <h2>Messages</h2>
  ${(S.bell?.notifications || []).map((n) => `<article class="card"
      data-notif="${esc(n.id)}" data-opens="${esc(n.opens)}" data-target="${esc(n.target)}">
    <h3>${esc(n.title)}</h3>
    <div class="meta"><span class="en">${esc(n.subtitle)}</span></div>
    ${n.opens === 'record'
      ? `<p class="gap"><b>Tap to answer</b></p>` : ''}
  </article>`).join('') || `<p class="empty">Nothing new.</p>`}`);

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
  on('[data-right]', (el) => { el.textContent = 'Thank you'; el.disabled = true; });
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
      ? `She said: "${place.linked_evidence}"`
      : 'She named this place in another conversation.';
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
    S.chat.push({ text: "Couldn't reach that just now. Try again in a moment." });
  }
  render();
}

/* Timeline on demand: it is a request, and it should feel like one. */
async function makeTimeline() {
  S.chat.push({ text: 'Make her timeline', mine: true });
  S.chat.push({ text: 'Xiao Chuan is putting it in order…' });
  render();
  try {
    const d = await api(`/api/family/${encodeURIComponent(S.member)}?view=timeline`);
    const lines = d.stories.map((s) => {
      const y = s.year_from || s.year_to;
      return `${y || 'year not yet told'} · ${s.title}`;
    });
    S.chat[S.chat.length - 1] = { text: `${given(memberOf(S.member).display_name)}'s life\n\n${lines.join('\n')}` };
  } catch {
    S.chat[S.chat.length - 1] = { text: "Couldn't put it in order. Try again in a moment." };
  }
  render();
}

async function queueFollowUp(question) {
  await api(`/api/family/${encodeURIComponent(S.member)}/ask`, {
    method: 'POST',
    body: JSON.stringify({ from_name: given(memberOf(ME)?.display_name || 'family'), question }),
  }).catch(() => {});
  S.chat.push({ text: 'Alright — Xiao Chuan will ask her next call.' });
  render();
}

async function sendAsk() {
  const from = document.getElementById('askfrom').value.trim();
  const question = document.getElementById('askq').value.trim();
  const out = document.getElementById('asksent');
  if (!from || !question) { out.textContent = 'Both your name and a question are needed'; return; }
  try {
    await api(`/api/family/${encodeURIComponent(S.member)}/ask`,
      { method: 'POST', body: JSON.stringify({ from_name: from, question }) });
    out.textContent = 'Sent. She will hear it when she next picks up.';
  } catch { out.textContent = "Couldn't send. Try again in a moment."; }
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
  const value = prompt(`Where is "${rawName}"?`, '');
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
  } catch (err) { say('Cannot open the microphone: ' + err.message); return; }

  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/talk?key=${
    encodeURIComponent(KEY)}&user=${encodeURIComponent(ME)}`);
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.audio) play(Uint8Array.from(atob(m.audio), (c) => c.charCodeAt(0)), m.sample_rate || 24000);
    if (m.agent_transcript) say('Xiao Chuan: ' + m.agent_transcript);
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
  if (el) el.textContent = "Saved. Xiao Chuan will listen again later.";
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
