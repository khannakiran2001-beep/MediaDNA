// MediaDNA — single-page frontend
const TOKEN_KEY = 'mediadna_token';
let currentUser = null;
const getToken = () => localStorage.getItem(TOKEN_KEY) || '';
const setToken = (t) => t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY);

async function api(p, opts = {}) {
  const headers = Object.assign({}, opts.headers || {});
  const tok = getToken();
  if (tok) headers['Authorization'] = 'Bearer ' + tok;
  const r = await fetch(`/api${p}`, Object.assign({}, opts, { headers }));
  if (r.status === 401) { setToken(''); currentUser = null; renderAuth(); throw new Error('unauthorized'); }
  if (!r.ok) throw r;
  return r.status === 204 ? null : r.json();
}
const el = (h) => { const t = document.createElement('template'); t.innerHTML = h.trim(); return t.content.firstChild; };
const fmtBytes = (b) => { if (!b) return '0 B'; const u = ['B','KB','MB','GB']; const i = Math.floor(Math.log(b)/Math.log(1024)); return (b/Math.pow(1024,i)).toFixed(1)+' '+u[i]; };
const thumb = (a) => a.thumbnail_key ? `/api/assets/${a.id}/thumbnail` : null;
const icon = { image:'🖼️', video:'🎬', audio:'🎵', document:'📄' };

const state = { view: 'dashboard', assets: [], stats: null };

const NAV = [
  ['dashboard','Dashboard','▚'], ['generate','Generate','✦'], ['assets','Assets','▦'], ['search','Search','⌕'],
  ['graph','Lineage Graph','⋔'], ['collections','Collections','☰'], ['activity','Activity','◷'],
];

function shell() {
  const nav = NAV.slice();
  if (currentUser && currentUser.role === 'admin') nav.push(['admin','Admin','⚑']);
  const initial = (currentUser?.name || currentUser?.email || '?').trim()[0]?.toUpperCase() || '?';
  return `
  <aside class="w-60 shrink-0 border-r border-white/5 p-4 hidden md:flex flex-col gap-1 sticky top-0 h-screen">
    <div class="flex items-center gap-2 px-2 py-3 mb-2">
      <div class="w-8 h-8 rounded-lg" style="background:linear-gradient(135deg,#7c5cff,#22d3ee)"></div>
      <div><div class="font-bold text-lg leading-none">MediaDNA</div><div class="text-[10px] text-slate-500 mt-0.5">GitHub for AI Assets</div></div>
    </div>
    ${nav.map(([k,l,i]) => `<button data-nav="${k}" class="nav-btn text-left px-3 py-2 rounded-lg text-sm flex items-center gap-3 hover:bg-white/5 ${state.view===k?'bg-white/10 text-white font-medium':''}"><span class="text-slate-500">${i}</span>${l}</button>`).join('')}
    <div class="mt-auto text-xs text-slate-600 px-2">
      <button onclick="openUpload()" class="w-full mb-3 px-3 py-2 rounded-lg font-medium text-white" style="background:linear-gradient(135deg,#7c5cff,#6d4bff)">+ Upload / Generate</button>
      <div id="envBadges" class="mb-3"></div>
      <div class="flex items-center gap-2 pt-3 border-t border-white/10">
        <div class="w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-bold" style="background:linear-gradient(135deg,#7c5cff,#6d4bff)">${initial}</div>
        <div class="min-w-0 flex-1"><div class="truncate text-slate-300">${currentUser?.email||''}</div>
          <div class="text-[10px] ${currentUser?.role==='admin'?'text-accent2':'text-slate-500'}">${currentUser?.role||''}</div></div>
        <button onclick="logout()" title="Sign out" class="text-slate-500 hover:text-white">⎋</button>
      </div>
    </div>
  </aside>
  <main class="flex-1 min-w-0">
    <header class="flex items-center gap-3 px-6 py-4 border-b border-white/5 sticky top-0 glass z-20">
      <div class="md:hidden font-bold">MediaDNA</div>
      <button onclick="openPalette()" class="flex-1 max-w-md text-left px-4 py-2 rounded-lg bg-white/5 text-slate-400 text-sm flex items-center justify-between">
        <span>⌕ Search assets…</span><kbd>⌘K</kbd></button>
      <div class="flex-1"></div>
      <button onclick="openUpload()" class="px-4 py-2 rounded-lg text-sm font-medium text-white" style="background:linear-gradient(135deg,#7c5cff,#6d4bff)">+ New</button>
    </header>
    <div id="content" class="p-6 fade-in"></div>
  </main>`;
}

async function render() {
  document.getElementById('app').innerHTML = shell();
  document.querySelectorAll('[data-nav]').forEach(b => b.onclick = () => nav(b.dataset.nav));
  renderEnvBadges();
  const c = document.getElementById('content');
  c.innerHTML = '<div class="text-slate-500">Loading…</div>';
  try {
    if (state.view === 'dashboard') await viewDashboard(c);
    else if (state.view === 'generate') await viewGenerate(c);
    else if (state.view === 'assets') await viewAssets(c);
    else if (state.view === 'search') await viewSearch(c);
    else if (state.view === 'graph') await viewGraph(c);
    else if (state.view === 'collections') await viewCollections(c);
    else if (state.view === 'activity') await viewActivity(c);
    else if (state.view === 'admin') await viewAdmin(c);
  } catch (e) { c.innerHTML = `<div class="text-red-400">Error: ${e}</div>`; }
}
function nav(v) { state.view = v; render(); }

