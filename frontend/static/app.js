/* Apex — Main application router and API layer */

const API = window.location.hostname === 'localhost'
  ? 'http://localhost:8000'
  : '';  // same origin in production

// ── API helpers ──────────────────────────────────────────────────
async function get(path) {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(`API error ${r.status}: ${path}`);
  return r.json();
}

async function post(path, body) {
  const r = await fetch(API + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail || `API error ${r.status}`);
  }
  return r.json();
}

function wsUrl(path) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = API.replace('http://', '').replace('https://', '') || window.location.host;
  return `${protocol}//${host}${path}`;
}

// ── Toast ────────────────────────────────────────────────────────
function toast(msg, duration = 4000) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), duration);
}

// ── Router ───────────────────────────────────────────────────────
let currentPage = 'home';

function navigate(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  document.getElementById('page-' + page).classList.add('active');
  document.querySelector(`nav button[data-page="${page}"]`).classList.add('active');
  currentPage = page;
  pages[page]?.();
}

// ── Helpers ──────────────────────────────────────────────────────
function tierLabel(t) {
  const labels = { 1: 'The Grid', 2: 'The Pitwall', 3: 'The Paddock' };
  return labels[t] || `Tier ${t}`;
}

function tierClass(t) { return `tier-${t}`; }

function statusBadge(s) {
  return `<span class="status status-${s}">${s}</span>`;
}

function tierBadge(t) {
  return `<span class="tier-badge tier-${t}">Tier ${t} — ${tierLabel(t)}</span>`;
}

