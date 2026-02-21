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
  if (currentPage === 'debates' && page !== 'debates') {
    clearInterval(_debatesAutoRefresh);
  }
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
    container.innerHTML = debates.map(d => {
      const vc = d.verdict_confidence ? d.verdict_confidence.toFixed(0) : null;
      const verdictColour = d.verdict === 'pass' ? '#4caf50' : d.verdict === 'fail' ? '#e5534b' : '#ffd54f';
      const verdictLabel = d.verdict === 'pass' ? 'YES' : d.verdict === 'fail' ? 'NO' : (d.verdict || '').toUpperCase();
      const verdictBadge = d.verdict
        ? `<span style="background:${verdictColour}22;color:${verdictColour};border:1px solid ${verdictColour}55;border-radius:4px;padding:0.15rem 0.5rem;font-size:0.72rem;font-weight:600">${verdictLabel} ${vc ? vc+'%' : ''}</span>`
        : '';
      const scores = d.verdict_scores || {};
      const scoreStr = Object.entries(scores).map(([a,s]) => `${a}: ${s}/100`).join(' · ');
      return `
        <div class="debate-item" onclick="viewDebate(${d.id})">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:1rem">
            <div class="debate-topic">${d.topic.slice(0, 180)}</div>
            <div style="display:flex;gap:0.4rem;flex-shrink:0">${verdictBadge} ${statusBadge(d.status)}</div>
          </div>
          <div class="debate-meta" style="margin-top:0.5rem">
            <span>👥 ${d.participants.join(' · ')}</span>
            <span>🕐 ${timeAgo(d.started_at)}</span>
            ${d.ended_at ? `<button class="btn btn-outline" style="padding:0.2rem 0.6rem;font-size:0.7rem" onclick="event.stopPropagation();downloadDebate(${d.id})">⬇ Export</button>` : ''}
          </div>
          ${scoreStr ? `<div style="margin-top:0.4rem;font-size:0.75rem;color:var(--text-muted)">${scoreStr}</div>` : ''}
          ${d.summary ? `<div style="margin-top:0.75rem;font-size:0.83rem;color:var(--text-muted);border-top:1px solid var(--border);padding-top:0.75rem">${d.summary.slice(0, 300)}…</div>` : ''}
        </div>
      `;
    }).join('');
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

