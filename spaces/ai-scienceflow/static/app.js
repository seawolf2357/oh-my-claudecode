// ═══ AI Scientist v3 Frontend ═══

let ws = null;
let selectedIdeaIdx = -1;

// ── Step Navigation ──
function showStep(n) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
  document.getElementById('step' + n).classList.add('active');
  document.querySelector(`.step[data-step="${n}"]`).classList.add('active');
  if (n === 3) connectWS();
  if (n === 4) refreshExpList();
}

// ── Config ──
function onProviderChange() {
  const v = document.getElementById('llmProvider').value;
  document.getElementById('customUrlGroup').style.display = v === 'custom' ? '' : 'none';
  document.getElementById('customModelGroup').style.display = v === 'custom' ? '' : 'none';
}

async function saveConfig() {
  const provider = document.getElementById('llmProvider').value;
  const key = document.getElementById('apiKey').value;
  const map = { fireworks: 'fireworks_key', anthropic: 'anthropic_key', openai: 'openai_key', custom: 'fireworks_key' };
  const body = {};
  body[map[provider] || 'fireworks_key'] = key;
  try {
    const r = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const d = await r.json();
    const el = document.getElementById('configStatus');
    el.textContent = 'Configuration saved!';
    el.className = 'status-msg ok';
  } catch (e) {
    document.getElementById('configStatus').textContent = 'Error: ' + e;
    document.getElementById('configStatus').className = 'status-msg err';
  }
}

// ── File Upload ──
function handleDrop(e) {
  e.preventDefault();
  e.target.closest('.upload-zone').classList.remove('drag-over');
  if (e.dataTransfer.files.length) uploadFileObj(e.dataTransfer.files[0]);
}

function uploadFile(input) {
  if (input.files.length) uploadFileObj(input.files[0]);
}

async function uploadFileObj(file) {
  const fd = new FormData();
  fd.append('file', file);
  const el = document.getElementById('uploadedFiles');
  el.innerHTML += `<div class="file-item"><span>${file.name}</span><span>Uploading...</span></div>`;

  try {
    const r = await fetch('/api/upload', { method: 'POST', body: fd });
    const d = await r.json();
    el.innerHTML = '';
    el.innerHTML += `<div class="file-item"><span>${d.filename}</span><span>${d.text_length} chars extracted</span></div>`;

    // Show ontology graph
    if (d.ontology && (d.ontology.nodes || []).length > 0) {
      document.getElementById('graphCard').style.display = '';
      renderGraph(d.ontology);
    }
  } catch (e) {
    el.innerHTML += `<div class="file-item"><span>${file.name}</span><span style="color:var(--error)">Error</span></div>`;
  }
}

// ── Ontology Graph (D3.js) ──
function renderGraph(data) {
  const container = document.getElementById('graphContainer');
  container.innerHTML = '';
  const w = container.clientWidth, h = 400;

  const svg = d3.select(container).append('svg').attr('width', w).attr('height', h);
  const g = svg.append('g');
  svg.call(d3.zoom().on('zoom', e => g.attr('transform', e.transform)));

  const colors = { person: '#6366f1', org: '#22c55e', concept: '#f59e0b', event: '#ef4444', method: '#06b6d4' };

  const sim = d3.forceSimulation(data.nodes)
    .force('link', d3.forceLink(data.edges).id(d => d.id).distance(120))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(w / 2, h / 2));

  const link = g.selectAll('.link').data(data.edges).join('line')
    .attr('stroke', '#b0b4c8').attr('stroke-width', 1.5);

  const linkLabel = g.selectAll('.link-label').data(data.edges).join('text')
    .text(d => d.label).attr('fill', '#7b7fa0').attr('font-size', 10).attr('text-anchor', 'middle');

  const node = g.selectAll('.node').data(data.nodes).join('g')
    .call(d3.drag().on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on('end', (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));

  node.append('circle').attr('r', 8).attr('fill', d => colors[d.type] || '#6366f1').attr('stroke', '#fff').attr('stroke-width', 1.5);
  node.append('text').text(d => d.label).attr('dx', 12).attr('dy', 4).attr('fill', '#2d3148').attr('font-size', 12);

  sim.on('tick', () => {
    link.attr('x1', d => d.source.x).attr('y1', d => d.source.y).attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    linkLabel.attr('x', d => (d.source.x + d.target.x) / 2).attr('y', d => (d.source.y + d.target.y) / 2);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });
}

// ── Ideation ──
async function generateIdeas() {
  const btn = document.getElementById('ideaBtn');
  btn.disabled = true; btn.textContent = 'Generating...';
  const topic = document.getElementById('topicInput').value;
  const maxIdeas = parseInt(document.getElementById('maxIdeas').value);

  try {
    const r = await fetch('/api/ideation', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, max_ideas: maxIdeas })
    });
    const d = await r.json();
    if (d.error) { alert(d.error); return; }
    renderIdeas(d.ideas);
  } catch (e) { alert('Error: ' + e); }
  finally { btn.disabled = false; btn.textContent = 'Generate Ideas'; }
}

