'use strict';

const API = '';
let state = {
  tab: 'show',
  imdbId: '',
  title: '',
  seasons: [],
  activeSeason: null,
  episodes: [],
  statuses: {},  // "S01E01" -> EpisodeStatus
  jobs: [],
  settings: {},
  fetchingAll: false,
};

// ── Tab nav ──────────────────────────────────────────────────────────────────

document.querySelectorAll('nav button').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

function switchTab(tab) {
  state.tab = tab;
  document.querySelectorAll('nav button').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === `tab-${tab}`));
  if (tab === 'jobs') loadJobs();
  if (tab === 'settings') loadSettings();
}

// ── Show tab ─────────────────────────────────────────────────────────────────

document.getElementById('search-btn').addEventListener('click', searchShow);
document.getElementById('imdb-input').addEventListener('keydown', e => { if (e.key === 'Enter') searchShow(); });

async function searchShow() {
  const input = document.getElementById('imdb-input').value.trim();
  if (!input) return;
  state.imdbId = input.startsWith('tt') ? input : `tt${input}`;

  setLoading('episode-grid', 'Loading show info…');

  try {
    const [titleRes, epsRes] = await Promise.all([
      apiFetch(`/shows/${state.imdbId}/title`),
      apiFetch(`/shows/${state.imdbId}/episodes`),
    ]);

    state.title = titleRes.title;
    state.episodes = epsRes.map(e => ({ ...e, season: Number(e.season), episode: Number(e.episode) }));

    console.log('episodes raw sample:', epsRes[0]);
    const seasonNums = [...new Set(state.episodes.map(e => e.season))].sort((a, b) => a - b);
    console.log('season nums:', seasonNums);
    state.seasons = seasonNums;
    state.activeSeason = seasonNums[0] ?? 1;

    renderShowHeader();
    await loadStatuses();
    renderEpisodes();
  } catch (err) {
    console.error('searchShow error:', err);
    setError('episode-grid', `Failed to load show: ${err.message}`);
  }
}

function renderShowHeader() {
  const wrap = document.getElementById('show-header');
  wrap.innerHTML = `
    <div class="show-header">
      <h2>${esc(state.title)}</h2>
      <span class="text-muted" style="color:var(--text-muted);font-size:13px">${esc(state.imdbId)}</span>
    </div>
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
      <div class="season-selector" id="season-btns"></div>
      <button class="btn btn-sm" id="fetch-all-btn">Fetch all S${state.activeSeason} subtitles</button>
    </div>
  `;

  const btnWrap = document.getElementById('season-btns');
  state.seasons.forEach(s => {
    const b = document.createElement('button');
    b.className = `season-btn${s === state.activeSeason ? ' active' : ''}`;
    b.textContent = `Season ${s}`;
    b.addEventListener('click', () => {
      state.activeSeason = s;
      btnWrap.querySelectorAll('.season-btn').forEach(x => x.classList.toggle('active', x.textContent === `Season ${s}`));
      document.getElementById('fetch-all-btn').textContent = `Fetch all S${s} subtitles`;
      renderEpisodes();
    });
    btnWrap.appendChild(b);
  });

  document.getElementById('fetch-all-btn').addEventListener('click', fetchAllSeason);
}

async function fetchAllSeason() {
  const eps = state.episodes.filter(e => e.season === state.activeSeason);
  for (const ep of eps) {
    await fetchSingle(ep.series_imdb_id, ep.season, ep.episode);
  }
}

async function loadStatuses() {
  const eps = state.episodes;
  await Promise.allSettled(
    eps.map(async ep => {
      const key = epKey(ep.season, ep.episode);
      try {
        const s = await apiFetch(`/subtitles/status/${ep.series_imdb_id}/${ep.season}/${ep.episode}`);
        state.statuses[key] = s;
      } catch {}
    })
  );
}

function renderEpisodes() {
  const eps = state.episodes.filter(e => e.season === state.activeSeason);
  const grid = document.getElementById('episode-grid');
  grid.innerHTML = '';

  if (eps.length === 0) {
    grid.innerHTML = '<div class="empty-state">No episodes found for this season.</div>';
    return;
  }

  eps.forEach(ep => {
    const key = epKey(ep.season, ep.episode);
    const status = state.statuses[key];
    grid.appendChild(buildEpCard(ep, status));
  });
}