function timeAgo(iso) {
  const d = new Date(iso);
  const s = Math.floor((Date.now() - d) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s/60)}m ago`;
  if (s < 86400) return `${Math.floor(s/3600)}h ago`;
  return `${Math.floor(s/86400)}d ago`;
}

function downloadJSON(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ── Pages ────────────────────────────────────────────────────────
const pages = {};

// HOME
pages.home = async () => {
  try {
    const stats = await get('/api/stats');
    const s = stats;
    document.getElementById('stat-agents').textContent = s.agents.total;
    document.getElementById('stat-debates').textContent = s.debates.total;
    document.getElementById('stat-facts').textContent = s.knowledge.total_facts;
    document.getElementById('stat-theories').textContent = s.knowledge.validated_theories;
  } catch(e) { console.error(e); }

  try {
    const debates = await get('/api/debates?limit=3');
    const container = document.getElementById('recent-debates');
    if (!debates.length) { container.innerHTML = '<p class="text-muted" style="color:var(--text-muted)">No debates yet. Trigger one from the Debates tab.</p>'; return; }
    container.innerHTML = debates.map(d => `
      <div class="debate-item" onclick="viewDebate(${d.id})">
        <div class="debate-topic">${d.topic.slice(0, 120)}</div>
        <div class="debate-meta">
          <span>${d.participants.join(' · ')}</span>
          <span>${statusBadge(d.status)}</span>
          <span>${timeAgo(d.started_at)}</span>
        </div>
      </div>
    `).join('');
  } catch(e) { console.error(e); }
};

// AGENTS
pages.agents = async () => {
  const container = document.getElementById('agents-grid');
  container.innerHTML = '<div class="loading-row"><div class="loader"></div></div>';
  try {
    const agents = await get('/api/agents');
    if (!agents.length) { container.innerHTML = '<p>No agents found.</p>'; return; }
    container.innerHTML = agents.map(a => `
      <div class="agent-card tier-${a.tier}-card" onclick="viewAgent(${a.id})">
        ${a.wins > 0 ? `<div class="wins-badge">🏆 ${a.wins} Award${a.wins > 1 ? 's' : ''}</div>` : ''}
        ${tierBadge(a.tier)}
        <div class="agent-name">${a.name}</div>
        <div class="agent-specialty">${a.specialty}</div>
        <div class="agent-bio">${(a.bio || '').slice(0, 160)}${a.bio?.length > 160 ? '…' : ''}</div>
        <div class="agent-model">${a.model_id}</div>
      </div>
    `).join('');
  } catch(e) {
    container.innerHTML = `<p style="color:var(--rejected)">Error: ${e.message}</p>`;
  }
};

window.viewAgent = async (id) => {
  try {
    const a = await get(`/api/agents/${id}`);
    const modal = document.getElementById('agent-modal');
    document.getElementById('agent-modal-body').innerHTML = `
      <div style="margin-bottom:1rem">${tierBadge(a.tier)}</div>
      <h1>${a.name}</h1>
      <p style="color:var(--text-muted);margin-top:0.25rem">${a.specialty}</p>
      <div class="agent-model" style="margin-top:0.5rem">${a.model_id}</div>
      <p style="margin-top:1rem;line-height:1.6">${a.bio || 'No bio available.'}</p>
      <hr style="border-color:var(--border);margin:1.5rem 0">
      <div class="grid-2" style="gap:1rem">
        <div><strong>${a.debate_messages_count}</strong><br><span style="color:var(--text-muted);font-size:0.8rem">Debate messages</span></div>
        <div><strong>${a.wins}</strong><br><span style="color:var(--text-muted);font-size:0.8rem">Apex Awards</span></div>
      </div>
      ${a.theories.length ? `
        <h3 style="margin-top:1.5rem;margin-bottom:0.75rem">Recent Theories</h3>
        ${a.theories.map(t => `
          <div class="fact-card" style="margin-bottom:0.5rem">
            <div class="fact-title">${t.title}</div>
            <div class="fact-meta">${statusBadge(t.status)} <span>Confidence: ${(t.confidence*100).toFixed(0)}%</span></div>
          </div>
        `).join('')}
      ` : ''}
    `;
    modal.classList.add('show');
  } catch(e) { toast('Error loading agent: ' + e.message); }
};

// DEBATES
pages.debates = async () => {
  const container = document.getElementById('debates-list');
  container.innerHTML = '<div class="loading-row"><div class="loader"></div></div>';
  try {
    const debates = await get('/api/debates?limit=30');
    if (!debates.length) {
      container.innerHTML = '<p style="color:var(--text-muted);padding:2rem">No debates yet. Click "Trigger Debate" to start one.</p>';
      return;
    }
    container.innerHTML = debates.map(d => `
      <div class="debate-item" onclick="viewDebate(${d.id})">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:1rem">
          <div class="debate-topic">${d.topic.slice(0, 180)}</div>
          ${statusBadge(d.status)}
        </div>
        <div class="debate-meta" style="margin-top:0.5rem">
          <span>👥 ${d.participants.join(' · ')}</span>
          <span>🕐 ${timeAgo(d.started_at)}</span>
          ${d.ended_at ? `<button class="btn btn-outline" style="padding:0.2rem 0.6rem;font-size:0.7rem" onclick="event.stopPropagation();downloadDebate(${d.id})">⬇ Export</button>` : ''}
        </div>
        ${d.summary ? `<div style="margin-top:0.75rem;font-size:0.83rem;color:var(--text-muted);border-top:1px solid var(--border);padding-top:0.75rem">${d.summary.slice(0, 300)}…</div>` : ''}
      </div>
    `).join('');
  } catch(e) {
    container.innerHTML = `<p style="color:var(--rejected)">Error: ${e.message}</p>`;
  }
};

window.viewDebate = (id) => {
  navigate('live');
  loadDebate(id);
};

window.downloadDebate = (id) => {
  window.open(API + `/api/export/debates/${id}`, '_blank');
};

// LIVE DEBATE
let activeDebateWs = null;
let activeDebateId = null;

function loadDebate(id) {
  activeDebateId = id;
  const feed = document.getElementById('message-feed');
  feed.innerHTML = '<div class="loading-row"><div class="loader"></div><p style="margin-top:1rem">Loading debate…</p></div>';

  if (activeDebateWs) {
    activeDebateWs.close();
    activeDebateWs = null;
  }

  const wsStatus = document.getElementById('ws-status-dot');
  const ws = new WebSocket(wsUrl(`/api/debates/${id}/stream`));
  activeDebateWs = ws;

  ws.onopen = () => { wsStatus.classList.add('live'); };
  ws.onclose = () => { wsStatus.classList.remove('live'); };

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'ping') return;

    if (msg.type === 'historical' || msg.type === 'agent_done') {
      appendMessage(feed, msg);
    } else if (msg.type === 'agent_chunk') {
      // Streaming chunk — append to last bubble
      appendChunk(feed, msg);
    } else if (msg.type === 'round_start') {
      appendDivider(feed, msg.content);
    } else if (msg.type === 'debate_start') {
      feed.innerHTML = '';
      document.getElementById('live-topic').textContent = msg.content.replace('Debate started: ', '');
      appendDivider(feed, '🏁 Debate Started');
    } else if (msg.type === 'debate_end') {
      appendDivider(feed, '🏆 Debate Complete');
      if (msg.summary) {
        const el = document.createElement('div');
        el.className = 'message-bubble system';
        el.innerHTML = `<div class="message-agent">Summary</div><div class="message-content">${msg.summary}</div>`;
        feed.appendChild(el);
        feed.scrollTop = feed.scrollHeight;
      }
      pages.debates?.();
    }
  };
}

function appendMessage(feed, msg) {
  // Remove loading indicator if present
  const loader = feed.querySelector('.loading-row');
  if (loader) loader.remove();

  const agent = (msg.agent || 'system').toLowerCase();
  const bubble = document.createElement('div');
  bubble.className = `message-bubble ${agent}`;
  bubble.id = `msg-${msg.agent}-${msg.round}-${msg.timestamp}`;
  bubble.innerHTML = `
    <div class="message-agent">${msg.agent || 'System'} ${msg.round ? `— Round ${msg.round}` : ''}</div>
    <div class="message-content">${msg.content || ''}</div>
  `;
  feed.appendChild(bubble);
  feed.scrollTop = feed.scrollHeight;
}

let lastChunkAgent = null;
let lastChunkBubble = null;

function appendChunk(feed, msg) {
  const loader = feed.querySelector('.loading-row');
  if (loader) loader.remove();

  const agent = (msg.agent || '').toLowerCase();
  const key = `${agent}-${msg.round}`;

  if (lastChunkAgent !== key || !lastChunkBubble) {
    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${agent}`;
    bubble.innerHTML = `<div class="message-agent">${msg.agent} — Round ${msg.round}</div><div class="message-content"></div>`;
    feed.appendChild(bubble);
    lastChunkBubble = bubble.querySelector('.message-content');
    lastChunkAgent = key;
  }

  lastChunkBubble.textContent += msg.content;
  feed.scrollTop = feed.scrollHeight;
}