async function loadDebate(id) {
  activeDebateId = id;
  const feed = document.getElementById('message-feed');
  feed.innerHTML = '<div class="loading-row"><div class="loader"></div><p style="margin-top:1rem">Loading debate…</p></div>';

  // Populate participant sidebar
  try {
    const d = await get(`/api/debates/${id}`);
    const colours = ['var(--accent)', '#4fc3f7', 'var(--accent2)', '#81c784', '#ffb74d', '#ce93d8'];
    document.getElementById('live-participants').innerHTML = d.participants.map((name, i) => `
      <div class="sidebar-agent" style="margin-bottom:0.5rem">
        <div class="agent-dot" style="background:${colours[i % colours.length]};width:10px;height:10px;border-radius:50%;flex-shrink:0"></div>
        <div><strong>${name}</strong></div>
      </div>
    `).join('');
    // Pre-fill topic
    if (d.topic) document.getElementById('live-topic').textContent = d.topic.slice(0, 120);
    // Reset verdict panel
    document.getElementById('verdict-panel').style.display = 'none';
  } catch(e) { /* non-fatal */ }

  if (activeDebateWs) {
    activeDebateWs.close();
    activeDebateWs = null;
  }

  const wsStatus = document.getElementById('ws-status-dot');
  const wsText = document.getElementById('ws-status-text');
  const ws = new WebSocket(wsUrl(`/api/debates/${id}/stream`));
  activeDebateWs = ws;

  ws.onopen = () => {
    wsStatus.classList.add('live');
    wsText.textContent = 'Connected';
    wsText.style.color = 'var(--green, #4caf50)';
  };
  ws.onclose = () => {
    wsStatus.classList.remove('live');
    wsText.textContent = 'Disconnected';
    wsText.style.color = 'var(--text-muted)';
  };

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'ping') return;

    if (msg.type === 'historical' || msg.type === 'agent_done') {
      appendMessage(feed, msg);
    } else if (msg.type === 'agent_chunk') {
      appendChunk(feed, msg);
    } else if (msg.type === 'round_start') {
      appendDivider(feed, msg.content);
    } else if (msg.type === 'debate_start') {
      feed.innerHTML = '';
      document.getElementById('live-topic').textContent = msg.content.replace('Debate started: ', '');
      appendDivider(feed, '🏁 Debate Started');
    } else if (msg.type === 'debate_end') {
      appendDivider(feed, '🏆 Debate Complete');
      // Show verdict panel
      if (msg.verdict) {
        const vp = document.getElementById('verdict-panel');
        const vd = document.getElementById('verdict-display');
        const vc = msg.verdict_confidence ?? 0;
        const scores = msg.agent_scores ?? {};
        const verdictColour = msg.verdict === 'pass' ? '#4caf50' : msg.verdict === 'fail' ? '#e5534b' : '#ffd54f';
        const verdictLabel = msg.verdict === 'pass' ? 'YES' : msg.verdict === 'fail' ? 'NO' : (msg.verdict || '').toUpperCase();
        vd.innerHTML = `
          <div style="font-size:1.4rem;font-weight:700;color:${verdictColour};margin-bottom:0.5rem">
            ${verdictLabel} · ${vc.toFixed(0)}%
          </div>
          <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:0.75rem">Resolution confidence</div>
          ${Object.entries(scores).map(([agent, score]) =>
            `<div style="display:flex;justify-content:space-between;font-size:0.8rem;margin-bottom:0.25rem">
               <span>${agent}</span><span style="color:${verdictColour}">${score}/100</span>
             </div>`
          ).join('')}
        `;
        vp.style.display = '';
      }
      if (msg.content) {
        const el = document.createElement('div');
        el.className = 'message-bubble system';
        el.innerHTML = `<div class="message-agent">Summary</div><div class="message-content">${msg.content}</div>`;
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
  container.innerHTML = facts.map(f => {
    const t2 = f.t2_lookups || 0;
    const t3 = f.t3_lookups || 0;
    const usageBadges = [
      t2 > 0 ? `<span style="background:rgba(79,195,247,0.15);color:#4fc3f7;border:1px solid rgba(79,195,247,0.3);border-radius:4px;padding:0.1rem 0.4rem;font-size:0.68rem">T2 ×${t2}</span>` : '',
      t3 > 0 ? `<span style="background:rgba(129,199,132,0.15);color:#81c784;border:1px solid rgba(129,199,132,0.3);border-radius:4px;padding:0.1rem 0.4rem;font-size:0.68rem">T3 ×${t3}</span>` : '',
    ].filter(Boolean).join(' ');
    return `
      <div class="fact-card">
        <div class="fact-title" style="display:flex;align-items:center;gap:0.5rem;flex-wrap:wrap">
          ${f.title}
          ${f.is_seed ? '<span style="color:var(--text-muted);font-size:0.7rem">[seed]</span>' : ''}
          ${usageBadges}
        </div>
        <div class="confidence-bar"><div class="confidence-fill" style="width:${f.confidence*100}%"></div></div>
        <div class="fact-content" style="margin-top:0.75rem">${f.content}</div>
        <div class="fact-meta"><span>Confidence: ${(f.confidence*100).toFixed(0)}%</span><span>${timeAgo(f.created_at)}</span></div>
      </div>
    `;
  }).join('');
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

// KNOWLEDGE GRAPH
pages.graph = async () => {
  const loading = document.getElementById('graph-loading');
  loading.style.display = 'flex';
  try {
    const data = await get('/api/knowledge/graph');
    loading.style.display = 'none';
    renderKnowledgeGraph(data);
  } catch(e) {
    loading.innerHTML = `<p style="color:var(--rejected)">Error: ${e.message}</p>`;
  }
};

function renderKnowledgeGraph({ nodes, edges }) {
  const svg = document.getElementById('knowledge-graph-svg');
  const container = document.getElementById('graph-container');
  const tooltip = document.getElementById('graph-tooltip');
  const W = container.clientWidth;
  const H = container.clientHeight;

  // Clear previous render
  while (svg.firstChild) svg.removeChild(svg.firstChild);

  if (!nodes.length) {
    svg.innerHTML = '<text x="50%" y="50%" text-anchor="middle" fill="#666" font-size="14">No graph data yet — trigger a debate first.</text>';
    return;
  }

  const nodeColour = (n) => {
    if (n.type === 'tier1') return '#e5534b';
    if (n.type === 'tier2') return '#4fc3f7';
    if (n.type === 'tier3') return '#81c784';
    if (n.type === 'theory') return '#ffb74d';
    if (n.type === 'fact')   return '#ce93d8';
    if (n.type === 'debate') return '#ffd54f';
    return '#888';
  };

  const nodeRadius = (n) => {
    if (n.type.startsWith('tier')) return 18;
    if (n.type === 'debate') return 14;
    return 10;
  };

  // Build D3 data
  const nodeMap = {};
  nodes.forEach(n => { nodeMap[n.id] = n; });
  const links = edges.map(e => ({ source: e.source, target: e.target, type: e.type }))
    .filter(e => nodeMap[e.source] && nodeMap[e.target]);

  const d3svg = d3.select(svg)
    .attr('viewBox', `0 0 ${W} ${H}`);

  const defs = d3svg.append('defs');
  defs.append('marker').attr('id', 'arrow').attr('viewBox', '0 -4 8 8')
    .attr('refX', 20).attr('markerWidth', 6).attr('markerHeight', 6).attr('orient', 'auto')
    .append('path').attr('d', 'M0,-4L8,0L0,4').attr('fill', '#444');

  const g = d3svg.append('g');

  // Zoom + pan
  d3svg.call(d3.zoom().scaleExtent([0.2, 3]).on('zoom', (event) => {
    g.attr('transform', event.transform);
  }));

  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(d => {
      if (d.type === 'participated') return 120;
      if (d.type === 'submitted') return 80;
      return 60;
    }).strength(0.5))
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(W / 2, H / 2))
    .force('collision', d3.forceCollide().radius(d => nodeRadius(d) + 8));

  const edgeColour = (type) => {
    if (type === 'submitted') return '#ffb74d66';
    if (type === 'validated') return '#4fc3f766';
    if (type === 'promoted_to_fact') return '#ce93d866';
    if (type === 'used_by_t2') return '#4fc3f744';
    if (type === 'used_by_t3') return '#81c78444';
    if (type === 'participated') return '#ffffff22';
    return '#55555566';
  };

  const link = g.append('g').selectAll('line').data(links).join('line')
    .attr('stroke', d => edgeColour(d.type))
    .attr('stroke-width', 1.5)
    .attr('marker-end', 'url(#arrow)');

  const node = g.append('g').selectAll('g').data(nodes).join('g')
    .attr('cursor', 'pointer')
    .call(d3.drag()
      .on('start', (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag',  (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on('end',   (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
    );

  node.append('circle')
    .attr('r', d => nodeRadius(d))
    .attr('fill', d => nodeColour(d))
    .attr('stroke', '#1a1a1a')
    .attr('stroke-width', 1.5);

  node.append('text')
    .attr('text-anchor', 'middle')
    .attr('dy', d => nodeRadius(d) + 12)
    .attr('fill', '#ccc')
    .attr('font-size', '9px')
    .text(d => d.label.slice(0, 18));

  node.on('mouseover', (event, d) => {
    let html = `<strong>${d.label}</strong><br><em style="color:#888">${d.type}</em>`;
    if (d.tier) html += `<br>Tier ${d.tier}`;
    if (d.specialty) html += `<br>${d.specialty}`;
    if (d.confidence != null) html += `<br>Confidence: ${(d.confidence * 100).toFixed(0)}%`;
    if (d.status) html += `<br>Status: ${d.status}`;
    if (d.verdict) {
      const vc = (d.verdict_confidence || 0).toFixed(0);
      const graphVerdictLabel = d.verdict === 'pass' ? 'YES' : d.verdict === 'fail' ? 'NO' : 'DRAW';
      const vc_color = d.verdict === 'pass' ? '#4caf50' : d.verdict === 'fail' ? '#e5534b' : '#ffd54f';
      html += `<br><span style="font-weight:700;font-size:1.15em;color:${vc_color}">${graphVerdictLabel}</span>`;
      html += `<br><span style="color:#999;font-size:0.82em">${vc}% resolution confidence</span>`;
    }
    if (d.t2_lookups) html += `<br>T2 lookups: ${d.t2_lookups}`;
    if (d.t3_lookups) html += `<br>T3 lookups: ${d.t3_lookups}`;
    tooltip.innerHTML = html;
    tooltip.style.display = 'block';
  }).on('mousemove', (event) => {
    tooltip.style.left = (event.clientX + 14) + 'px';
    tooltip.style.top  = (event.clientY - 10) + 'px';
  }).on('mouseleave', () => {
    tooltip.style.display = 'none';
  });

  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });
}