function buildEpCard(ep, status) {
  const div = document.createElement('div');
  div.className = 'ep-card';
  div.id = `card-${epKey(ep.season, ep.episode)}`;

  const statusInfo = statusDisplay(status);
  const pct = (status?.status === 'translating') ? getJobProgress(ep) : null;

  div.innerHTML = `
    <div class="ep-meta">
      <span class="ep-label">S${ep.season.toString().padStart(2,'0')}E${ep.episode.toString().padStart(2,'0')}</span>
      <span class="badge badge-${statusInfo.cls}">${statusInfo.label}</span>
    </div>
    <div class="ep-title">${esc(ep.title)}</div>
    ${pct !== null ? `<div class="progress-wrap"><div class="progress-bar" style="width:${pct}%"></div></div>` : ''}
    <div class="ep-actions">
      ${status?.srt_path
        ? `<button class="btn btn-sm btn-ghost" onclick="downloadSrt('${ep.series_imdb_id}',${ep.season},${ep.episode})">Download SRT</button>`
        : `<button class="btn btn-sm" onclick="fetchSingle('${ep.series_imdb_id}',${ep.season},${ep.episode})">Fetch Subtitles</button>`}
    </div>
  `;
  return div;
}

async function fetchSingle(seriesId, season, episode) {
  const key = epKey(season, episode);
  const card = document.getElementById(`card-${key}`);
  if (card) {
    card.querySelector('.ep-actions').innerHTML = '<span class="spinner"></span>';
  }
  try {
    const status = await apiFetch(`/subtitles/fetch/${seriesId}/${season}/${episode}`, { method: 'POST' });
    state.statuses[key] = status;
  } catch {}
  refreshCard(seriesId, season, episode);
}

async function refreshCard(seriesId, season, episode) {
  const key = epKey(season, episode);
  const ep = state.episodes.find(e => e.season === season && e.episode === episode);
  if (!ep) return;

  try {
    const status = await apiFetch(`/subtitles/status/${seriesId}/${season}/${episode}`);
    state.statuses[key] = status;
  } catch {}

  const card = document.getElementById(`card-${key}`);
  if (card) {
    const newCard = buildEpCard(ep, state.statuses[key]);
    card.replaceWith(newCard);
  }
}

function downloadSrt(seriesId, season, episode) {
  const url = `/subtitles/download/${seriesId}/${season}/${episode}`;
  const a = document.createElement('a');
  a.href = url;
  a.download = '';
  a.click();
}

// ── Jobs tab ─────────────────────────────────────────────────────────────────

async function loadJobs() {
  const list = document.getElementById('job-list');
  list.innerHTML = '<div class="empty-state"><span class="spinner"></span></div>';
  try {
    const jobs = await apiFetch('/jobs');
    state.jobs = jobs;
    renderJobs();
  } catch {
    list.innerHTML = '<div class="empty-state">Failed to load jobs.</div>';
  }
}

function renderJobs() {
  const list = document.getElementById('job-list');
  if (state.jobs.length === 0) {
    list.innerHTML = '<div class="empty-state">No translation jobs yet.</div>';
    return;
  }
  list.innerHTML = '';
  state.jobs.forEach(job => list.appendChild(buildJobCard(job)));
}