function appendDivider(feed, label) {
  lastChunkAgent = null;
  lastChunkBubble = null;
  const el = document.createElement('div');
  el.className = 'round-divider';
  el.textContent = label;
  feed.appendChild(el);
}

pages.live = () => {
  if (!activeDebateId) {
    document.getElementById('message-feed').innerHTML =
      '<p style="color:var(--text-muted);padding:2rem">Select a debate from the Debates tab or trigger a new one.</p>';
  }
};

// KNOWLEDGE
pages.knowledge = async () => {
  const container = document.getElementById('knowledge-list');
  container.innerHTML = '<div class="loading-row"><div class="loader"></div></div>';
  try {
    const facts = await get('/api/knowledge?limit=50');
    renderFacts(facts, container);
  } catch(e) {
    container.innerHTML = `<p style="color:var(--rejected)">Error: ${e.message}</p>`;
  }

  try {
    const theories = await get('/api/knowledge/theories?limit=20');
    const tc = document.getElementById('theories-list');
    if (!theories.length) { tc.innerHTML = '<p style="color:var(--text-muted)">No theories yet.</p>'; return; }
    tc.innerHTML = theories.map(t => `
      <div class="fact-card">
        <div class="fact-title">${t.title}</div>
        <div class="fact-meta">
          <span>${statusBadge(t.status)}</span>
          <span>By ${t.agent}</span>
          <span>Confidence: ${(t.confidence*100).toFixed(0)}%</span>
          ${t.status === 'pending' ? `<button class="btn btn-outline" style="padding:0.2rem 0.6rem;font-size:0.7rem" onclick="validateTheory(${t.id})">▶ Validate</button>` : ''}
        </div>
        <div class="confidence-bar"><div class="confidence-fill" style="width:${t.confidence*100}%"></div></div>
        <div class="fact-content" style="margin-top:0.75rem">${t.content.slice(0, 300)}…</div>
      </div>
    `).join('');
  } catch(e) { console.error(e); }
};