async function renderEnvBadges() {
  const s = await api('/stats').catch(()=>null); if (!s) return;
  const b = document.getElementById('envBadges'); if (!b) return;
  const badge = (on, label, extra) => `<div class="flex items-center gap-2 py-1"><span class="w-2 h-2 rounded-full ${on?'bg-emerald-400':'bg-slate-600'}"></span>${label} <span class="text-slate-600">${extra||(on?'live':'fallback')}</span></div>`;
  b.innerHTML =
    badge(true,'Genblaze SDK', 'v'+(s.genblaze_version||'?')) +
    badge(s.storage_backend==='b2','B2 storage', s.storage_backend) +
    badge(s.huggingface_enabled,'HuggingFace') ;
}

// --- Dashboard --------------------------------------------------------------
async function viewDashboard(c) {
  const [stats, assets, acts] = await Promise.all([api('/stats'), api('/assets?limit=8'), api('/activity')]);
  state.stats = stats;
  const stat = (n,l,sub) => `<div class="glass rounded-xl p-5"><div class="text-3xl font-bold grad-text">${n}</div><div class="text-sm text-slate-400 mt-1">${l}</div><div class="text-xs text-slate-600">${sub||''}</div></div>`;
  const providers = Object.entries(stats.by_provider||{}).map(([k,v])=>`<span class="text-xs px-2 py-1 rounded bg-white/5 mr-2">${k}: ${v}</span>`).join('');
  c.innerHTML = `
    <h1 class="text-2xl font-bold mb-1">Dashboard</h1>
    <p class="text-slate-500 mb-6 text-sm">Every AI asset with permanent identity, lineage & searchable history.</p>
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      ${stat(stats.total_assets,'Total Assets')}
      ${stat(fmtBytes(stats.total_storage_bytes),'Storage Used', stats.b2_enabled?'Backblaze B2':'Local (B2 fallback)')}
      ${stat(Object.keys(stats.by_media_type||{}).length,'Media Types')}
      ${stat(Object.keys(stats.by_provider||{}).length,'Providers')}
    </div>
    <div class="mb-4">${providers}</div>
    <div class="grid lg:grid-cols-3 gap-6">
      <div class="lg:col-span-2">
        <h2 class="font-semibold mb-3 flex items-center justify-between">Recent Assets <button onclick="nav('assets')" class="text-xs text-accent">view all →</button></h2>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">${assets.map(assetCard).join('') || emptyState()}</div>
      </div>
      <div>
        <h2 class="font-semibold mb-3">Activity Feed</h2>
        <div class="glass rounded-xl p-4 space-y-3 text-sm">
          ${acts.slice(0,10).map(a=>`<div class="flex gap-2"><span class="text-accent2">●</span><div><span class="font-medium">${a.action}</span> <span class="text-slate-500 text-xs">${new Date(a.at).toLocaleTimeString()}</span></div></div>`).join('') || '<div class="text-slate-500">No activity yet.</div>'}
        </div>
      </div>
    </div>`;
  bindCards(c);
}

function emptyState() {
  return `<div class="col-span-full glass rounded-xl p-10 text-center text-slate-500">
    <div class="text-4xl mb-3">🧬</div><div class="mb-3">No assets yet.</div>
    <button onclick="openUpload()" class="px-4 py-2 rounded-lg text-white text-sm" style="background:linear-gradient(135deg,#7c5cff,#6d4bff)">Upload your first asset</button>
    <div class="text-xs mt-3">or run <span class="font-mono">python scripts/seed.py</span> for demo data</div></div>`;
}