// ── Agent Feed ───────────────────────────────────────────────────
let feedWs = null;
let feedFilter = 'all';
let feedItems = [];       // all received items (for re-filtering)
let feedLoopRunning = false;
let feedReconnectTimer = null;
let feedStatusPollTimer = null;
let feedStatusPollInFlight = false;
let feedToggleBusy = false;
let feedWsShouldRun = true;

const FEED_MAX_ITEMS = 200;
const FEED_STATUS_POLL_MS = 15000;
const feedDebateMeta = new Map();
let lastLoopContext = { topic: null, category: 'default' };

const CATEGORY_EMOJI = {
  breaking: '🚨', conspiracy: '🕵️', technical: '🔧',
  strategy: '♟', prediction: '📊', historical: '📜', default: '💬',
};
const CATEGORY_COLOUR = {
  breaking: '#e5534b', conspiracy: '#ce93d8', technical: '#4fc3f7',
  strategy: '#ffb74d', prediction: '#81c784', historical: '#ffd54f',
};

function setFeedFilter(cat) {
  feedFilter = cat;
  document.querySelectorAll('.feed-filter').forEach(b => {
    b.classList.toggle('active', b.dataset.cat === cat);
  });
  renderFeedItems();
}

function normalizedTopic(topic) {
  return (topic || '').replace(/\s+/g, ' ').trim().toLowerCase();
}

