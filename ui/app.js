/* SAMPSON v0.8.0 — Frontend controller */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

// Global app state (mirrors Python state)
const APP_STATE = {};
let selectedPreviewIndex = -1;
let isPlaying = false;

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
async function init() {
  // Setup collapsibles
  setupCollapsibles();
  
  // Setup event listeners
  setupEventListeners();
  
  // Get initial state from Python
  const initialState = await pywebview.api.get_state();
  Object.assign(APP_STATE, initialState);
  
  // Render initial UI
  renderAll();
  
  // Log startup
  log("SAMPSON v0.8.0 ready", "info");
}

// ---------------------------------------------------------------------------
// State sync from Python
// ---------------------------------------------------------------------------
window._onStateUpdate = function(patch) {
  Object.assign(APP_STATE, patch);
  renderPatch(patch);
};

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function renderAll() {
  renderDeckA();
  renderCenterPanel();
  renderStatus();
  renderLog();
  renderDeckB();
}

function renderPatch(patch) {
  const keys = Object.keys(patch);
  
  if (keys.includes('dir_entries') || keys.includes('active_dir') || keys.includes('src_count')) {
    renderDeckA();
  }
  if (keys.some(k => ['move', 'dry', 'modify_names', 'custom_prefix', 'struct_mode', 
                       'profile', 'convert_enabled', 'convert_format', 'convert_sample_rate',
                       'convert_bit_depth', 'convert_channels', 'convert_normalize',
                       'convert_follow_profile', 'bpm_enabled', 'bpm_append', 'bpm_fresh',
                       'key_enabled', 'key_append', 'key_fresh', 'section_open'].includes(k))) {
    renderCenterPanel();
  }
  if (keys.includes('status') || keys.includes('progress')) {
    renderStatus();
  }
  if (keys.includes('log_lines')) {
    renderLog();
  }
  if (keys.includes('preview_entries') || keys.includes('preview_count') || 
      keys.includes('dest') || keys.includes('is_playing')) {
    renderDeckB();
  }
  if (keys.includes('is_playing')) {
    updateTransportButtons();
  }
}

function renderDeckA() {
  // Path display
  $('#deck-a-path').value = APP_STATE.source || '';
  $('#breadcrumb-a').textContent = APP_STATE.active_dir || '/';
  $('#file-count').textContent = `${APP_STATE.src_count || 0} audio files`;
  
  // File list
  const tbody = $('#file-list-a');
  tbody.innerHTML = '';
  
  const entries = APP_STATE.dir_entries || [];
  
  entries.forEach(entry => {
    const tr = document.createElement('tr');
    tr.dataset.path = entry.path;
    tr.dataset.type = entry.type;
    
    const checkHtml = entry.type === 'folder' 
      ? `<input type="checkbox" ${entry.checked ? 'checked' : ''} />`
      : '';
    
    tr.innerHTML = `
      <td class="col-check">${checkHtml}</td>
      <td class="col-name">${entry.icon} ${escapeHtml(entry.name)}</td>
    `;
    
    // Checkbox change
    const checkbox = tr.querySelector('input[type="checkbox"]');
    if (checkbox) {
      checkbox.addEventListener('change', (e) => {
        pywebview.api.toggle_folder(entry.path, e.target.checked);
      });
    }
    
    // Row click to navigate
    tr.addEventListener('click', (e) => {
      if (e.target.tagName !== 'INPUT') {
        if (entry.type === 'folder' || entry.type === 'up') {
          pywebview.api.navigate(entry.path);
        }
      }
    });
    
    tbody.appendChild(tr);
  });
}