// --- Generate (Genblaze text-to-image) --------------------------------------
const GEN_SAMPLES = [
  'cyberpunk city street at night, neon signs, rain, cinematic',
  'aerial drone shot over a green valley at sunrise',
  'minimalist product photo of a sneaker on a gradient background',
  'vaporwave poster with pink and cyan retro grid',
  'photorealistic portrait, soft studio lighting',
];
async function viewGenerate(c) {
  const s = await api('/stats').catch(()=>({generation_backend:'procedural'}));
  const backendLabels = {
    huggingface: 'Hugging Face (live text-to-image)',
    pollinations: 'Pollinations · FLUX (real images, no API key)',
    procedural: 'procedural fallback (abstract art only)',
  };
  const backend = backendLabels[s.generation_backend] || s.generation_backend;
  c.innerHTML = `<h1 class="text-2xl font-bold mb-1">Generate <span class="grad-text">with Genblaze</span></h1>
    <p class="text-slate-500 text-sm mb-1">Runs a real <span class="text-accent2">Genblaze Pipeline</span> (SDK v${s.genblaze_version||'?'}) → verified provenance manifest → stored via B2 backend (<span class="text-accent2">${s.storage_backend}</span>) → auto-analysed for the DNA record.</p>
    <p class="text-xs text-slate-600 mb-5">Image backend: <span class="text-accent2">${backend}</span></p>
    <div class="grid lg:grid-cols-2 gap-6">
      <div class="glass rounded-xl p-5">
        <textarea id="genPrompt" rows="3" placeholder="Describe the asset to generate…" class="w-full px-3 py-2 rounded-lg bg-white/5 outline-none border border-white/10 focus:border-accent text-sm">${GEN_SAMPLES[0]}</textarea>
        <div class="grid grid-cols-2 gap-3 mt-3">
          <select id="genModel" class="px-3 py-2 rounded-lg bg-white/5 text-sm outline-none">
            <option value="black-forest-labs/FLUX.1-schnell">FLUX.1-schnell</option>
            <option value="stabilityai/stable-diffusion-xl-base-1.0">SDXL 1.0</option>
            <option value="stabilityai/sdxl-turbo">SDXL Turbo</option>
          </select>
          <input id="genProject" placeholder="Project (optional)" class="px-3 py-2 rounded-lg bg-white/5 text-sm outline-none">
        </div>
        <input id="genTags" placeholder="tags, comma, separated" class="w-full mt-3 px-3 py-2 rounded-lg bg-white/5 text-sm outline-none">
        <button onclick="runGenerate()" id="genBtn" class="w-full mt-4 py-2.5 rounded-lg text-white font-medium" style="background:linear-gradient(135deg,#7c5cff,#6d4bff)">✦ Generate Asset</button>
        <div class="flex flex-wrap gap-2 mt-4 text-xs">
          ${GEN_SAMPLES.map(p=>`<button onclick="document.getElementById('genPrompt').value=this.textContent" class="px-3 py-1 rounded-full bg-white/5 hover:bg-white/10 text-left">${p.slice(0,34)}…</button>`).join('')}
        </div>
        <div id="genStatus" class="text-xs text-slate-500 mt-3"></div>
      </div>
      <div>
        <div class="text-sm text-slate-400 mb-2">This session</div>
        <div id="genResults" class="grid grid-cols-2 gap-3"></div>
      </div>
    </div>`;
}
async function runGenerate() {
  const prompt = document.getElementById('genPrompt').value.trim();
  if (!prompt) return;
  const btn = document.getElementById('genBtn'), st = document.getElementById('genStatus');
  const body = {
    prompt,
    model: document.getElementById('genModel').value,
    project: document.getElementById('genProject').value,
    tags: document.getElementById('genTags').value.split(',').map(t=>t.trim()).filter(Boolean),
  };
  btn.disabled = true; btn.style.opacity = .6;
  const steps = ['🎨 generating image…','🔎 captioning + object detection…','🎨 colours + quality…','🧬 embedding + provenance…','💾 storing…'];
  let i = 0; st.textContent = steps[0];
  const timer = setInterval(()=>{ i=(i+1)%steps.length; st.textContent = steps[i]; }, 700);
  try {
    const a = await api('/generate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    clearInterval(timer); st.textContent = `✅ Generated "${a.name}" — style ${a.visual_style}, quality ${a.quality_score}`;
    const r = document.getElementById('genResults');
    r.insertAdjacentHTML('afterbegin', assetCard(a));
    bindCards(r);
    renderEnvBadges();
  } catch (e) { clearInterval(timer); st.textContent = '❌ Generation failed.'; }
  btn.disabled = false; btn.style.opacity = 1;
}

// --- Assets grid ------------------------------------------------------------
async function viewAssets(c) {
  const assets = await api('/assets?limit=200');
  state.assets = assets;
  c.innerHTML = `<h1 class="text-2xl font-bold mb-4">Assets <span class="text-slate-500 text-base">${assets.length}</span></h1>
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">${assets.map(assetCard).join('') || emptyState()}</div>`;
  bindCards(c);
}

function assetCard(a) {
  const t = thumb(a);
  const media = t ? `<img src="${t}" class="w-full h-32 object-cover" loading="lazy">`
    : `<div class="w-full h-32 flex items-center justify-center text-4xl" style="background:${(a.dominant_colors&&a.dominant_colors[0])||'#1a1a24'}">${icon[a.media_type]||'📦'}</div>`;
  const swatches = (a.dominant_colors||[]).slice(0,4).map(c=>`<span class="w-3 h-3 rounded-full inline-block" style="background:${c}"></span>`).join('');
  return `<div class="card glass rounded-xl overflow-hidden cursor-pointer" data-asset="${a.id}">
    ${media}
    <div class="p-3">
      <div class="text-sm font-medium truncate">${a.name}</div>
      <div class="text-xs text-slate-500 truncate mb-2">${a.caption||''}</div>
      <div class="flex items-center justify-between">
        <span class="text-[10px] px-1.5 py-0.5 rounded bg-accent/20 text-accent">${a.provider||a.model}</span>
        <span class="flex gap-1">${swatches}</span>
      </div>
      <div class="flex items-center gap-2 mt-2 text-[10px] text-slate-500">
        <span>v${a.version}</span>${a.parent_id?'<span class="text-accent2">↳ fork</span>':''}
        <span class="ml-auto ${a.approval_status==='approved'?'text-emerald-400':''}">${a.approval_status}</span>
      </div>
    </div></div>`;
}
function bindCards(c) { c.querySelectorAll('[data-asset]').forEach(x => x.onclick = () => openAsset(x.dataset.asset)); }

// --- Search -----------------------------------------------------------------
async function viewSearch(c) {
  c.innerHTML = `<h1 class="text-2xl font-bold mb-2">Semantic Search</h1>
    <p class="text-slate-500 text-sm mb-4">Natural language + embeddings + metadata. Try: "cyberpunk", "generated with FLUX", "video with drones".</p>
    <div class="flex gap-2 mb-3">
      <input id="q" placeholder="Ask anything…" class="flex-1 px-4 py-3 rounded-lg bg-white/5 outline-none border border-white/10 focus:border-accent">
      <button onclick="runSearch()" class="px-5 rounded-lg text-white font-medium" style="background:linear-gradient(135deg,#7c5cff,#6d4bff)">Search</button>
    </div>
    <div class="flex flex-wrap gap-2 mb-5 text-xs">
      ${['cyberpunk','photorealistic','FLUX','drone','product','summer'].map(x=>`<button onclick="document.getElementById('q').value='${x}';runSearch()" class="px-3 py-1 rounded-full bg-white/5 hover:bg-white/10">${x}</button>`).join('')}
    </div>
    <div id="results" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4"></div>`;
  document.getElementById('q').addEventListener('keydown', e => { if (e.key==='Enter') runSearch(); });
  runSearch();
}
async function runSearch() {
  const q = (document.getElementById('q')?.value)||'';
  const hits = await api('/search', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({query:q, limit:30})});
  const r = document.getElementById('results');
  r.innerHTML = hits.map(h => assetCard(h).replace('</div></div>', `<div class="text-[10px] text-accent2 mt-1">match ${(h.score*100).toFixed(0)}%</div></div></div>`)).join('') || '<div class="text-slate-500 col-span-full">No matches.</div>';
  bindCards(r);
}