function buildJobCard(job) {
  const div = document.createElement('div');
  div.className = 'job-card';
  div.id = `job-${job.id}`;

  const statusInfo = jobStatusDisplay(job.status);
  const pct = job.progress ?? 0;

  div.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
      <div class="job-title">S${job.season.toString().padStart(2,'0')}E${job.episode.toString().padStart(2,'0')} — ${esc(job.series_imdb_id)}</div>
      <span class="badge badge-${statusInfo.cls}">${statusInfo.label}</span>
    </div>
    <div class="job-meta">Source: ${esc(job.source_language)} → English &nbsp;·&nbsp; ${job.created_at.slice(0,10)}</div>
    ${(job.status === 'running' || job.status === 'queued') ? `
      <div class="progress-wrap"><div class="progress-bar" style="width:${pct}%"></div></div>
      <div style="color:var(--text-muted);font-size:12px;margin-top:6px">${pct}%</div>
    ` : ''}
    ${job.error ? `<div style="color:var(--red);font-size:12px;margin-top:6px">${esc(job.error)}</div>` : ''}
  `;
  return div;
}

// ── Settings tab ─────────────────────────────────────────────────────────────

async function loadSettings() {
  try {
    state.settings = await apiFetch('/settings');
    renderSettings();
  } catch {}
}

function renderSettings() {
  const s = state.settings;

  // Ollama
  document.getElementById('ollama-host').value = s.ollama_host || 'http://localhost:11434';
  document.getElementById('ollama-model').value = s.ollama_model || 'qwen2.5:7b';

  // API key badges
  if (s.subdl_configured) {
    const b = document.getElementById('subdl-badge');
    b.className = 'badge badge-english';
    b.textContent = s.subdl_api_key || 'Set';
  }
  if (s.opensubtitles_configured) {
    const b = document.getElementById('os-badge');
    b.className = 'badge badge-english';
    b.textContent = s.opensubtitles_api_key || 'Set';
  }

  // Username
  if (s.opensubtitles_username) {
    document.getElementById('os-username').value = s.opensubtitles_username;
  }
}

document.getElementById('save-keys-btn').addEventListener('click', async () => {
  const payload = {};
  const subdl = document.getElementById('subdl-key').value.trim();
  const osKey = document.getElementById('os-key').value.trim();
  const osUser = document.getElementById('os-username').value.trim();
  const osPass = document.getElementById('os-password').value.trim();

  if (subdl) payload.subdl_api_key = subdl;
  if (osKey) payload.opensubtitles_api_key = osKey;
  if (osUser) payload.opensubtitles_username = osUser;
  if (osPass) payload.opensubtitles_password = osPass;

  if (!Object.keys(payload).length) return;

  try {
    await apiFetch('/settings', { method: 'POST', body: JSON.stringify(payload) });
    const el = document.getElementById('save-status');
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 5000);
    // Clear password fields, reload to update badges
    document.getElementById('subdl-key').value = '';
    document.getElementById('os-key').value = '';
    document.getElementById('os-password').value = '';
    await loadSettings();
  } catch (err) {
    alert('Failed to save: ' + err.message);
  }
});

document.getElementById('save-ollama-btn').addEventListener('click', async () => {
  const payload = {
    ollama_host: document.getElementById('ollama-host').value.trim() || 'http://localhost:11434',
    ollama_model: document.getElementById('ollama-model').value.trim() || 'qwen2.5:7b',
  };
  try {
    await apiFetch('/settings', { method: 'POST', body: JSON.stringify(payload) });
    const el = document.getElementById('save-ollama-status');
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 5000);
  } catch (err) {
    alert('Failed to save: ' + err.message);
  }
});

// ── SSE job stream ────────────────────────────────────────────────────────────

function startSSE() {
  const es = new EventSource('/jobs/stream/all');
  es.onmessage = e => {
    try {
      const evt = JSON.parse(e.data);
      handleJobEvent(evt);
    } catch {}
  };
}

function handleJobEvent(evt) {
  const idx = state.jobs.findIndex(j => j.id === evt.job_id);
  if (idx >= 0) {
    if (evt.progress !== undefined) state.jobs[idx].progress = evt.progress;
    if (evt.status) state.jobs[idx].status = evt.status;
    const card = document.getElementById(`job-${evt.job_id}`);
    if (card) {
      card.replaceWith(buildJobCard(state.jobs[idx]));
    }
  }
  // Refresh episode card if job completed/failed
  if (evt.status === 'completed' || evt.status === 'failed') {
    const job = state.jobs[idx];
    if (job) {
      refreshCard(job.series_imdb_id, job.season, job.episode);
    }
  }
}

function getJobProgress(ep) {
  const job = state.jobs.find(j =>
    j.series_imdb_id === ep.series_imdb_id &&
    j.season === ep.season &&
    j.episode === ep.episode &&
    (j.status === 'running' || j.status === 'queued')
  );
  return job ? (job.progress ?? 0) : 0;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function epKey(season, episode) {
  return `S${season.toString().padStart(2,'0')}E${episode.toString().padStart(2,'0')}`;
}

function statusDisplay(status) {
  if (!status) return { cls: 'missing', label: '? Unknown' };
  const map = {
    english:     { cls: 'english',     label: '✓ English' },
    translated:  { cls: 'translated',  label: '✓ Translated' },
    translating: { cls: 'translating', label: '⟳ Translating' },
    source_only: { cls: 'source_only', label: '⟳ Queued' },
    missing:     { cls: 'missing',     label: '✗ Not found' },
  };
  return map[status.status] ?? { cls: 'missing', label: status.status };
}

function jobStatusDisplay(status) {
  const map = {
    queued:    { cls: 'translating', label: 'Queued' },
    running:   { cls: 'translating', label: 'Running' },
    completed: { cls: 'english',     label: 'Done' },
    failed:    { cls: 'error',       label: 'Failed' },
  };
  return map[status] ?? { cls: 'missing', label: status };
}

function esc(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function setLoading(id, msg) {
  document.getElementById(id).innerHTML = `<div class="empty-state"><span class="spinner"></span> ${msg}</div>`;
}

function setError(id, msg) {
  document.getElementById(id).innerHTML = `<div class="empty-state" style="color:var(--red)">${esc(msg)}</div>`;
}

async function apiFetch(path, opts = {}) {
  const res = await fetch(API + path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

// ── Init ──────────────────────────────────────────────────────────────────────

switchTab('show');
startSSE();
