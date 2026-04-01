/* SAMPSON v0.8.0 — Frontend controller */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

// Global app state (mirrors Python state)
const APP_STATE = {};
let selectedPreviewIndex = -1;
let isEditing = false;  // Prevent keyboard nav while editing

// Theme toggle handler
function toggleTheme() {
  const isDark = !document.body.classList.contains('light-mode');
  document.body.classList.toggle('light-mode');
  
  // Update button text
  const btn = $('#theme-toggle');
  if (btn) {
    btn.textContent = isDark ? '☀ Light' : '☾ Dark';
  }
  
  // Swap logo
  updateLogo(isDark);
  
  // Persist to Python state
  pywebview.api.set_option('is_dark', !isDark);
}

// Update logo based on theme
function updateLogo(isDark) {
  const logoImg = $('#logo-img');
  if (logoImg) {
    logoImg.src = isDark ? 'sampsontransparentwhite.png' : 'sampsontransparent2.png';
  }
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
async function init() {
  setupCollapsibles();
  setupEventListeners();
  setupPreviewTable();
  
  const initialState = await pywebview.api.get_state();
  Object.assign(APP_STATE, initialState);
  
  renderAll();
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
// Rendering (selective updates)
// ---------------------------------------------------------------------------
function renderAll() {
  // Apply theme
  const isDark = APP_STATE.is_dark !== false;
  if (isDark) {
    document.body.classList.remove('light-mode');
  } else {
    document.body.classList.add('light-mode');
  }
  
  // Update theme toggle button
  const themeBtn = $('#theme-toggle');
  if (themeBtn) {
    themeBtn.textContent = isDark ? '☾ Dark' : '☀ Light';
  }
  
  // Update logo
  updateLogo(isDark);
  
  renderDeckA();
  renderCenterPanel();
  renderStatus();
  renderLog();
  renderDeckB();
}

function renderPatch(patch) {
  const keys = Object.keys(patch);
  
  // Handle theme change
  if (keys.includes('is_dark')) {
    const isDark = patch.is_dark !== false;
    if (isDark) {
      document.body.classList.remove('light-mode');
    } else {
      document.body.classList.add('light-mode');
    }
    const themeBtn = $('#theme-toggle');
    if (themeBtn) {
      themeBtn.textContent = isDark ? '☾ Dark' : '☀ Light';
    }
    updateLogo(isDark);
  }
  
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
  if (keys.includes('status') || keys.includes('progress') || keys.includes('is_running')) {
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

// ---------------------------------------------------------------------------
// Deck A (Source browser)
// ---------------------------------------------------------------------------
function renderDeckA() {
  $('#deck-a-path').value = APP_STATE.source || '';
  $('#breadcrumb-a').textContent = APP_STATE.active_dir || '/';
  $('#file-count').textContent = `${APP_STATE.src_count || 0} audio files`;
  
  // Update header checkbox state
  const folders = (APP_STATE.dir_entries || []).filter(e => e.type === 'folder');
  const checkedCount = folders.filter(e => e.checked).length;
  const headerCb = $('#check-all');
  if (headerCb && folders.length > 0) {
    headerCb.checked = checkedCount === folders.length;
    headerCb.indeterminate = checkedCount > 0 && checkedCount < folders.length;
  } else if (headerCb) {
    headerCb.checked = false;
    headerCb.indeterminate = false;
  }
  
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
    
    const checkbox = tr.querySelector('input[type="checkbox"]');
    if (checkbox) {
      checkbox.addEventListener('change', (e) => {
        pywebview.api.toggle_folder(entry.path, e.target.checked);
      });
    }
    
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

// ---------------------------------------------------------------------------
// Center Panel (Options)
// ---------------------------------------------------------------------------
function renderCenterPanel() {
  $('#opt-move').checked = APP_STATE.move || false;
  $('#opt-dry').checked = APP_STATE.dry !== false;
  $('#opt-rename').checked = APP_STATE.modify_names || false;
  $('#custom-prefix').value = APP_STATE.custom_prefix || '';
  $('#custom-prefix').disabled = !APP_STATE.modify_names;
  
  const structMode = APP_STATE.struct_mode || 'flat';
  $$(`input[name="output"][value="${structMode}"]`).forEach(el => el.checked = true);
  
  $('#target-device').value = APP_STATE.profile || 'Generic';
  
  // Audio conversion
  $('#opt-convert').checked = APP_STATE.convert_enabled || false;
  $('#conv-format').value = APP_STATE.convert_format || 'wav';
  $('#conv-sr').value = APP_STATE.convert_sample_rate || 'keep';
  $('#conv-bd').value = APP_STATE.convert_bit_depth || 'keep';
  $('#conv-ch').value = APP_STATE.convert_channels || 'keep';
  $('#opt-normalize').checked = APP_STATE.convert_normalize || false;
  $('#opt-follow-device').checked = APP_STATE.convert_follow_profile !== false;
  
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

// ---------------------------------------------------------------------------
// Status Bar
// ---------------------------------------------------------------------------
function renderStatus() {
  $('#status-text').textContent = APP_STATE.status || 'Ready';
  $('#progress-bar').style.width = `${APP_STATE.progress || 0}%`;
  
  const dot = $('#status-dot');
  dot.className = 'status-dot';
  if (APP_STATE.is_running) {
    dot.classList.add('active');
  } else if (APP_STATE.progress > 0 && APP_STATE.progress < 100) {
    dot.classList.add('active');
  } else if (APP_STATE.status?.toLowerCase().includes('error')) {
    dot.classList.add('error');
  } else {
    dot.classList.add('idle');
  }
  
  // RUN button state
  const runBtn = $('#btn-run');
  if (runBtn) {
    runBtn.disabled = APP_STATE.is_running;
    runBtn.textContent = APP_STATE.is_running ? 'Running…' : '▶ RUN';
  }
}

// ---------------------------------------------------------------------------
// Log Panel
// ---------------------------------------------------------------------------
function renderLog() {
  const output = $('#log-output');
  const lines = APP_STATE.log_lines || [];
  
  // Only update if changed (simple check)
  const currentHtml = output.innerHTML;
  const newHtml = lines.map(line => {
    const time = new Date(line.time).toLocaleTimeString();
    return `<div class="log-line ${line.type}">[${time}] ${escapeHtml(line.message)}</div>`;
  }).join('');
  
  if (currentHtml !== newHtml) {
    output.innerHTML = newHtml;
    output.scrollTop = output.scrollHeight;
  }
}

// ---------------------------------------------------------------------------
// Deck B (Preview)
// ---------------------------------------------------------------------------
function renderDeckB() {
  $('#deck-b-path').value = APP_STATE.dest || '';
  
  const count = APP_STATE.preview_count || 0;
  $('#preview-label').textContent = count > 0 
    ? `${count} files in preview` 
    : 'Navigate source to see preview';
  
  const tbody = $('#preview-list');
  tbody.innerHTML = '';
  
  const entries = APP_STATE.preview_entries || [];
  
  // Reselect by srcpath after sort/filter
  const playingPath = APP_STATE.playback_file;
  if (playingPath && selectedPreviewIndex >= 0) {
    const newIndex = entries.findIndex(e => e.srcpath === playingPath);
    if (newIndex >= 0) {
      selectedPreviewIndex = newIndex;
    }
  }
  
  entries.forEach((entry, index) => {
    const tr = document.createElement('tr');
    tr.dataset.index = index;
    tr.dataset.srcpath = entry.srcpath;
    
    tr.innerHTML = `
      <td class="col-src">${escapeHtml(entry.src_name)}</td>
      <td class="col-dest">${entry.dest_name ? escapeHtml(entry.dest_name) : '—'}</td>
      <td class="col-bpm editable" data-field="bpm">${entry.bpm || '—'}</td>
      <td class="col-key editable" data-field="key">${entry.key || '—'}</td>
      <td class="col-length">${entry.length || '—'}</td>
    `;
    
    // Row click to select & play
    tr.addEventListener('click', (e) => {
      if (!e.target.classList.contains('editable') && !isEditing) {
        selectPreview(index);
      }
    });
    
    // Double-click BPM/Key to edit
    const bpmCell = tr.querySelector('.col-bpm');
    const keyCell = tr.querySelector('.col-key');
    
    if (bpmCell && bpmCell.textContent !== '—') {
      bpmCell.addEventListener('dblclick', (e) => {
        e.stopPropagation();
        startInlineEdit(tr, entry, 'bpm');
      });
    }
    
    if (keyCell && keyCell.textContent !== '—') {
      keyCell.addEventListener('dblclick', (e) => {
        e.stopPropagation();
        startInlineEdit(tr, entry, 'key');
      });
    }
    
    tbody.appendChild(tr);
  });
  
  highlightPreviewRow();
  updateTransportButtons();
}

function setupPreviewTable() {
  // Column header click handlers for sorting
  const headers = $$('.preview-table th');
  const sortMap = ['src_name', 'dest_name', 'bpm', 'key', 'length'];
  
  headers.forEach((th, index) => {
    const sortKey = sortMap[index];
    if (sortKey && (sortKey === 'bpm' || sortKey === 'key' || sortKey === 'length')) {
      th.style.cursor = 'pointer';
      th.addEventListener('click', () => {
        pywebview.api.sort_preview(sortKey);
      });
    }
  });
}

async function startInlineEdit(row, entry, field) {
  if (isEditing) return;
  isEditing = true;
  
  const cell = row.querySelector(`.col-${field}`);
  const currentValue = entry[field] || '';
  const isBpm = field === 'bpm';
  
  // Replace cell content with input
  cell.innerHTML = `<input type="text" class="inline-edit" value="${currentValue.replace('???', '')}" />`;
  const input = cell.querySelector('input');
  input.focus();
  input.select();
  
  function save() {
    const newValue = input.value.trim();
    if (newValue && newValue !== currentValue) {
      if (isBpm) {
        const bpm = parseFloat(newValue);
        if (!isNaN(bpm) && bpm >= 30 && bpm <= 300) {
          pywebview.api.set_file_bpm(entry.srcpath, bpm);
        }
      } else {
        pywebview.api.set_file_key(entry.srcpath, newValue);
      }
    }
    isEditing = false;
    // Re-render will restore the cell
  }
  
  function cancel() {
    isEditing = false;
    // Re-render to restore
    renderDeckB();
  }
  
  input.addEventListener('blur', save);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      input.blur();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      cancel();
    }
  });
}

function updateTransportButtons() {
  const entries = APP_STATE.preview_entries || [];
  const hasEntries = entries.length > 0;
  
  $('#btn-play').textContent = APP_STATE.is_playing ? '■' : '▶';
  $('#btn-play').disabled = !hasEntries || APP_STATE.is_running;
  $('#btn-stop').disabled = !APP_STATE.is_playing;
  $('#btn-prev').disabled = !hasEntries || selectedPreviewIndex <= 0 || APP_STATE.is_running;
  $('#btn-next').disabled = !hasEntries || selectedPreviewIndex >= entries.length - 1 || APP_STATE.is_running;
}

// ---------------------------------------------------------------------------
// Event handlers
// ---------------------------------------------------------------------------
function setupEventListeners() {
  // Theme toggle
  $('#theme-toggle')?.addEventListener('click', toggleTheme);
  
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
  
  // Options
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
  
  const entry = entries[index];
  await pywebview.api.preview_play(entry.srcpath);
}

function highlightPreviewRow() {
  $$('#preview-list tr').forEach((tr, i) => {
    const isSelected = i === selectedPreviewIndex;
    tr.classList.toggle('selected', isSelected);
    if (isSelected) {
      tr.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
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
  if (isEditing) return;  // Disable while editing
  
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
  console.log(`[${type}] ${message}`);
}

// Start once pywebview is ready
window.addEventListener('pywebviewready', init);