// --- Graph ------------------------------------------------------------------
async function viewGraph(c) {
  const g = await api('/graph');
  c.innerHTML = `<h1 class="text-2xl font-bold mb-2">Lineage Graph</h1>
    <p class="text-slate-500 text-sm mb-4">${g.nodes.length} nodes · ${g.edges.length} relationships. Click a node to open its DNA.</p>
    <div id="cy" class="glass rounded-xl" style="height:70vh"></div>`;
  if (!g.nodes.length) { document.getElementById('cy').innerHTML = '<div class="p-10 text-center text-slate-500">No assets to graph yet.</div>'; return; }
  const colors = { image:'#7c5cff', video:'#22d3ee', audio:'#34d399', document:'#fbbf24' };
  const cy = cytoscape({
    container: document.getElementById('cy'),
    elements: [
      ...g.nodes.map(n => ({ data: { id:n.id, label:n.label, type:n.type } })),
      ...g.edges.map(e => ({ data: { source:e.source, target:e.target, kind:e.kind } })),
    ],
    style: [
      { selector:'node', style:{ 'background-color': n=>colors[n.data('type')]||'#888', 'label':'data(label)', 'color':'#cbd5e1', 'font-size':'9px', 'width':22, 'height':22, 'text-valign':'bottom', 'text-margin-y':4 } },
      { selector:'edge', style:{ 'width':1.5, 'line-color':'#3a3a55', 'target-arrow-color':'#3a3a55', 'target-arrow-shape':'triangle', 'curve-style':'bezier', 'label':'data(kind)', 'font-size':'7px', 'color':'#64748b', 'text-rotation':'autorotate' } },
    ],
    layout: { name:'cose', animate:true, nodeRepulsion: 8000, idealEdgeLength: 90 },
  });
  cy.on('tap','node', evt => openAsset(evt.target.id()));
}

// --- Collections ------------------------------------------------------------
async function viewCollections(c) {
  const cols = await api('/collections');
  c.innerHTML = `<div class="flex items-center justify-between mb-4"><h1 class="text-2xl font-bold">Collections</h1>
    <button onclick="createCollection()" class="px-4 py-2 rounded-lg bg-white/10 text-sm">+ New Collection</button></div>
    <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
    ${cols.map(col=>`<div class="glass rounded-xl p-5"><div class="flex items-center gap-2 mb-1"><span class="text-xs px-2 py-0.5 rounded bg-accent/20 text-accent">${col.kind}</span></div>
      <div class="font-semibold text-lg">${col.name}</div><div class="text-sm text-slate-500">${col.description||''}</div>
      <div class="text-xs text-slate-600 mt-3">${col.asset_ids.length} assets</div></div>`).join('') || '<div class="text-slate-500">No collections yet.</div>'}
    </div>`;
}
async function createCollection() {
  const name = prompt('Collection name'); if (!name) return;
  await api('/collections', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name, kind:'collection'})});
  render();
}

// --- Activity ---------------------------------------------------------------
async function viewActivity(c) {
  const acts = await api('/activity');
  c.innerHTML = `<h1 class="text-2xl font-bold mb-4">Activity</h1>
    <div class="glass rounded-xl divide-y divide-white/5">
    ${acts.map(a=>`<div class="p-4 flex items-center gap-3"><span class="text-accent2">●</span><span class="font-medium">${a.action}</span>
      <span class="text-slate-500 text-sm truncate flex-1">${JSON.stringify(a.detail)}</span>
      <span class="text-xs text-slate-600">${new Date(a.at).toLocaleString()}</span></div>`).join('') || '<div class="p-6 text-slate-500">No activity.</div>'}
    </div>`;
}