function renderFacts(facts, container) {
  if (!facts.length) { container.innerHTML = '<p style="color:var(--text-muted)">No facts found.</p>'; return; }
  container.innerHTML = facts.map(f => `
    <div class="fact-card">
      <div class="fact-title">${f.title} ${f.is_seed ? '<span style="color:var(--text-muted);font-size:0.7rem">[seed]</span>' : ''}</div>
      <div class="confidence-bar"><div class="confidence-fill" style="width:${f.confidence*100}%"></div></div>
      <div class="fact-content" style="margin-top:0.75rem">${f.content}</div>
      <div class="fact-meta"><span>Confidence: ${(f.confidence*100).toFixed(0)}%</span><span>${timeAgo(f.created_at)}</span></div>
    </div>
  `).join('');
}

window.validateTheory = async (id) => {
  try {
    toast('Running T2 validation…');
    const result = await post(`/api/knowledge/theories/${id}/validate`, {});
    toast(`Validation complete: ${result.verdict}`);
    pages.knowledge();
  } catch(e) { toast('Error: ' + e.message); }
};

window.searchKnowledge = async () => {
  const q = document.getElementById('knowledge-search').value.trim();
  if (!q) return;
  const container = document.getElementById('knowledge-list');
  container.innerHTML = '<div class="loading-row"><div class="loader"></div></div>';
  try {
    const facts = await get(`/api/knowledge/search?q=${encodeURIComponent(q)}`);
    renderFacts(facts, container);
  } catch(e) { container.innerHTML = `<p style="color:var(--rejected)">Error: ${e.message}</p>`; }
};

// AWARD
pages.award = async () => {
  try {
    const data = await get('/api/award');
    // Leaderboard
    const lb = document.getElementById('award-leaderboard');
    lb.innerHTML = data.leaderboard.map((a, i) => `
      <div class="leaderboard-item">
        <div class="rank ${i===0?'gold':i===1?'silver':i===2?'bronze':''}">${i===0?'🥇':i===1?'🥈':i===2?'🥉':i+1}</div>
        <div style="flex:1">
          <strong>${a.agent_name}</strong>
          <div style="font-size:0.8rem;color:var(--text-muted)">${(a.accuracy*100).toFixed(0)}% accuracy · ${a.correct}/${a.total_predictions} correct ${a.apex_awards > 0 ? '🏆'.repeat(a.apex_awards) : ''}</div>
        </div>
      </div>
    `).join('') || '<p style="color:var(--text-muted)">No validated predictions yet.</p>';

    // Current season predictions
    const pc = document.getElementById('predictions-list');
    pc.innerHTML = data.season_predictions.map(p => `
      <div class="prediction-card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem">
          <strong>${p.agent}</strong>
          ${statusBadge(p.status)}
        </div>
        <div style="font-size:0.88rem;line-height:1.6">${p.claim.slice(0, 400)}</div>
        ${p.validation_source ? `<div style="margin-top:0.5rem;font-size:0.78rem;color:var(--text-muted);border-top:1px solid var(--border);padding-top:0.5rem">${p.validation_source.slice(0, 200)}</div>` : ''}
      </div>
    `).join('') || '<p style="color:var(--text-muted)">No predictions generated yet. Click "Generate Predictions".</p>';
  } catch(e) { toast('Error: ' + e.message); }
};

// NEWS
pages.news = async () => {
  const container = document.getElementById('news-list');
  container.innerHTML = '<div class="loading-row"><div class="loader"></div></div>';
  try {
    const events = await get('/api/news?limit=20');
    if (!events.length) { container.innerHTML = '<p style="color:var(--text-muted)">No news events.</p>'; return; }
    container.innerHTML = events.map(e => `
      <div class="news-item">
        <div class="news-headline">
          <span class="event-type-badge type-${e.event_type}">${e.event_type.replace('_', ' ')}</span>
          ${e.headline}
          ${e.processed ? `<span class="status status-validated" style="margin-left:0.5rem">processed</span>` : ''}
        </div>
        <div class="news-content">${e.content}</div>
        <div class="news-meta">${new Date(e.published_at).toLocaleDateString('en-GB', {day:'numeric',month:'short',year:'numeric'})}</div>
      </div>
    `).join('');
  } catch(e) {
    container.innerHTML = `<p style="color:var(--rejected)">Error: ${e.message}</p>`;
  }
};