function renderCenterPanel() {
  // Options
  $('#opt-move').checked = APP_STATE.move || false;
  $('#opt-dry').checked = APP_STATE.dry !== false;
  $('#opt-rename').checked = APP_STATE.modify_names || false;
  $('#custom-prefix').value = APP_STATE.custom_prefix || '';
  $('#custom-prefix').disabled = !APP_STATE.modify_names;
  
  // Output structure radio
  const structMode = APP_STATE.struct_mode || 'flat';
  $$(`input[name="output"][value="${structMode}"]`).forEach(el => el.checked = true);
  
  // Target device
  $('#target-device').value = APP_STATE.profile || 'Generic';
  
  // Audio conversion
  $('#opt-convert').checked = APP_STATE.convert_enabled || false;
  $('#conv-format').value = APP_STATE.convert_format || 'wav';
  $('#conv-sr').value = APP_STATE.convert_sample_rate || 'keep';
  $('#conv-bd').value = APP_STATE.convert_bit_depth || 'keep';
  $('#conv-ch').value = APP_STATE.convert_channels || 'keep';
  $('#opt-normalize').checked = APP_STATE.convert_normalize || false;
  $('#opt-follow-device').checked = APP_STATE.convert_follow_profile !== false;
  
  // Disable conversion controls if not enabled
  const convEnabled = APP_STATE.convert_enabled || false;
  ['conv-format', 'conv-sr', 'conv-bd', 'conv-ch', 'opt-normalize', 'opt-follow-device'].forEach(id => {
    $(`#${id}`).disabled = !convEnabled;
  });
  
  // BPM detection
  $('#opt-detect-bpm').checked = APP_STATE.bpm_enabled || false;
  $('#opt-append-bpm').checked = APP_STATE.bpm_append || false;
  $('#opt-fresh-bpm').checked = APP_STATE.bpm_fresh || false;
  $('#opt-append-bpm').disabled = !APP_STATE.bpm_enabled;
  $('#opt-fresh-bpm').disabled = !APP_STATE.bpm_enabled;
  
  // Key detection
  $('#opt-detect-key').checked = APP_STATE.key_enabled || false;
  $('#opt-append-key').checked = APP_STATE.key_append || false;
  $('#opt-fresh-key').checked = APP_STATE.key_fresh || false;
  $('#opt-append-key').disabled = !APP_STATE.key_enabled;
  $('#opt-fresh-key').disabled = !APP_STATE.key_enabled;
  
  // Collapsible sections
  const sections = APP_STATE.section_open || {};
  Object.keys(sections).forEach(key => {
    const sectionId = {
      'struct': 'section-output',
      'device': 'section-device',
      'conversion': 'section-audio',
      'bpm': 'section-bpm',
      'key': 'section-key'
    }[key];
    const el = $(`#${sectionId}`);
    if (el) {
      el.classList.toggle('expanded', sections[key]);
    }
  });
}

function renderStatus() {
  $('#status-text').textContent = APP_STATE.status || 'Ready';
  $('#progress-bar').style.width = `${APP_STATE.progress || 0}%`;
  
  const dot = $('#status-dot');
  dot.className = 'status-dot';
  if (APP_STATE.progress > 0 && APP_STATE.progress < 100) {
    dot.classList.add('active');
  } else if (APP_STATE.status?.toLowerCase().includes('error')) {
    dot.classList.add('error');
  } else {
    dot.classList.add('idle');
  }
}

function renderLog() {
  const output = $('#log-output');
  const lines = APP_STATE.log_lines || [];
  
  output.innerHTML = lines.map(line => {
    const time = new Date(line.time).toLocaleTimeString();
    return `<div class="log-line ${line.type}">[${time}] ${escapeHtml(line.message)}</div>`;
  }).join('');
  
  output.scrollTop = output.scrollHeight;
}

function renderDeckB() {
  // Path
  $('#deck-b-path').value = APP_STATE.dest || '';
  
  // Preview count
  const count = APP_STATE.preview_count || 0;
  $('#preview-label').textContent = count > 0 
    ? `${count} files in preview` 
    : 'Navigate source to see preview';
  
  // Preview table
  const tbody = $('#preview-list');
  tbody.innerHTML = '';
  
  const entries = APP_STATE.preview_entries || [];
  
  entries.forEach((entry, index) => {
    const tr = document.createElement('tr');
    tr.dataset.index = index;
    tr.dataset.srcpath = entry.srcpath;
    
    tr.innerHTML = `
      <td>${escapeHtml(entry.src_name)}</td>
      <td class="will-become">${entry.dest_name ? escapeHtml(entry.dest_name) : '—'}</td>
      <td>${entry.bpm || '—'}</td>
      <td>${entry.key || '—'}</td>
      <td>${entry.length || '—'}</td>
    `;
    
    tr.addEventListener('click', () => selectPreview(index));
    
    tbody.appendChild(tr);
  });
  
  updateTransportButtons();
}

function updateTransportButtons() {
  const entries = APP_STATE.preview_entries || [];
  const hasEntries = entries.length > 0;
  
  $('#btn-play').textContent = APP_STATE.is_playing ? '■' : '▶';
  $('#btn-play').disabled = !hasEntries;
  $('#btn-stop').disabled = !APP_STATE.is_playing;
  $('#btn-prev').disabled = !hasEntries || selectedPreviewIndex <= 0;
  $('#btn-next').disabled = !hasEntries || selectedPreviewIndex >= entries.length - 1;
}