// --- Asset detail modal -----------------------------------------------------
async function openAsset(id) {
  const [a, versions, related, comments] = await Promise.all([
    api(`/assets/${id}`), api(`/assets/${id}/versions`), api(`/assets/${id}/related`), api(`/assets/${id}/comments`)]);
  const m = document.getElementById('modal');
  const t = thumb(a);
  const preview = t ? `<img src="${t}" class="w-full rounded-lg">` : `<div class="w-full h-64 rounded-lg flex items-center justify-center text-6xl bg-panel2">${icon[a.media_type]}</div>`;
  const dna = (k,v) => v||v===0 ? `<div class="flex justify-between gap-4 py-1.5 border-b border-white/5 text-sm"><span class="text-slate-500">${k}</span><span class="text-right font-mono text-xs">${v}</span></div>` : '';
  const chips = arr => (arr||[]).map(x=>`<span class="text-xs px-2 py-0.5 rounded bg-white/5 mr-1 mb-1 inline-block">${typeof x==='object'?x.label:x}</span>`).join('');
  m.innerHTML = `
    <div class="max-w-5xl mx-auto glass rounded-2xl overflow-hidden fade-in">
      <div class="flex items-center justify-between p-4 border-b border-white/10">
        <div class="font-semibold truncate">${icon[a.media_type]} ${a.name}</div>
        <button onclick="closeModal()" class="text-slate-400 hover:text-white text-xl px-2">✕</button>
      </div>
      <div class="grid md:grid-cols-2 gap-6 p-6 max-h-[80vh] overflow-y-auto">
        <div>
          ${preview}
          <div class="flex gap-2 mt-3">
            <a href="/api/assets/${a.id}/file" download class="flex-1 text-center px-3 py-2 rounded-lg bg-white/10 text-sm">⤓ Download</a>
            <button onclick="forkAsset('${a.id}')" class="flex-1 px-3 py-2 rounded-lg text-white text-sm" style="background:linear-gradient(135deg,#7c5cff,#6d4bff)">⑂ Fork</button>
            <button onclick="deleteAsset('${a.id}')" class="px-3 py-2 rounded-lg bg-red-500/20 text-red-300 text-sm">Delete</button>
          </div>
          <div class="mt-4"><div class="text-xs text-slate-500 mb-1">Dominant colors</div>
            <div class="flex gap-1">${(a.dominant_colors||[]).map(c=>`<span class="w-8 h-8 rounded" style="background:${c}" title="${c}"></span>`).join('')}</div></div>
        </div>
        <div>
          <div class="flex gap-2 mb-3 text-xs">
            <span class="px-2 py-1 rounded bg-accent/20 text-accent">${a.provider}</span>
            <span class="px-2 py-1 rounded bg-white/5">${a.model||'—'}</span>
            <span class="px-2 py-1 rounded bg-white/5">v${a.version}</span>
            <span class="px-2 py-1 rounded ${a.approval_status==='approved'?'bg-emerald-500/20 text-emerald-300':'bg-white/5'}">${a.approval_status}</span>
          </div>
          <div class="mb-4"><div class="text-xs text-slate-500 mb-1">Caption</div><div class="text-sm">${a.caption||'—'}</div></div>
          ${a.prompt?`<div class="mb-4"><div class="text-xs text-slate-500 mb-1">Prompt</div><div class="text-sm font-mono bg-black/30 rounded p-2">${a.prompt}</div></div>`:''}
          <div class="mb-4"><div class="text-xs text-slate-500 mb-1">Detected objects</div>${chips(a.objects_detected)||'<span class="text-xs text-slate-600">none</span>'}</div>
          <div class="mb-4"><div class="text-xs text-slate-500 mb-1">Tags</div>${chips(a.tags)||'<span class="text-xs text-slate-600">none</span>'}</div>
          ${a.provenance && a.provenance.source==='genblaze' ? `<div class="mb-4 rounded-lg border border-accent/30 bg-accent/5 p-3">
            <div class="text-xs text-accent2 mb-1 flex items-center gap-2">⛓️ Genblaze provenance manifest ${a.provenance.verified?'<span class="text-emerald-400">✓ verified</span>':'<span class="text-amber-400">unverified</span>'}</div>
            <div class="text-[11px] font-mono text-slate-400">run ${(a.provenance.genblaze_run_id||'').slice(0,18)}…</div>
            <div class="text-[11px] font-mono text-slate-400">hash ${(a.provenance.canonical_hash||'').slice(0,24)}…</div>
            <div class="text-[11px] text-slate-500 mt-1">schema v${(a.provenance.manifest||{}).schema_version||'?'} · SHA-256 covered</div>
          </div>`:''}
          <details class="mb-2"><summary class="cursor-pointer text-sm text-accent2 mb-2">🧬 Full DNA record</summary>
            ${dna('Asset ID', a.id)}${dna('Checksum', (a.checksum||'').slice(0,24)+'…')}${dna('Media type', a.media_type)}
            ${dna('Dimensions', a.width?`${a.width}×${a.height}`:'')}${dna('Size', fmtBytes(a.size_bytes))}${dna('Visual style', a.visual_style)}
            ${dna('Quality', a.quality_score)}${dna('People', a.people_detected)}${dna('Project', a.project)}${dna('Campaign', a.campaign)}
            ${dna('Storage', a.storage_backend)}${dna('Downloads', a.downloads)}${dna('Root', a.root_id)}${dna('Parent', a.parent_id||'—')}
          </details>
          <div class="mb-4"><div class="text-xs text-slate-500 mb-2">Version history (${versions.length})</div>
            <div class="space-y-1">${versions.map(v=>`<div class="flex items-center gap-2 text-sm ${v.id===a.id?'text-accent':''}"><span class="font-mono text-xs">v${v.version}</span><span class="truncate cursor-pointer hover:underline" onclick="openAsset('${v.id}')">${v.name}</span></div>`).join('')}</div></div>
          <div class="mb-4"><div class="text-xs text-slate-500 mb-2">Related assets (${related.length})</div>
            <div class="flex gap-2 flex-wrap">${related.map(r=>`<div class="w-16 cursor-pointer" onclick="openAsset('${r.id}')">${thumb(r)?`<img src="${thumb(r)}" class="w-16 h-16 object-cover rounded">`:`<div class="w-16 h-16 rounded bg-panel2 flex items-center justify-center">${icon[r.media_type]}</div>`}</div>`).join('')||'<span class="text-xs text-slate-600">none</span>'}</div></div>
          <div><div class="text-xs text-slate-500 mb-2">Comments</div>
            <div id="commentList" class="space-y-2 mb-2">${comments.map(c=>`<div class="text-sm bg-white/5 rounded p-2"><span class="font-medium">${c.author}</span>: ${c.body}</div>`).join('')}</div>
            <div class="flex gap-2"><input id="commentBox" placeholder="Add a comment…" class="flex-1 px-3 py-2 rounded bg-white/5 text-sm outline-none"><button onclick="addComment('${a.id}')" class="px-3 rounded bg-white/10 text-sm">Post</button></div>
          </div>
        </div>
      </div>
    </div>`;
  m.classList.remove('hidden'); m.classList.add('block');
  m.onclick = e => { if (e.target === m) closeModal(); };
}
function closeModal() { const m = document.getElementById('modal'); m.classList.add('hidden'); m.classList.remove('block'); }
async function forkAsset(id) {
  const p = prompt('New prompt for the fork (blank keeps original):');
  await api(`/assets/${id}/fork`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({prompt:p||null, note:'Forked via UI'})});
  closeModal(); render();
}
async function deleteAsset(id) { if (!confirm('Delete this asset?')) return; await api(`/assets/${id}`, {method:'DELETE'}); closeModal(); render(); }
async function addComment(id) {
  const box = document.getElementById('commentBox'); if (!box.value.trim()) return;
  await api(`/assets/${id}/comments`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({author:'you', body:box.value})});
  openAsset(id);
}