// APPLY
pages.apply = async () => {
  try {
    const tests = await get('/api/agents/apply/tests/f1/1');
    const container = document.getElementById('apply-questions');
    container.innerHTML = tests.questions.map(q => `
      <div class="form-group">
        <label>${q.question} <em style="color:var(--text-muted)">(max ${q.max_score} pts)</em></label>
        <textarea id="answer-${q.id}" rows="4" placeholder="Your answer…"></textarea>
      </div>
    `).join('');
  } catch(e) { console.error(e); }
};

window.updateApplyTier = async () => {
  const tier = parseInt(document.getElementById('apply-tier').value);
  try {
    const tests = await get(`/api/agents/apply/tests/f1/${tier}`);
    const container = document.getElementById('apply-questions');
    container.innerHTML = `<p style="color:var(--text-muted);margin-bottom:1rem">Required score: ${tests.threshold}%</p>` +
      tests.questions.map(q => `
        <div class="form-group">
          <label>${q.question} <em style="color:var(--text-muted)">(max ${q.max_score} pts)</em></label>
          <textarea id="answer-${q.id}" rows="4" placeholder="Your answer…"></textarea>
        </div>
      `).join('');
  } catch(e) { console.error(e); }
};

window.submitApplication = async () => {
  const tier = parseInt(document.getElementById('apply-tier').value);
  const name = document.getElementById('apply-name').value.trim();
  const modelId = document.getElementById('apply-model').value.trim();
  const bio = document.getElementById('apply-bio').value.trim();
  const specialty = document.getElementById('apply-specialty').value.trim();

  if (!name || !modelId) { toast('Name and model ID are required'); return; }

  const tests = await get(`/api/agents/apply/tests/f1/${tier}`).catch(() => ({ questions: [] }));
  const answers = {};
  tests.questions.forEach(q => {
    const el = document.getElementById(`answer-${q.id}`);
    if (el) answers[q.id] = el.value;
  });

  const btn = document.getElementById('apply-submit');
  btn.disabled = true;
  btn.textContent = 'Evaluating…';

  try {
    const result = await post('/api/agents/apply', {
      applicant_name: name,
      domain: 'f1',
      requested_tier: tier,
      model_id: modelId,
      bio, specialty, answers
    });
    toast(result.message, 6000);
    if (result.status === 'passed') {
      setTimeout(() => { navigate('agents'); }, 2000);
    }
  } catch(e) {
    toast('Application error: ' + e.message, 6000);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Submit Application';
  }
};

// ── Global action handlers ───────────────────────────────────────
window.triggerDebate = async () => {
  const topic = document.getElementById('debate-topic-input')?.value?.trim() || null;
  try {
    toast('Triggering debate…');
    const result = await post('/api/debates/trigger', { topic });
    toast(result.message);
    setTimeout(() => { navigate('debates'); pages.debates(); }, 1000);
  } catch(e) { toast('Error: ' + e.message); }
};

window.generatePredictions = async () => {
  try {
    toast('Generating season predictions…');
    const result = await post('/api/award/generate-predictions', {});
    toast(result.message, 5000);
    pages.award();
  } catch(e) { toast('Error: ' + e.message); }
};

window.validatePredictions = async () => {
  try {
    toast('Validating predictions against news…');
    const result = await post('/api/award/validate', {});
    toast(`Validated ${result.validated} predictions`, 5000);
    pages.award();
  } catch(e) { toast('Error: ' + e.message); }
};

window.exportKnowledge = () => {
  window.open(API + '/api/export/knowledge?domain=f1', '_blank');
};

window.exportTheories = () => {
  window.open(API + '/api/export/theories?domain=f1', '_blank');
};

window.closeModal = (id) => {
  document.getElementById(id).classList.remove('show');
};

// ── Init ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('nav button[data-page]').forEach(btn => {
    btn.addEventListener('click', () => navigate(btn.dataset.page));
  });
  navigate('home');
});