function topicsMatch(a, b) {
  const na = normalizedTopic(a);
  const nb = normalizedTopic(b);
  if (!na || !nb) return false;
  const shortA = na.slice(0, 80);
  const shortB = nb.slice(0, 80);
  return na === nb || na.includes(shortB) || nb.includes(shortA);
}

function inferFeedCategory(topic, fallback = 'default') {
  const t = normalizedTopic(topic);
  if (!t) return fallback;
  if (t.startsWith('breaking:')) return 'breaking';
  if (t.includes('conspiracy') || t.includes('sandbag') || t.includes('illegal') || t.includes('loophole')) return 'conspiracy';
  if (t.includes('technical') || t.includes('aero') || t.includes('downforce') || t.includes('drs') || t.includes('suspension') || t.includes('power unit')) return 'technical';
  if (t.includes('strategy') || t.includes('undercut') || t.includes('pit') || t.includes('safety car')) return 'strategy';
  if (t.includes('predict') || t.includes('championship') || t.includes('who wins') || t.includes('will ')) return 'prediction';
  if (t.includes('historical') || t.includes('compare') || t.includes('era')) return 'historical';
  return fallback;
}

function rememberDebateMeta(debateId, topic, category) {
  if (!debateId) return;
  const existing = feedDebateMeta.get(debateId) || {};
  feedDebateMeta.set(debateId, {
    topic: topic || existing.topic || '',
    category: category || existing.category || 'default',
  });
  if (feedDebateMeta.size > FEED_MAX_ITEMS) {
    const oldest = feedDebateMeta.keys().next().value;
    feedDebateMeta.delete(oldest);
  }
}

function pushFeedItem(item) {
  feedItems.push(item);
  if (feedItems.length > FEED_MAX_ITEMS) {
    feedItems.splice(0, feedItems.length - FEED_MAX_ITEMS);
  }
}