// --- Upload modal -----------------------------------------------------------
function openUpload() {
  const m = document.getElementById('uploadModal');
  m.innerHTML = `<div class="glass rounded-2xl p-6 w-[520px] fade-in">
    <div class="flex items-center justify-between mb-4"><div class="font-semibold text-lg">Upload / Generate Asset</div><button onclick="closeUpload()" class="text-slate-400 text-xl">✕</button></div>
    <form id="uploadForm" class="space-y-3">
      <label class="block border-2 border-dashed border-white/15 rounded-xl p-6 text-center cursor-pointer hover:border-accent">
        <input type="file" name="file" required class="hidden" onchange="this.parentNode.querySelector('.fn').textContent=this.files[0]?.name||''">
        <div class="text-3xl mb-2">🧬</div><div class="text-sm text-slate-400">Drop image / video / audio / PDF</div>
        <div class="fn text-xs text-accent2 mt-1"></div>
      </label>
      <input name="prompt" placeholder="Original prompt" class="w-full px-3 py-2 rounded-lg bg-white/5 text-sm outline-none">
      <div class="grid grid-cols-2 gap-3">
        <input name="model" placeholder="Model (e.g. FLUX.1)" class="px-3 py-2 rounded-lg bg-white/5 text-sm outline-none">
        <input name="provider" placeholder="Provider" class="px-3 py-2 rounded-lg bg-white/5 text-sm outline-none">
        <input name="project" placeholder="Project" class="px-3 py-2 rounded-lg bg-white/5 text-sm outline-none">
        <input name="campaign" placeholder="Campaign" class="px-3 py-2 rounded-lg bg-white/5 text-sm outline-none">
      </div>
      <input name="tags" placeholder="tags, comma, separated" class="w-full px-3 py-2 rounded-lg bg-white/5 text-sm outline-none">
      <button type="submit" class="w-full py-2.5 rounded-lg text-white font-medium" style="background:linear-gradient(135deg,#7c5cff,#6d4bff)">Run Genblaze Pipeline →</button>
      <div id="uploadStatus" class="text-xs text-center text-slate-500"></div>
    </form></div>`;
  m.classList.remove('hidden');
  m.onclick = e => { if (e.target === m) closeUpload(); };
  document.getElementById('uploadForm').onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const st = document.getElementById('uploadStatus');
    st.textContent = '⚙️ Extracting metadata → caption → detection → embedding → storing…';
    try { await fetch('/api/assets', {method:'POST', body:fd}).then(r=>{if(!r.ok)throw r;return r.json();});
      st.textContent = '✅ Done!'; closeUpload(); state.view='assets'; render();
    } catch { st.textContent = '❌ Upload failed.'; }
  };
}
function closeUpload() { const m = document.getElementById('uploadModal'); m.classList.add('hidden'); }

// --- Command palette --------------------------------------------------------
function openPalette() {
  const p = document.getElementById('palette'); p.classList.remove('hidden');
  const inp = document.getElementById('paletteInput'); inp.value=''; inp.focus();
  paletteSearch('');
  inp.oninput = () => paletteSearch(inp.value);
  p.onclick = e => { if (e.target===p) closePalette(); };
}
function closePalette() { document.getElementById('palette').classList.add('hidden'); }
async function paletteSearch(q) {
  const cmds = NAV.map(([k,l]) => ({cmd:true, k, label:'Go to '+l}));
  const res = document.getElementById('paletteResults');
  let hits = [];
  if (q) hits = await api('/search', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({query:q, limit:6})}).catch(()=>[]);
  const cmdRows = cmds.filter(c=>!q||c.label.toLowerCase().includes(q.toLowerCase())).map(c=>`<button class="w-full text-left px-5 py-3 hover:bg-white/5 flex items-center gap-3" onclick="nav('${c.k}');closePalette()"><span class="text-accent">⌘</span>${c.label}</button>`).join('');
  const hitRows = hits.map(h=>`<button class="w-full text-left px-5 py-3 hover:bg-white/5 flex items-center gap-3" onclick="closePalette();openAsset('${h.id}')"><span>${icon[h.media_type]}</span><div><div class="text-sm">${h.name}</div><div class="text-xs text-slate-500">${h.caption||''}</div></div></button>`).join('');
  res.innerHTML = cmdRows + hitRows || '<div class="px-5 py-4 text-slate-500 text-sm">No results.</div>';
}

// --- Keyboard shortcuts -----------------------------------------------------
document.addEventListener('keydown', e => {
  if (!currentUser) return;
  if ((e.metaKey||e.ctrlKey) && e.key.toLowerCase()==='k') { e.preventDefault(); openPalette(); }
  if (e.key==='Escape') { closePalette(); closeModal(); closeUpload(); }
  if ((e.metaKey||e.ctrlKey) && e.key.toLowerCase()==='u') { e.preventDefault(); openUpload(); }
});