function renderIdeas(ideas) {
  const el = document.getElementById('ideasContainer');
  if (!ideas.length) { el.innerHTML = '<p class="placeholder">No ideas generated</p>'; return; }
  el.innerHTML = ideas.map((idea, i) => `
    <div class="idea-card" onclick="selectIdea(${i})" id="idea-${i}">
      <h3>${idea.Title || idea.Name || 'Untitled'}</h3>
      <p>${(idea['Short Hypothesis'] || idea.Short_Hypothesis || idea.Abstract || '').substring(0, 200)}...</p>
      <div style="margin-top:8px">
        ${(idea.Experiments || []).slice(0, 3).map(e => `<span class="idea-tag">${e.substring(0, 30)}</span>`).join('')}
      </div>
    </div>
  `).join('');
}

function selectIdea(idx) {
  selectedIdeaIdx = idx;
  document.querySelectorAll('.idea-card').forEach(c => c.classList.remove('selected'));
  document.getElementById('idea-' + idx).classList.add('selected');

  // Auto-fill experiment tab
  fetch('/api/ideation', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic: '' }) }).catch(() => {});

  // Use current_ideas from last generation
  const el = document.getElementById('expIdeaJson');
  const cards = document.querySelectorAll('.idea-card');
  // Re-fetch from DOM is tricky, so store globally
  if (window._lastIdeas && window._lastIdeas[idx]) {
    el.value = JSON.stringify(window._lastIdeas[idx], null, 2);
  }

  // Mark step 2 done, go to step 3
  document.querySelector('.step[data-step="2"]').classList.add('done');
  showStep(3);
}

// Patch generateIdeas to store
const _origRenderIdeas = renderIdeas;
renderIdeas = function(ideas) {
  window._lastIdeas = ideas;
  _origRenderIdeas(ideas);
};

// ── Experiments ──
async function startExperiment() {
  const btn = document.getElementById('expBtn');
  btn.disabled = true; btn.textContent = 'Running...';
  document.getElementById('statusDot').classList.add('running');
  document.getElementById('statusText').textContent = 'Experiment Running';

  const ideaJson = document.getElementById('expIdeaJson').value;
  const citeRounds = parseInt(document.getElementById('citeRounds').value);
  const skipWriteup = document.getElementById('skipWriteup').checked;
  const skipReview = document.getElementById('skipReview').checked;

  try {
    await fetch('/api/experiments/start', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ideas_json: ideaJson, num_cite_rounds: citeRounds, skip_writeup: skipWriteup, skip_review: skipReview })
    });
    connectWS();
  } catch (e) { alert('Error: ' + e); btn.disabled = false; btn.textContent = 'Start Experiment'; }
}

// ── WebSocket Logs ──
function connectWS() {
  if (ws && ws.readyState === WebSocket.OPEN) return;
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws/logs`);
  ws.onmessage = (e) => {
    const d = JSON.parse(e.data);
    if (d.logs.length) appendLogs(d.logs);
    if (!d.running && document.getElementById('expBtn').disabled) {
      document.getElementById('expBtn').disabled = false;
      document.getElementById('expBtn').textContent = 'Start Experiment';
      document.getElementById('statusDot').classList.remove('running');
      document.getElementById('statusText').textContent = 'Ready';

      // Auto-switch to results
      if (d.logs.some(l => l.includes('[DONE]'))) {
        document.querySelector('.step[data-step="3"]').classList.add('done');
        refreshExpList();
        showStep(4);
      }
    }
  };
  ws.onclose = () => { setTimeout(connectWS, 3000); };
}

function appendLogs(logs) {
  const el = document.getElementById('logContainer');
  logs.forEach(log => {
    const cls = log.includes('[ERROR]') ? 'log-error' : log.includes('[WARN]') ? 'log-warn' :
      log.includes('[DONE]') ? 'log-done' : 'log-info';
    el.innerHTML += `<div class="${cls}">${escHtml(log)}</div>`;
  });
  el.scrollTop = el.scrollHeight;
}

function escHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// ── Results ──
async function refreshExpList() {
  try {
    const r = await fetch('/api/experiments/list');
    const d = await r.json();
    const sel = document.getElementById('expSelect');
    sel.innerHTML = '<option value="">Select experiment...</option>' +
      d.experiments.map(e => `<option value="${e}">${e}</option>`).join('');
    if (d.experiments.length) { sel.value = d.experiments[0]; loadResults(d.experiments[0]); }
  } catch (e) {}
}

async function loadResults(name) {
  if (!name) return;
  try {
    const r = await fetch(`/api/results/${name}`);
    const d = await r.json();
    if (d.error) return;

    document.getElementById('resultsContainer').style.display = '';

    // Figures
    const fg = document.getElementById('figuresGrid');
    fg.innerHTML = d.figures.map(f => `<img src="${f}" onclick="window.open('${f}','_blank')">`).join('');

    // Summary
    document.getElementById('summaryContent').textContent = JSON.stringify(d.summary, null, 2);

    // Review
    if (d.review) {
      document.getElementById('reviewCard').style.display = '';
      document.getElementById('reviewContent').textContent = d.review;
    }

    // PDF
    if (d.pdf) {
      document.getElementById('pdfCard').style.display = '';
      document.getElementById('pdfLink').href = d.pdf;
    }
  } catch (e) {}
}

// ── Init ──
window.addEventListener('load', async () => {
  try {
    const r = await fetch('/api/config');
    const d = await r.json();
    if (d.fireworks_key_set) document.getElementById('configStatus').innerHTML = '<span class="status-msg ok">Fireworks API key detected</span>';
  } catch (e) {}
});