function updateFeedBanner(status, topic) {
  const banner = document.getElementById('feed-banner');
  if (!banner) return;
  if (status === 'debating' && topic) {
    banner.style.display = '';
    const bt = document.getElementById('feed-banner-topic');
    if (bt) bt.textContent = topic;
    return;
  }
  banner.style.display = 'none';
}

function renderFeedItems() {
  const container = document.getElementById('feed-stream');
  if (!container) return;
  const visible = feedFilter === 'all'
    ? feedItems
    : feedItems.filter(i => i.category === feedFilter);
  if (!visible.length) {
    container.innerHTML = '<p style="color:var(--text-muted);padding:2rem;text-align:center">No agent activity yet in this category. Debates will appear here automatically.</p>';
    return;
  }
  container.innerHTML = visible.slice().reverse().map(item => {
    const cat = item.category || 'default';
    const emoji = CATEGORY_EMOJI[cat] || CATEGORY_EMOJI.default;
    const colour = CATEGORY_COLOUR[cat] || '#888';
    const snippet = (item.content || '').slice(0, 280);
    const agents = item.agents ? item.agents.join(', ') : (item.agent || 'System');
    const clickable = Number(item.debate_id) > 0;
    const onClick = clickable ? ` onclick="viewDebate(${item.debate_id})"` : '';
    return `
      <div class="feed-card"${onClick} style="cursor:${clickable ? 'pointer' : 'default'}">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.5rem">
          <div style="display:flex;align-items:center;gap:0.5rem">
            <span style="background:${colour}22;color:${colour};border:1px solid ${colour}44;border-radius:4px;padding:0.1rem 0.5rem;font-size:0.7rem;font-weight:600;text-transform:uppercase">${emoji} ${cat}</span>
            ${item.verdict ? `<span style="background:${item.verdict==='pass'?'#4caf5022':item.verdict==='fail'?'#e5534b22':'#ffd54f22'};color:${item.verdict==='pass'?'#4caf50':item.verdict==='fail'?'#e5534b':'#ffd54f'};border-radius:4px;padding:0.1rem 0.45rem;font-size:0.7rem;font-weight:700">${item.verdict==='pass'?'YES':item.verdict==='fail'?'NO':'DRAW'}</span>` : ''}
          </div>
          <span style="font-size:0.72rem;color:var(--text-muted)">${timeAgo(item.ts)}</span>
        </div>
        <div style="font-weight:600;font-size:0.9rem;margin-bottom:0.4rem;line-height:1.4">${(item.topic || item.content || '').slice(0, 140)}</div>
        ${snippet && item.type !== 'debate_start' ? `<div style="font-size:0.82rem;color:var(--text-muted);line-height:1.5;border-top:1px solid var(--border);padding-top:0.4rem;margin-top:0.4rem">${snippet}${(item.content||'').length > 280 ? '…' : ''}</div>` : ''}
        ${agents && item.type !== 'loop_status' ? `<div style="font-size:0.72rem;color:var(--text-muted);margin-top:0.4rem">👥 ${agents}</div>` : ''}
      </div>
    `;
  }).join('');
}