// --- Auth screen ------------------------------------------------------------
const authState = { mode: 'login', step: 'email', email: '', devOtp: null };

function renderAuth() {
  currentUser = null;
  const isLogin = authState.mode === 'login';
  document.getElementById('app').innerHTML = `
  <div class="min-h-screen w-full flex items-center justify-center p-6">
    <div class="glass rounded-2xl p-8 w-[420px] fade-in">
      <div class="flex items-center gap-2 mb-6">
        <div class="w-9 h-9 rounded-lg" style="background:linear-gradient(135deg,#7c5cff,#22d3ee)"></div>
        <div><div class="font-bold text-xl leading-none">MediaDNA</div><div class="text-[11px] text-slate-500 mt-0.5">GitHub for AI Assets</div></div>
      </div>
      <div class="flex gap-1 mb-6 bg-white/5 rounded-lg p-1 text-sm">
        <button onclick="setAuthMode('login')" class="flex-1 py-2 rounded-md ${isLogin?'bg-white/10 text-white font-medium':'text-slate-400'}">Sign in</button>
        <button onclick="setAuthMode('register')" class="flex-1 py-2 rounded-md ${!isLogin?'bg-white/10 text-white font-medium':'text-slate-400'}">Register</button>
      </div>
      <div id="authBody"></div>
    </div>
  </div>`;
  renderAuthBody();
}

function setAuthMode(mode) { authState.mode = mode; authState.step = 'email'; authState.devOtp = null; renderAuth(); }

function renderAuthBody() {
  const b = document.getElementById('authBody');
  const isLogin = authState.mode === 'login';
  if (authState.step === 'email') {
    if (isLogin) {
      b.innerHTML = `
        <p class="text-sm text-slate-400 mb-4">Sign in with your password, or request a one-time code.</p>
        <input id="authEmail" type="email" placeholder="you@company.com" class="w-full mb-3 px-3 py-2.5 rounded-lg bg-white/5 outline-none border border-white/10 focus:border-accent text-sm">
        <input id="authPassword" type="password" placeholder="Password" class="w-full mb-3 px-3 py-2.5 rounded-lg bg-white/5 outline-none border border-white/10 focus:border-accent text-sm">
        <button onclick="loginPassword()" id="authBtn" class="w-full py-2.5 rounded-lg text-white font-medium" style="background:linear-gradient(135deg,#7c5cff,#6d4bff)">Sign in</button>
        <button onclick="requestOtp()" class="w-full mt-3 text-xs text-slate-400 hover:text-white">Email me a one-time code instead →</button>
        <div id="authMsg" class="text-xs text-center mt-3 min-h-[16px]"></div>`;
      const em = document.getElementById('authEmail'); em.value = authState.email;
      const pw = document.getElementById('authPassword'); (em.value ? pw : em).focus();
      pw.addEventListener('keydown', e => { if (e.key==='Enter') loginPassword(); });
    } else {
      b.innerHTML = `
        <p class="text-sm text-slate-400 mb-4">Create your account with an email verification code.</p>
        <input id="authName" placeholder="Name" class="w-full mb-3 px-3 py-2.5 rounded-lg bg-white/5 outline-none border border-white/10 focus:border-accent text-sm">
        <input id="authEmail" type="email" placeholder="you@company.com" class="w-full mb-3 px-3 py-2.5 rounded-lg bg-white/5 outline-none border border-white/10 focus:border-accent text-sm">
        <button onclick="requestOtp()" id="authBtn" class="w-full py-2.5 rounded-lg text-white font-medium" style="background:linear-gradient(135deg,#7c5cff,#6d4bff)">Send code →</button>
        <div id="authMsg" class="text-xs text-center mt-3 min-h-[16px]"></div>`;
      const em = document.getElementById('authEmail'); em.value = authState.email; em.focus();
      em.addEventListener('keydown', e => { if (e.key==='Enter') requestOtp(); });
    }
  } else {
    b.innerHTML = `
      <p class="text-sm text-slate-400 mb-1">Enter the 6-digit code sent to</p>
      <p class="text-sm text-accent2 mb-4">${authState.email}</p>
      ${authState.devOtp ? `<div class="mb-3 text-xs rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-300 p-2">Dev mode (no mailer configured): your code is <span class="font-mono font-bold">${authState.devOtp}</span></div>` : ''}
      <input id="authCode" inputmode="numeric" maxlength="6" placeholder="000000" class="w-full mb-3 px-3 py-2.5 rounded-lg bg-white/5 outline-none border border-white/10 focus:border-accent text-center text-2xl font-mono tracking-[0.4em]">
      <button onclick="verifyOtp()" id="authBtn" class="w-full py-2.5 rounded-lg text-white font-medium" style="background:linear-gradient(135deg,#7c5cff,#6d4bff)">Verify & continue →</button>
      <div class="flex justify-between mt-3 text-xs">
        <button onclick="authState.step='email';renderAuthBody()" class="text-slate-500 hover:text-white">← change email</button>
        <button onclick="requestOtp()" class="text-slate-500 hover:text-white">resend code</button>
      </div>
      <div id="authMsg" class="text-xs text-center mt-2 min-h-[16px]"></div>`;
    const cd = document.getElementById('authCode'); cd.focus();
    cd.addEventListener('keydown', e => { if (e.key==='Enter') verifyOtp(); });
  }
}