// ---------------------------------------------------------------------------
// Event handlers
// ---------------------------------------------------------------------------
function setupEventListeners() {
  // Browse buttons
  $('#btn-browse-a')?.addEventListener('click', () => pywebview.api.browse_source());
  $('#btn-browse-b')?.addEventListener('click', () => pywebview.api.browse_dest());
  
  // Up button
  $('#btn-up-a')?.addEventListener('click', () => pywebview.api.nav_up());
  
  // Check all / uncheck all
  $('#btn-check-all')?.addEventListener('click', () => pywebview.api.select_all_folders());
  $('#btn-uncheck-all')?.addEventListener('click', () => pywebview.api.deselect_all_folders());
  $('#check-all')?.addEventListener('change', (e) => {
    if (e.target.checked) {
      pywebview.api.select_all_folders();
    } else {
      pywebview.api.deselect_all_folders();
    }
  });
  
  // Options — bind all data-key elements
  $$('[data-key]').forEach(el => {
    const key = el.dataset.key;
    
    if (el.type === 'checkbox') {
      el.addEventListener('change', () => {
        pywebview.api.set_option(key, el.checked);
      });
    } else if (el.type === 'radio') {
      el.addEventListener('change', () => {
        if (el.checked) {
          pywebview.api.set_option(key, el.value);
        }
      });
    } else if (el.tagName === 'SELECT') {
      el.addEventListener('change', () => {
        pywebview.api.set_option(key, el.value);
      });
    } else {
      el.addEventListener('input', () => {
        pywebview.api.set_option(key, el.value);
      });
    }
  });
  
  // Filter
  $('#filter-preview')?.addEventListener('input', (e) => {
    pywebview.api.set_option('preview_filter', e.target.value);
  });
  
  // Transport controls
  $('#btn-play')?.addEventListener('click', () => togglePlay());
  $('#btn-stop')?.addEventListener('click', () => pywebview.api.preview_stop());
  $('#btn-prev')?.addEventListener('click', () => {
    pywebview.api.preview_prev();
    selectedPreviewIndex = Math.max(0, selectedPreviewIndex - 1);
    highlightPreviewRow();
  });
  $('#btn-next')?.addEventListener('click', () => {
    pywebview.api.preview_next();
    selectedPreviewIndex = Math.min((APP_STATE.preview_entries || []).length - 1, selectedPreviewIndex + 1);
    highlightPreviewRow();
  });
  
  // RUN button
  $('#btn-run')?.addEventListener('click', async () => {
    const result = await pywebview.api.run();
    if (!result.success) {
      log(result.error, 'error');
    }
  });
}

function setupCollapsibles() {
  $$('.collapsible-header').forEach(header => {
    header.addEventListener('click', () => {
      const collapsible = header.parentElement;
      collapsible.classList.toggle('expanded');
      
      // Update state
      const sectionMap = {
        'section-output': 'struct',
        'section-device': 'device',
        'section-audio': 'conversion',
        'section-bpm': 'bpm',
        'section-key': 'key'
      };
      const sectionKey = sectionMap[collapsible.id];
      if (sectionKey) {
        const sections = APP_STATE.section_open || {};
        sections[sectionKey] = collapsible.classList.contains('expanded');
        pywebview.api.set_option('section_open', sections);
      }
    });
  });
}

async function selectPreview(index) {
  const entries = APP_STATE.preview_entries || [];
  if (index < 0 || index >= entries.length) return;
  
  selectedPreviewIndex = index;
  highlightPreviewRow();
  
  // Play the file
  const entry = entries[index];
  await pywebview.api.preview_play(entry.srcpath);
}

function highlightPreviewRow() {
  $$('#preview-list tr').forEach((tr, i) => {
    tr.classList.toggle('selected', i === selectedPreviewIndex);
  });
}

async function togglePlay() {
  if (APP_STATE.is_playing) {
    await pywebview.api.preview_stop();
  } else {
    const entries = APP_STATE.preview_entries || [];
    if (selectedPreviewIndex >= 0 && selectedPreviewIndex < entries.length) {
      await pywebview.api.preview_play(entries[selectedPreviewIndex].srcpath);
    } else if (entries.length > 0) {
      selectedPreviewIndex = 0;
      highlightPreviewRow();
      await pywebview.api.preview_play(entries[0].srcpath);
    }
  }
}

// Keyboard navigation
document.addEventListener('keydown', (e) => {
  const entries = APP_STATE.preview_entries || [];
  if (entries.length === 0) return;
  
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    selectedPreviewIndex = Math.min(selectedPreviewIndex + 1, entries.length - 1);
    highlightPreviewRow();
    pywebview.api.preview_next();
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    selectedPreviewIndex = Math.max(selectedPreviewIndex - 1, 0);
    highlightPreviewRow();
    pywebview.api.preview_prev();
  } else if (e.key === ' ') {
    e.preventDefault();
    togglePlay();
  }
});

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function log(message, type = 'info') {
  // Local logging (also goes to Python)
  console.log(`[${type}] ${message}`);
}

// Start once pywebview is ready
window.addEventListener('pywebviewready', init);