function processFeedEvent(msg) {
  const ts = msg.timestamp || new Date().toISOString();

  if (msg.type === 'loop_status') {
    const category = msg.category || inferFeedCategory(msg.topic, 'default');
    feedLoopRunning = msg.status === 'debating' || msg.status === 'cooldown' || msg.running === true;
    if (msg.status === 'debating' && msg.topic) {
      lastLoopContext = { topic: msg.topic, category };
    }
    updateLoopStatusBar(msg);
    updateFeedBanner(msg.status, msg.topic);
    return;
  }

  if (msg.type === 'ping') return;

  // Build a feed item from agent_done, debate_end, debate_start
  if (msg.type === 'debate_start') {
    const topic = msg.content?.replace('Debate started: ', '') || msg.topic || '';
    const category = msg.category ||
      (topicsMatch(topic, lastLoopContext.topic) ? lastLoopContext.category : inferFeedCategory(topic, 'default'));
    rememberDebateMeta(msg.debate_id, topic, category);
    pushFeedItem({
      type: 'debate_start',
      debate_id: msg.debate_id,
      topic,
      category,
      agent: 'System',
      content: '',
      ts,
    });
    renderFeedItems();
  } else if (msg.type === 'agent_done' && msg.round === 3) {
    // Only surface Round 3 conclusions as feed items (conclusions are the richest)
    const meta = feedDebateMeta.get(msg.debate_id) || {};
    const topic = msg.topic || meta.topic || '';
    const category = msg.category || meta.category || inferFeedCategory(topic, 'default');
    rememberDebateMeta(msg.debate_id, topic, category);
    pushFeedItem({
      type: 'agent_done',
      debate_id: msg.debate_id,
      topic,
      category,
      agent: msg.agent,
      content: msg.content,
      ts,
    });
    renderFeedItems();
  } else if (msg.type === 'debate_end') {
    // Replace or add verdict item
    const meta = feedDebateMeta.get(msg.debate_id) || {};
    const topic = msg.topic || meta.topic || msg.content?.slice(0, 160) || '';
    const category = msg.category || meta.category || inferFeedCategory(topic, 'default');
    rememberDebateMeta(msg.debate_id, topic, category);
    const existing = feedItems.findIndex(i => i.debate_id === msg.debate_id && (i.type === 'debate_start' || i.type === 'debate_end'));
    const verdictItem = {
      type: 'debate_end',
      debate_id: msg.debate_id,
      topic,
      category,
      verdict: msg.verdict,
      content: msg.content || '',
      agents: msg.agent_scores ? Object.keys(msg.agent_scores) : [],
      ts,
    };
    if (existing >= 0) {
      feedItems[existing] = verdictItem;
    } else {
      pushFeedItem(verdictItem);
    }
    renderFeedItems();
    // Refresh debates list if open
    if (currentPage === 'debates') pages.debates();
  }
}

function updateLoopStatusBar(msg) {
  const label = document.getElementById('loop-status-label');
  const topicEl = document.getElementById('loop-status-topic');
  const btn = document.getElementById('loop-toggle-btn');
  if (!label) return;

  if (msg.status === 'debating') {
    label.textContent = `🔴 LIVE — ${msg.debates_run ?? 0} debates`;
    label.style.color = '#e5534b';
    if (topicEl && msg.topic) topicEl.textContent = msg.topic.slice(0, 50);
  } else if (msg.status === 'cooldown') {
    label.textContent = `⏳ ${msg.debates_run ?? 0} debates — cooldown`;
    label.style.color = '#ffd54f';
    if (topicEl) topicEl.textContent = 'Next debate starting soon…';
  } else if (!msg.running) {
    label.textContent = '⏸ Agents Paused';
    label.style.color = 'var(--text-muted)';
    if (topicEl) topicEl.textContent = 'Loop paused';
  }

  if (btn) {
    const running = msg.status === 'debating' || msg.status === 'cooldown';
    btn.textContent = running ? '⏸ Pause Agents' : '▶ Resume Agents';
    feedLoopRunning = running;
  }
}

async function syncLoopStatus() {
  if (feedStatusPollInFlight) return;
  feedStatusPollInFlight = true;
  try {
    const s = await get('/api/loop/status');
    const status = s.running ? (s.current_topic ? 'debating' : 'cooldown') : 'paused';
    const category = s.current_category || inferFeedCategory(s.current_topic, 'default');
    if (s.running && s.current_topic) {
      lastLoopContext = { topic: s.current_topic, category };
    }
    updateLoopStatusBar({
      status,
      running: s.running,
      debates_run: s.debates_run,
      topic: s.current_topic,
      category,
    });
    updateFeedBanner(status, s.current_topic);
  } catch (_) {
    // best effort only
  } finally {
    feedStatusPollInFlight = false;
  }
}

function startFeedStatusPolling() {
  clearInterval(feedStatusPollTimer);
  feedStatusPollTimer = setInterval(() => {
    syncLoopStatus();
  }, FEED_STATUS_POLL_MS);
}