async function loginPassword() {
  const email = (document.getElementById('authEmail')?.value || '').trim();
  const password = document.getElementById('authPassword')?.value || '';
  const msg = document.getElementById('authMsg');
  if (!email || !password) { msg.className='text-xs text-center mt-3 text-red-400'; msg.textContent='Enter email and password'; return; }
  const btn = document.getElementById('authBtn'); btn.disabled = true; btn.style.opacity = .6;
  try {
    const r = await fetch('/api/auth/login-password', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({email, password})});
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Invalid credentials');
    setToken(data.token); currentUser = data.user; state.view = 'dashboard';
    render();
  } catch (e) {
    msg.className='text-xs text-center mt-3 text-red-400'; msg.textContent = e.message;
    btn.disabled = false; btn.style.opacity = 1;
  }
}

async function requestOtp() {
  const email = (document.getElementById('authEmail')?.value || authState.email).trim();
  const name = document.getElementById('authName')?.value || '';
  const msg = document.getElementById('authMsg');
  if (!email) { msg.className='text-xs text-center mt-3 text-red-400'; msg.textContent='Enter an email'; return; }
  authState.email = email;
  const btn = document.getElementById('authBtn'); btn.disabled = true; btn.style.opacity = .6;
  try {
    const r = await fetch('/api/auth/request-otp', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({email, name, purpose: authState.mode})});
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Failed');
    authState.devOtp = data.dev_otp || null;
    authState.step = 'code';
    renderAuthBody();
  } catch (e) {
    msg.className='text-xs text-center mt-3 text-red-400'; msg.textContent = e.message;
    btn.disabled = false; btn.style.opacity = 1;
  }
}

async function verifyOtp() {
  const code = document.getElementById('authCode').value.trim();
  const msg = document.getElementById('authMsg');
  const btn = document.getElementById('authBtn'); btn.disabled = true; btn.style.opacity = .6;
  try {
    const r = await fetch('/api/auth/verify', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({email: authState.email, code})});
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Invalid code');
    setToken(data.token); currentUser = data.user; state.view = 'dashboard';
    render();
  } catch (e) {
    msg.className='text-xs text-center mt-2 text-red-400'; msg.textContent = e.message;
    btn.disabled = false; btn.style.opacity = 1;
  }
}

async function logout() {
  try { await api('/auth/logout', {method:'POST'}); } catch (e) {}
  setToken(''); currentUser = null; authState.step = 'email'; renderAuth();
}

// --- Admin panel ------------------------------------------------------------
async function viewAdmin(c) {
  const [users, assets] = await Promise.all([api('/admin/users'), api('/assets?limit=200')]);
  const pending = assets.filter(a => a.approval_status === 'pending');
  c.innerHTML = `<h1 class="text-2xl font-bold mb-1">Admin</h1>
    <p class="text-slate-500 text-sm mb-6">Manage users and moderate assets.</p>
    <div class="grid lg:grid-cols-2 gap-6">
      <div>
        <h2 class="font-semibold mb-3">Users <span class="text-slate-500">${users.length}</span></h2>
        <div class="glass rounded-xl divide-y divide-white/5">
          ${users.map(u => `<div class="p-3 flex items-center gap-3 text-sm">
            <div class="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold" style="background:linear-gradient(135deg,#7c5cff,#6d4bff)">${(u.name||u.email)[0].toUpperCase()}</div>
            <div class="min-w-0 flex-1"><div class="truncate">${u.email} ${u.id===currentUser.id?'<span class="text-[10px] text-slate-500">(you)</span>':''}</div>
              <div class="text-[11px] text-slate-500">${u.name||'—'} · ${u.is_active?'active':'<span class="text-red-400">inactive</span>'}</div></div>
            <span class="text-[10px] px-2 py-0.5 rounded ${u.role==='admin'?'bg-accent2/20 text-accent2':'bg-white/5 text-slate-400'}">${u.role}</span>
            ${u.id===currentUser.id ? '' : `<button onclick="setRole('${u.id}','${u.role==='admin'?'user':'admin'}')" class="text-xs px-2 py-1 rounded bg-white/5 hover:bg-white/10">${u.role==='admin'?'demote':'make admin'}</button>`}
          </div>`).join('')}
        </div>
      </div>
      <div>
        <h2 class="font-semibold mb-3">Pending approval <span class="text-slate-500">${pending.length}</span></h2>
        <div class="space-y-2">
          ${pending.map(a => `<div class="glass rounded-xl p-3 flex items-center gap-3">
            ${thumb(a)?`<img src="${thumb(a)}" class="w-12 h-12 rounded object-cover">`:`<div class="w-12 h-12 rounded bg-panel2 flex items-center justify-center">${icon[a.media_type]||'📦'}</div>`}
            <div class="min-w-0 flex-1"><div class="truncate text-sm">${a.name}</div><div class="text-[11px] text-slate-500 truncate">${a.owner_email||'—'}</div></div>
            <button onclick="setApproval('${a.id}','approved')" class="text-xs px-2 py-1 rounded bg-emerald-500/20 text-emerald-300">approve</button>
            <button onclick="setApproval('${a.id}','rejected')" class="text-xs px-2 py-1 rounded bg-red-500/20 text-red-300">reject</button>
          </div>`).join('') || '<div class="glass rounded-xl p-6 text-center text-slate-500 text-sm">Nothing pending 🎉</div>'}
        </div>
      </div>
    </div>`;
}
async function setRole(id, role) { await api(`/admin/users/${id}/role`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({role})}); render(); }
async function setApproval(id, status) { await api(`/admin/assets/${id}/approval?status=${status}`, {method:'POST'}); render(); }

// --- Boot -------------------------------------------------------------------
async function boot() {
  if (getToken()) {
    try { currentUser = await api('/auth/me'); render(); return; } catch (e) {}
  }
  renderAuth();
}
boot();