function connectFeedWs(force = false) {
  if (!force && feedWs && (feedWs.readyState === WebSocket.OPEN || feedWs.readyState === WebSocket.CONNECTING)) {
    return;
  }
  if (feedReconnectTimer) {
    clearTimeout(feedReconnectTimer);
    feedReconnectTimer = null;
  }
  if (feedWs) {
    try {
      feedWs.onclose = null;
      feedWs.close();
    } catch (_) {}
    feedWs = null;
  }

  const ws = new WebSocket(wsUrl('/api/loop/feed'));
  feedWs = ws;
  const dot = document.getElementById('feed-ws-dot');
  const txt = document.getElementById('feed-ws-text');

  ws.onopen = () => {
    if (feedWs !== ws) return;
    if (dot) dot.classList.add('live');
    if (txt) { txt.textContent = 'Connected'; txt.style.color = 'var(--green, #4caf50)'; }
    // Clear loader
    const container = document.getElementById('feed-stream');
    if (container && container.querySelector('.loading-row')) {
      container.innerHTML = '';
      renderFeedItems();
    }
    syncLoopStatus();
  };

  ws.onclose = () => {
    if (feedWs !== ws) return;
    feedWs = null;
    if (dot) dot.classList.remove('live');
    if (txt) { txt.textContent = 'Reconnecting…'; txt.style.color = 'var(--text-muted)'; }
    // Reconnect after 3s
    if (feedWsShouldRun) {
      feedReconnectTimer = setTimeout(() => connectFeedWs(), 3000);
    }
  };

  ws.onerror = () => {
    try { ws.close(); } catch (_) {}
  };

  ws.onmessage = (e) => {
    try { processFeedEvent(JSON.parse(e.data)); } catch (_) {}
  };
}

pages.feed = () => {
  connectFeedWs();
  syncLoopStatus();
  startFeedStatusPolling();
};

window.toggleLoop = async () => {
  if (feedToggleBusy) return;
  feedToggleBusy = true;
  const btn = document.getElementById('loop-toggle-btn');
  const previousLabel = btn ? btn.textContent : '';
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Working…';
  }
  try {
    const status = await get('/api/loop/status');
    let result;
    if (status.running) {
      result = await post('/api/loop/stop', {});
      toast('Agent loop paused');
    } else {
      result = await post('/api/loop/start', {});
      toast('Agent loop resumed');
    }
    const statusText = result.running ? (result.current_topic ? 'debating' : 'cooldown') : 'paused';
    updateLoopStatusBar({
      status: statusText,
      running: result.running,
      debates_run: result.debates_run,
      topic: result.current_topic,
    });
    if (result.running && result.current_topic) {
      const category = result.current_category || inferFeedCategory(result.current_topic, 'default');
      lastLoopContext = { topic: result.current_topic, category };
    }
    updateFeedBanner(statusText, result.current_topic);
  } catch (e) {
    toast('Error: ' + e.message);
  } finally {
    feedToggleBusy = false;
    if (btn) {
      btn.disabled = false;
      if (btn.textContent === 'Working…') btn.textContent = previousLabel;
    }
    syncLoopStatus();
  }
};

// ── Auto-refresh debates list ─────────────────────────────────────
let _debatesAutoRefresh = null;
let _debatesRefreshInFlight = false;

const _origDebatesPage = pages.debates;
pages.debates = async () => {
  if (_debatesRefreshInFlight) return;
  _debatesRefreshInFlight = true;
  try {
    await _origDebatesPage();
  } finally {
    _debatesRefreshInFlight = false;
  }
  clearInterval(_debatesAutoRefresh);
  _debatesAutoRefresh = setInterval(async () => {
    if (currentPage !== 'debates' || _debatesRefreshInFlight) return;
    _debatesRefreshInFlight = true;
    try {
      await _origDebatesPage();
    } finally {
      _debatesRefreshInFlight = false;
    }
  }, 30000);
};

// ── Init ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('nav button[data-page]').forEach(btn => {
    btn.addEventListener('click', () => navigate(btn.dataset.page));
  });
  navigate('home');

  // Connect feed WS in background so header status bar stays live
  connectFeedWs();
  startFeedStatusPolling();
  syncLoopStatus();
});
