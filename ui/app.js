/* SAMPSON v1.0.0 — Frontend controller */

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
  log("SAMPSON v1.0.0 ready", "info");
  pywebview.api.on_ready();
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
  if (keys.some(k => ['move', 'dry', 'dedup_enabled', 'modify_names', 'custom_prefix', 'struct_mode', 
                       'profile', 'convert_enabled', 'convert_format', 'convert_sample_rate',
                       'convert_bit_depth', 'convert_channels', 'convert_normalize',
                       'convert_follow_profile', 'bpm_enabled', 'bpm_append', 'bpm_fresh',
                       'key_enabled', 'key_append', 'key_fresh', 'section_open', 'sync_mode'].includes(k))) {
    renderCenterPanel();
  }
  if (keys.includes('status') || keys.includes('progress') || keys.includes('is_running') || 
      keys.includes('sync_in_progress')) {
    renderStatus();
  }
  if (keys.includes('log_lines')) {
    renderLog();
  }
  if (keys.includes('preview_entries') || keys.includes('preview_count') || 
      keys.includes('dest') || keys.includes('is_playing') ||
      keys.includes('sync_plan') || keys.includes('sync_show_plan') ||
      keys.includes('sync_plan_ready') || keys.includes('sync_plan_counts') ||
      keys.includes('sync_auto_detected')) {
    renderDeckB();
  }
  if (keys.includes('sync_plan_ready') || keys.includes('sync_in_progress')) {
    renderSyncControls();
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
  
  // Update header checkbox state (counts both folders and files)
  const checkableEntries = (APP_STATE.dir_entries || []).filter(e => e.type === 'folder' || e.type === 'file');
  const checkedCount = checkableEntries.filter(e => e.checked).length;
  const headerCb = $('#check-all');
  if (headerCb && checkableEntries.length > 0) {
    headerCb.checked = checkedCount === checkableEntries.length;
    headerCb.indeterminate = checkedCount > 0 && checkedCount < checkableEntries.length;
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
    
    const checkHtml = (entry.type === 'folder' || entry.type === 'file')
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
  $('#opt-dedup').checked = APP_STATE.dedup_enabled !== false;
  $('#opt-rename').checked = APP_STATE.modify_names || false;
  $('#custom-prefix').value = APP_STATE.custom_prefix || '';
  $('#custom-prefix').disabled = !APP_STATE.modify_names;
  
  const structMode = APP_STATE.struct_mode || 'flat';
  $$(`input[name="output"][value="${structMode}"]`).forEach(el => el.checked = true);
  
  const syncMode = APP_STATE.sync_mode || 'additive';
  $$(`input[name="sync_mode"][value="${syncMode}"]`).forEach(el => el.checked = true);
  
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
      'key': 'section-key',
      'sync': 'section-sync'
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
  
  // Sync auto-detect badge
  const autoBadge = $('#sync-auto-badge');
  if (autoBadge) {
    autoBadge.classList.toggle('hidden', !APP_STATE.sync_auto_detected);
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
// Deck B (Preview / Sync Plan)
// ---------------------------------------------------------------------------
function renderDeckB() {
  $('#deck-b-path').value = APP_STATE.dest || '';
  
  const showSyncPlan = APP_STATE.sync_show_plan || false;
  const syncPlan = APP_STATE.sync_plan || [];
  
  // Toggle between preview and sync plan view
  const filterRow = $('#filter-row');
  const tableHead = $('#preview-table-head');
  const table = $('#preview-table');
  
  if (showSyncPlan) {
    // Show sync plan view
    filterRow.classList.add('hidden');
    table.classList.add('sync-mode');
    
    const counts = APP_STATE.sync_plan_counts || {add: 0, update: 0, delete: 0, skip: 0};
    $('#preview-label').textContent = `Sync plan: ${counts.add} add · ${counts.update} update · ${counts.delete} delete · ${counts.skip} skip`;
    
    // Update table header for sync mode
    tableHead.innerHTML = `
      <tr>
        <th class="col-action">Action</th>
        <th class="col-src">Source</th>
        <th class="col-dest">Destination</th>
      </tr>
    `;
    
    // Render sync plan entries
    const tbody = $('#preview-list');
    tbody.innerHTML = '';
    
    syncPlan.forEach((entry, index) => {
      const tr = document.createElement('tr');
      tr.dataset.index = index;
      
      const actionClass = `sync-action-${entry.action}`;
      const actionLabel = entry.action.toUpperCase();
      const srcName = entry.src_name || '—';
      
      tr.innerHTML = `
        <td class="col-action ${actionClass}">${actionLabel}</td>
        <td class="col-src" title="${escapeHtml(srcName)}">${escapeHtml(srcName)}</td>
        <td class="col-dest" title="${escapeHtml(entry.dest_display)}">${escapeHtml(entry.dest_display)}</td>
      `;
      
      tbody.appendChild(tr);
    });
    
  } else {
    // Show normal preview view
    filterRow.classList.remove('hidden');
    table.classList.remove('sync-mode');
    
    const count = APP_STATE.preview_count || 0;
    $('#preview-label').textContent = count > 0 
      ? `${count} files in preview` 
      : 'Navigate source to see preview';
    
    // Restore original table header
    tableHead.innerHTML = `
      <tr>
        <th class="col-stack"></th>
        <th class="col-src">Original name</th>
        <th class="col-dest">Will become</th>
        <th class="col-bpm">BPM</th>
        <th class="col-key">Note</th>
        <th class="col-length">Length</th>
      </tr>
    `;
    
    // Render preview entries
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
      
      const selection = APP_STATE.audition_selection || [];
      const slotIndex = selection.indexOf(entry.srcpath);
      const stackIndicator = slotIndex >= 0 ? `<span class="stack-indicator" title="Slot ${slotIndex + 1}">♦${slotIndex + 1}</span>` : '';
      
      tr.innerHTML = `
        <td class="col-stack">${stackIndicator}</td>
        <td class="col-src" title="${escapeHtml(entry.src_name)}">${escapeHtml(entry.src_name)}</td>
        <td class="col-dest${entry.name_manual ? ' overridden' : ''}" title="${entry.dest_name ? escapeHtml(entry.dest_name) : ''}">${entry.dest_name ? escapeHtml(entry.dest_name) : '—'}</td>
        <td class="col-bpm editable" data-field="bpm">${entry.bpm || '—'}</td>
        <td class="col-key editable" data-field="key">${entry.key || '—'}</td>
        <td class="col-length">${entry.length || '—'}</td>
      `;
      
      // Row click to select & play (shift+click toggles audition stack)
      tr.addEventListener('click', (e) => {
        if (e.shiftKey) {
          e.preventDefault();
          e.stopPropagation();
          pywebview.api.audition_toggle_selection(entry.srcpath);
          return;
        }
        if (!e.target.classList.contains('editable') && !isEditing) {
          selectPreview(index);
        }
      });
      
      // Double-click BPM/Key/Dest to edit
      const bpmCell = tr.querySelector('.col-bpm');
      const keyCell = tr.querySelector('.col-key');
      const destCell = tr.querySelector('.col-dest');
      
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
      
      if (destCell && destCell.textContent !== '—') {
        destCell.classList.add('editable');
        destCell.addEventListener('dblclick', (e) => {
          e.stopPropagation();
          startInlineEdit(tr, entry, 'dest_name');
        });
      }
      
      tbody.appendChild(tr);
    });
    
    highlightPreviewRow();
    updateTransportButtons();
    updateSlicerButtonState();
  }
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
  
  const isDestName = field === 'dest_name';
  const cell = row.querySelector(isDestName ? '.col-dest' : `.col-${field}`);
  
  // For dest_name: strip [c] indicator and extension — edit stem only
  let currentValue;
  if (isDestName) {
    currentValue = (entry.dest_name || '').replace(/ \[c\]$/, '');
    // Strip extension so user edits just the stem
    const dotIdx = currentValue.lastIndexOf('.');
    if (dotIdx > 0) currentValue = currentValue.slice(0, dotIdx);
  } else {
    currentValue = entry[field] || '';
  }
  const originalValue = currentValue;
  const isBpm = field === 'bpm';
  
  // Replace cell content with input
  cell.innerHTML = `<input type="text" class="inline-edit" value="${currentValue.replace('???', '')}" />`;
  const input = cell.querySelector('input');
  input.focus();
  input.select();
  
  function save() {
    const newValue = input.value.trim();
    if (isDestName) {
      if (newValue !== originalValue) {
        pywebview.api.set_file_name(entry.srcpath, newValue);
      }
      isEditing = false;
    } else if (newValue && newValue !== currentValue) {
      if (isBpm) {
        const bpm = parseFloat(newValue);
        if (!isNaN(bpm) && bpm >= 30 && bpm <= 300) {
          pywebview.api.set_file_bpm(entry.srcpath, bpm);
        }
      } else {
        pywebview.api.set_file_key(entry.srcpath, newValue);
      }
      isEditing = false;
    } else {
      isEditing = false;
    }
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
  
  // Sync buttons
  $('#btn-preview-sync')?.addEventListener('click', async () => {
    const result = await pywebview.api.compute_sync_plan();
    if (!result.success) {
      log(result.error, 'error');
    }
  });
  
  $('#btn-execute-sync')?.addEventListener('click', async () => {
    const result = await pywebview.api.run_sync();
    if (!result.success) {
      log(result.error, 'error');
    }
  });
  
  $('#btn-clear-sync')?.addEventListener('click', async () => {
    const result = await pywebview.api.clear_sync_plan();
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
        'section-key': 'key',
        'section-sync': 'sync'
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

// ---------------------------------------------------------------------------
// Sync Controls
// ---------------------------------------------------------------------------
function renderSyncControls() {
  const planReady = APP_STATE.sync_plan_ready || false;
  const inProgress = APP_STATE.sync_in_progress || false;
  const showPlan = APP_STATE.sync_show_plan || false;
  
  const previewBtn = $('#btn-preview-sync');
  const executeBtn = $('#btn-execute-sync');
  const clearBtn = $('#btn-clear-sync');
  const syncStatus = $('#sync-status');
  
  if (!previewBtn || !executeBtn || !clearBtn) return;
  
  previewBtn.disabled = inProgress;
  executeBtn.disabled = !planReady || inProgress;
  clearBtn.disabled = !showPlan || inProgress;
  
  // Update status text
  if (inProgress) {
    syncStatus.textContent = APP_STATE.status || 'Sync in progress...';
  } else if (planReady) {
    const counts = APP_STATE.sync_plan_counts || {add: 0, update: 0, delete: 0, skip: 0};
    syncStatus.textContent = `Ready: ${counts.add} add · ${counts.update} update · ${counts.delete} delete · ${counts.skip} skip`;
  } else {
    syncStatus.textContent = '';
  }
}

async function selectPreview(index) {
  const entries = APP_STATE.preview_entries || [];
  if (index < 0 || index >= entries.length) return;
  
  selectedPreviewIndex = index;
  highlightPreviewRow();
  updateSlicerButtonState();
  
  const entry = entries[index];
  await pywebview.api.preview_play(entry.srcpath);
}

function updateSlicerButtonState() {
  const slicerBtn = $('#open-slicer');
  if (!slicerBtn) return;
  slicerBtn.disabled = false;
  slicerBtn.title = 'Open sample slicer';
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
  if (Slicer.isOpen) return;  // Slicer handles its own keys
  
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

// ── Help tooltips ─────────────────────────────────────────────────────────────
(function () {
  let tip = null;

  function showTip(el) {
    const text = el.getAttribute('data-tip');
    if (!text) return;
    tip = document.createElement('div');
    tip.className = 'tooltip-popup';
    tip.textContent = text;
    document.body.appendChild(tip);
    positionTip(el);
  }

  function positionTip(el) {
    if (!tip) return;
    const r = el.getBoundingClientRect();
    const tw = tip.offsetWidth;
    const th = tip.offsetHeight;
    // Prefer above; clamp to viewport edges
    let top = r.top - th - 7;
    if (top < 6) top = r.bottom + 7;
    let left = r.left + r.width / 2 - tw / 2;
    if (left < 6) left = 6;
    if (left + tw > window.innerWidth - 6) left = window.innerWidth - tw - 6;
    tip.style.top  = top + 'px';
    tip.style.left = left + 'px';
  }

  function hideTip() {
    if (tip) { tip.remove(); tip = null; }
  }

  document.addEventListener('mouseover', function (e) {
    const el = e.target.closest('.help-icon');
    if (el) { hideTip(); showTip(el); }
  });

  document.addEventListener('mouseout', function (e) {
    const el = e.target.closest('.help-icon');
    if (el) hideTip();
  });
})();

// ============================================================================
// Sample Slicer
// ============================================================================

const Slicer = {
  isOpen: false,
  fileInfo: null,
  waveform: null,
  slices: [],
  // Viewport state for X/Y zoom and pan
  viewStart: 0.0,   // fraction of total duration (0.0–1.0)
  viewEnd: 1.0,     // fraction of total duration (0.0–1.0)
  ampScale: 1.0,    // Y amplitude multiplier (1.0 = fit, 2.0 = doubled)
  isPanning: false,
  panStartX: 0,
  panStartViewStart: 0,
  // Playback state
  playing: false,
  currentTime: 0,
  selectedSliceIndex: -1,
  previewSliceIndex: -1,
  playEnd: null,      // null = play to fileInfo.duration; set to slice end for preview
  _playGen: 0,        // invalidates stale RAF loops when new playback starts
  _inSlicePreview: false,  // true while slice preview is running; blocks is_playing hook
  draggingMarker: null,
  _dragMoved: false,  // true once a boundary drag actually moved; suppresses click-seek
  _history: [],       // undo stack of slice-array snapshots (most recent last)

  // Open slicer with a file
  async open(filepath) {
    // Try Deck B selection if no explicit path
    if (!filepath) {
      const entries = APP_STATE.preview_entries || [];
      if (selectedPreviewIndex >= 0 && selectedPreviewIndex < entries.length) {
        filepath = entries[selectedPreviewIndex].srcpath;
      }
    }

    // Reset viewport
    this.viewStart = 0.0; this.viewEnd = 1.0; this.ampScale = 1.0;
    this.fileInfo = null;
    this.selectedSliceIndex = -1;
    this._history = [];
    this.updateUndoButton();
    this.isOpen = true;
    this.render();  // Show modal in empty state first

    if (filepath) {
      const result = await pywebview.api.slicer_open(filepath);
      if (result.success) {
        this.fileInfo = result.file_info;
        // Reset the export prefix to this file's stem. Without this, opening a
        // second file kept the first file's name as the prefix.
        const prefixInput = $('#slicer-prefix');
        if (prefixInput) prefixInput.value = this.fileInfo.name.replace(/\.[^.]+$/, '');
        this.render();
      } else {
        log(result.error || 'Failed to open file', 'error');
      }
    }
  },
  
  close() {
    pywebview.api.slicer_close();
    this.isOpen = false;
    this.playing = false;
    this.waveform = null;
    this.slices = [];
    this.selectedSliceIndex = -1;
    this.render();
  },
  
  render() {
    const modal = $('#slicer-modal');
    if (!modal) return;
    modal.classList.toggle('hidden', !this.isOpen);
    if (!this.isOpen) return;

    const hasFile = !!this.fileInfo;
    const loadBar = $('#slicer-load-bar');
    const loadPath = $('#slicer-load-path');
    const wfContainer = $('.slicer-waveform-container');
    const transport = $('.slicer-transport');
    const controls = $('.slicer-controls');

    // Load bar always visible; path input shows current file or placeholder
    if (loadBar) loadBar.classList.remove('hidden');
    if (loadPath) loadPath.value = hasFile ? this.fileInfo.path : '';

    if (wfContainer) wfContainer.classList.toggle('hidden', !hasFile);
    if (transport) transport.classList.toggle('hidden', !hasFile);
    if (controls) controls.classList.toggle('hidden', !hasFile);

    if (!hasFile) return;

    // Update filename
    $('#slicer-filename').textContent = 
      `${this.fileInfo.name}  ·  ${this.fileInfo.sample_rate/1000}kHz  ·  ${this.fileInfo.duration.toFixed(2)}s`;
    
    // Update time display
    this.updateTimeDisplay();
    
    // Draw waveform (double rAF needed: first for layout, second for size calc)
    requestAnimationFrame(() => requestAnimationFrame(() => this.drawWaveform()));
    
    // Render slice list
    this.renderSliceList();

    // Reflect target-count override state on the relevant controls
    this.updateTargetOverrides();
  },
  
  updateTimeDisplay() {
    if (!this.fileInfo) return;
    const current = this.formatTime(this.currentTime);
    const total = this.formatTime(this.fileInfo.duration);
    $('#slicer-time').textContent = `${current} / ${total}`;
  },
  
  formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = (seconds % 60).toFixed(3).padStart(6, '0');
    return `${mins}:${secs}`;
  },
  
  // Helper: convert time (seconds) to canvas x, accounting for viewport
  timeToX(timeSec, width) {
    const duration = this.fileInfo?.duration || 1;
    const frac = timeSec / duration;
    return ((frac - this.viewStart) / (this.viewEnd - this.viewStart)) * width;
  },

  drawWaveform() {
    const canvas = $('#slicer-canvas');
    if (!canvas || !APP_STATE.slicer_waveform) return;
    
    const ctx = canvas.getContext('2d');
    const allSamples = APP_STATE.slicer_waveform;
    
    // Sync canvas buffer to display size (handle device pixel ratio for sharpness)
    const container = canvas.parentElement;
    const dpr = window.devicePixelRatio || 1;
    const displayWidth = container.clientWidth;
    const displayHeight = container.clientHeight;
    
    if (!displayWidth || !displayHeight) return;
    
    canvas.width = displayWidth * dpr;
    canvas.height = displayHeight * dpr;
    canvas.style.width = displayWidth + 'px';
    canvas.style.height = displayHeight + 'px';
    ctx.scale(dpr, dpr);
    
    const width = displayWidth;
    const height = displayHeight;
    const midY = height / 2;
    
    // Slice visible samples based on viewport
    const startIdx = Math.floor(this.viewStart * allSamples.length);
    const endIdx = Math.ceil(this.viewEnd * allSamples.length);
    const samples = allSamples.slice(startIdx, endIdx);
    
    // Clear
    ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--bg-surface').trim();
    ctx.fillRect(0, 0, width, height);
    
    // Draw waveform
    const accentColor = getComputedStyle(document.body).getPropertyValue('--cyan').trim();
    ctx.fillStyle = accentColor;
    ctx.globalAlpha = 0.6;
    
    const step = width / samples.length;
    
    for (let i = 0; i < samples.length; i++) {
      const x = i * step;
      const h = Math.min(Math.abs(samples[i]) * this.ampScale, 1.0) * height * 0.9;
      ctx.fillRect(x, midY - h/2, Math.max(step, 1), h);
    }
    
    ctx.globalAlpha = 1.0;
    
    // Draw slice markers
    this.drawSliceMarkers(ctx, width, height);
    
    // Draw playhead
    this.drawPlayhead(width, height);
  },
  
  drawSliceMarkers(ctx, width, height) {
    const slices = APP_STATE.slicer_slices || [];
    
    const accentA = getComputedStyle(document.body).getPropertyValue('--cyan').trim();
    const accentB = getComputedStyle(document.body).getPropertyValue('--amber').trim();
    
    ctx.lineWidth = 2;
    
    slices.forEach((slice, i) => {
      const x = this.timeToX(slice.start_ms / 1000, width);
      const endX = this.timeToX(slice.end_ms / 1000, width);
      
      // Highlight the slice currently being previewed
      if (i === this.previewSliceIndex) {
        const clipX = Math.max(0, x);
        const clipEndX = Math.min(width, endX);
        if (clipEndX > clipX) {
          ctx.fillStyle = 'rgba(0, 0, 0, 0.35)';
          ctx.fillRect(clipX, 0, clipEndX - clipX, height);
        }
      }
      
      // Draw start marker (only if visible)
      if (x >= -2 && x <= width + 2) {
        ctx.strokeStyle = accentA;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
        
        // Draw slice number
        ctx.fillStyle = accentA;
        ctx.font = '10px sans-serif';
        ctx.fillText(String(i + 1), Math.max(3, x + 3), 12);
      }
      
      // Draw end marker (if not last slice and visible)
      if (i < slices.length - 1 && endX >= -2 && endX <= width + 2) {
        ctx.strokeStyle = accentB;
        ctx.beginPath();
        ctx.moveTo(endX, 0);
        ctx.lineTo(endX, height);
        ctx.stroke();
      }
    });
  },
  
  drawPlayhead(width, height) {
    const playhead = $('#slicer-playhead');
    if (!playhead || !this.fileInfo) return;
    
    const x = this.timeToX(this.currentTime, width);
    playhead.style.left = `${Math.max(0, Math.min(width, x))}px`;
  },
  
  selectSlice(index) {
    const slices = APP_STATE.slicer_slices || [];
    if (index < 0 || index >= slices.length) return;
    this.selectedSliceIndex = index;
    this.renderSliceList();
    // Scroll selected row into view
    const row = $(`#slicer-slices-tbody tr[data-index="${index}"]`);
    if (row) row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  },

  selectNextSlice() {
    const slices = APP_STATE.slicer_slices || [];
    this.selectSlice(Math.min(this.selectedSliceIndex + 1, slices.length - 1));
  },

  selectPrevSlice() {
    this.selectSlice(Math.max(this.selectedSliceIndex - 1, 0));
  },

  renderSliceList() {
    const tbody = $('#slicer-slices-tbody');
    if (!tbody) return;
    
    const slices = APP_STATE.slicer_slices || [];
    
    tbody.innerHTML = slices.map((slice, i) => `
      <tr data-index="${i}" class="slicer-slice-row${i === this.previewSliceIndex ? ' active' : ''}${i === this.selectedSliceIndex ? ' selected' : ''}">
        <td>
          <button class="btn-icon slicer-play-slice" data-index="${i}" title="Preview slice">▶</button>
          ${i + 1}
        </td>
        <td>${slice.start_str || this.formatTime(slice.start_ms/1000)}</td>
        <td>${slice.end_str || this.formatTime(slice.end_ms/1000)}</td>
        <td>${slice.duration_str || this.formatTime(slice.duration_ms/1000)}</td>
        <td><button class="btn-icon slicer-delete-slice" data-index="${i}" title="Remove">✕</button></td>
      </tr>
    `).join('');
    
    // Play slice buttons
    tbody.querySelectorAll('.slicer-play-slice').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const index = parseInt(e.currentTarget.dataset.index);
        await this.previewSlice(index);
      });
    });
    
    // Delete handlers
    tbody.querySelectorAll('.slicer-delete-slice').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const index = parseInt(e.currentTarget.dataset.index);
        this.deleteSlice(index);
      });
    });
    
    // Row click = select + zoom waveform to slice (keeps keyboard nav in sync)
    tbody.querySelectorAll('.slicer-slice-row').forEach(row => {
      row.addEventListener('click', (e) => {
        if (e.target.closest('button')) return;
        const index = parseInt(row.dataset.index);
        this.selectSlice(index);
        this.zoomToSlice(index);
      });
    });
  },
  
  // Snapshot the current slices onto the undo stack (call BEFORE mutating).
  pushHistory() {
    const slices = APP_STATE.slicer_slices || [];
    this._history.push(slices.map(s => ({ ...s })));
    if (this._history.length > 50) this._history.shift();
    this.updateUndoButton();
  },

  undo() {
    if (!this._history.length) return;
    const prev = this._history.pop();
    APP_STATE.slicer_slices = prev;
    this.selectedSliceIndex = -1;
    pywebview.api.slicer_set_slices(prev);
    this.updateUndoButton();
    this.render();
  },

  updateUndoButton() {
    const btn = $('#slicer-undo');
    if (btn) btn.disabled = this._history.length === 0;
  },

  // Recompute the string + duration fields of a slice after its bounds change
  _recomputeSlice(slice) {
    slice.start_str = this.msToStr(slice.start_ms);
    slice.end_str = this.msToStr(slice.end_ms);
    slice.duration_ms = slice.end_ms - slice.start_ms;
    slice.duration_str = this.msToStr(slice.duration_ms);
  },

  deleteSlice(index) {
    const slices = APP_STATE.slicer_slices || [];
    if (index < 0 || index >= slices.length) return;

    this.pushHistory();
    const removed = slices[index];
    slices.splice(index, 1);

    if (slices.length === 0) {
      // Nothing left — fall back to one slice spanning the whole file.
      // History already snapshotted above, so don't record again.
      this.clearAll(false);
      return;
    }

    // Absorb the removed span so no audio is silently dropped: the previous
    // slice extends over it, or (if we removed the first slice) the new first
    // slice extends back to the removed start. Recompute the merged slice's
    // end/duration strings — the old code left these stale.
    if (index > 0) {
      const prev = slices[index - 1];
      prev.end_ms = removed.end_ms;
      this._recomputeSlice(prev);
    } else {
      const first = slices[0];
      first.start_ms = removed.start_ms;
      this._recomputeSlice(first);
    }

    if (this.selectedSliceIndex >= slices.length) {
      this.selectedSliceIndex = slices.length - 1;
    }

    pywebview.api.slicer_set_slices(slices);
    this.render();
  },
  
  addMarkerAtCursor(timeMs = null) {
    // Add a marker at current time (or provided time)
    const slices = APP_STATE.slicer_slices || [];
    if (timeMs === null) timeMs = this.currentTime * 1000;
    this.pushHistory();
    
    // Find where to insert
    let insertIndex = slices.length;
    for (let i = 0; i < slices.length; i++) {
      if (slices[i].start_ms > timeMs) {
        insertIndex = i;
        break;
      }
    }
    
    // Create new slice
    const newSlice = {
      start_ms: timeMs,
      end_ms: insertIndex < slices.length ? slices[insertIndex].start_ms : this.fileInfo.duration * 1000,
      start_str: this.msToStr(timeMs),
      end_str: insertIndex < slices.length ? slices[insertIndex].start_str : this.msToStr(this.fileInfo.duration * 1000),
      duration_ms: 0,
      duration_str: "0:00.000"
    };
    
    slices.splice(insertIndex, 0, newSlice);
    
    // Update previous slice end
    if (insertIndex > 0) {
      slices[insertIndex - 1].end_ms = timeMs;
      slices[insertIndex - 1].end_str = newSlice.start_str;
    }
    
    // Recalculate durations
    slices.forEach(slice => {
      slice.duration_ms = slice.end_ms - slice.start_ms;
      slice.duration_str = this.msToStr(slice.duration_ms);
    });
    
    pywebview.api.slicer_set_slices(slices);
    this.render();
  },
  
  clearAll(record = true) {
    if (record) this.pushHistory();
    const durationMs = (this.fileInfo?.duration || 0) * 1000;
    APP_STATE.slicer_slices = [{
      start_ms: 0,
      end_ms: durationMs,
      start_str: "0:00.000",
      end_str: this.msToStr(durationMs),
      duration_ms: durationMs,
      duration_str: this.msToStr(durationMs)
    }];
    this.selectedSliceIndex = -1;
    pywebview.api.slicer_set_slices(APP_STATE.slicer_slices);
    this.render();
  },
  
  msToStr(ms) {
    const totalSeconds = ms / 1000;
    const mins = Math.floor(totalSeconds / 60);
    const secs = (totalSeconds % 60).toFixed(3).padStart(6, '0');
    return `${mins}:${secs}`;
  },
  
  async runAutoSlice() {
    const mode = $('#slicer-mode').value;
    const filepath = APP_STATE.slicer_file;

    this.pushHistory();  // auto-slice replaces all slices — make it undoable
    let result;
    
    switch (mode) {
      case 'silence':
        const threshold = parseFloat($('#silence-threshold').value);
        const minLen = parseFloat($('#silence-min').value);
        const padding = parseFloat($('#silence-padding').value);
        result = await pywebview.api.slicer_auto_silence(filepath, threshold, minLen, padding);
        break;
      case 'bpm':
        const bpm = parseFloat($('#bpm-value').value);
        const beats = parseFloat($('#bpm-beats').value);
        result = await pywebview.api.slicer_auto_bpm(filepath, bpm, beats);
        break;
      case 'fixed':
        const length = parseFloat($('#fixed-length').value);
        const fixedCountStr = $('#fixed-target-count').value.trim();
        const fixedTargetCount = fixedCountStr ? parseInt(fixedCountStr, 10) : null;
        result = await pywebview.api.slicer_auto_fixed(filepath, length, fixedTargetCount);
        break;
      case 'transients':
        const sensitivity = parseFloat($('#transient-threshold').value);
        const spacing = parseFloat($('#transient-spacing').value);
        const transCountStr = $('#transient-target-count').value.trim();
        const transTargetCount = transCountStr ? parseInt(transCountStr, 10) : null;
        result = await pywebview.api.slicer_auto_transients(filepath, sensitivity, spacing, transTargetCount);
        break;
    }
    
    if (result && result.success) {
      this.selectedSliceIndex = -1;
      this.render();
    } else {
      log(result?.error || 'Auto-slice failed', 'error');
    }
  },
  
  async export() {
    const filepath = APP_STATE.slicer_file;
    const slices = APP_STATE.slicer_slices || [];
    
    if (!slices.length) {
      log('No slices to export', 'warn');
      return;
    }
    
    let outputDir = $('#slicer-output-dir').value;
    if (!outputDir) {
      outputDir = filepath.substring(0, filepath.lastIndexOf('\\') + 1) || filepath.substring(0, filepath.lastIndexOf('/') + 1);
    }
    
    const prefix = $('#slicer-prefix').value;
    const suffix = $('#slicer-suffix').value;
    const format = $('#slicer-format').value;
    const normalize = $('#slicer-normalize').checked;
    const trim = $('#slicer-trim').checked;
    
    const result = await pywebview.api.slicer_export(
      filepath, slices, outputDir, prefix, suffix, format, normalize, trim
    );
    
    if (result.success) {
      log('Export started...', 'info');
    } else {
      log(result.error || 'Export failed', 'error');
    }
  },
  
  updateProgress() {
    const progress = APP_STATE.slicer_progress || 0;
    const exporting = APP_STATE.slicer_exporting;
    const status = APP_STATE.slicer_status || '';
    
    const progressBar = $('#slicer-progress-bar');
    const progressContainer = $('#slicer-export-progress');
    const statusText = $('#slicer-export-status');
    
    if (progressBar) progressBar.style.width = `${progress}%`;
    if (statusText) statusText.textContent = status;
    if (progressContainer) {
      progressContainer.classList.toggle('hidden', !exporting && progress === 0);
    }
    
    if (!exporting && APP_STATE.slicer_export_result) {
      const result = APP_STATE.slicer_export_result;
      if (result.success) {
        log(`Exported ${result.count} slices to ${result.output_dir}`, 'success');
      } else {
        log(result.error || 'Export failed', 'error');
      }
      APP_STATE.slicer_export_result = null;
    }
  },
  
  // Mode control visibility
  updateModeControls() {
    const mode = $('#slicer-mode').value;

    ['silence', 'bpm', 'fixed', 'transients'].forEach(m => {
      const el = $(`#${m}-controls`);
      if (el) el.classList.toggle('hidden', m !== mode);
    });
    this.updateTargetOverrides();
  },

  // When a target-slice-count is entered, that count overrides the length /
  // sensitivity control — dim + disable it so the precedence is visible.
  updateTargetOverrides() {
    const pairs = [
      ['#fixed-target-count', '#fixed-length'],
      ['#transient-target-count', '#transient-threshold'],
    ];
    pairs.forEach(([countSel, ctrlSel]) => {
      const count = $(countSel);
      const ctrl = $(ctrlSel);
      if (!count || !ctrl) return;
      const overridden = count.value.trim() !== '';
      ctrl.disabled = overridden;
      const field = ctrl.closest('.slicer-field');
      if (field) field.classList.toggle('overridden', overridden);
    });
  },
  
  // Playhead animation loop (timestamp-based for accuracy)
  startPlayheadUpdate() {
    if (!this.playing) return;
    const gen = ++this._playGen;   // stamp this loop; old loops will bail
    let lastTs = null;
    const update = (timestamp) => {
      if (!this.playing || !this.fileInfo || this._playGen !== gen) return;
      if (lastTs !== null) {
        this.currentTime += (timestamp - lastTs) / 1000;
      }
      lastTs = timestamp;
      const stopAt = this.playEnd !== null ? this.playEnd : this.fileInfo.duration;
      if (this.currentTime >= stopAt) {
        this.currentTime = stopAt;
        this.updateTimeDisplay();
        this.onPlaybackStopped();
        return;
      }
      this.updateTimeDisplay();
      this.drawWaveform();
      requestAnimationFrame(update);
    };
    requestAnimationFrame(update);
  },
  
  // Preview a specific slice
  async previewSlice(index) {
    const slices = APP_STATE.slicer_slices || [];
    if (index < 0 || index >= slices.length) return;
    const slice = slices[index];
    this.previewSliceIndex = index;
    this.renderSliceList(); // Update highlight
    this.drawWaveform();     // Re-draw to show active slice highlight
    
    this.currentTime = slice.start_ms / 1000;
    this.playEnd = slice.end_ms / 1000;
    this.playing = true;
    this._inSlicePreview = true;
    this.startPlayheadUpdate();
    
    const result = await pywebview.api.slicer_preview_slice(
      APP_STATE.slicer_file, slice.start_ms, slice.end_ms
    );
    if (!result.success) {
      log(result.error || 'Preview failed', 'error');
    }
  },
  
  // Zoom waveform to show a specific slice
  zoomToSlice(index) {
    const slices = APP_STATE.slicer_slices || [];
    if (index < 0 || index >= slices.length || !this.fileInfo) return;
    const slice = slices[index];
    const duration = this.fileInfo.duration;
    
    // Zoom to show the slice with 20% padding on each side
    const sliceStart = slice.start_ms / 1000 / duration;
    const sliceEnd = slice.end_ms / 1000 / duration;
    const sliceRange = sliceEnd - sliceStart;
    const padding = Math.max(sliceRange * 0.2, 0.02);
    
    this.viewStart = Math.max(0, sliceStart - padding);
    this.viewEnd = Math.min(1, sliceEnd + padding);
    this.drawWaveform();
  },

  // Hit-test a mouse event against slice boundary handles.
  // Returns {index, edge:'start'|'end'} for the closest handle within
  // HANDLE_TOL_PX, or null. Used for drag-to-adjust boundaries.
  hitTestHandle(clientX) {
    const canvas = $('#slicer-canvas');
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const x = clientX - rect.left;
    const width = rect.width;
    const slices = APP_STATE.slicer_slices || [];
    const TOL = 6;
    let best = null, bestDist = TOL;
    slices.forEach((s, i) => {
      const sx = this.timeToX(s.start_ms / 1000, width);
      if (Math.abs(x - sx) <= bestDist) { bestDist = Math.abs(x - sx); best = { index: i, edge: 'start' }; }
      const ex = this.timeToX(s.end_ms / 1000, width);
      if (Math.abs(x - ex) <= bestDist) { bestDist = Math.abs(x - ex); best = { index: i, edge: 'end' }; }
    });
    return best;
  },

  // Move a boundary to a new time (ms), clamped between neighbours. If the
  // boundary is shared with an adjacent slice (contiguous partition), move
  // both sides together so the slices stay edge-to-edge.
  moveBoundary(handle, ms) {
    const slices = APP_STATE.slicer_slices || [];
    const s = slices[handle.index];
    if (!s) return;
    const durMs = (this.fileInfo?.duration || 0) * 1000;
    const MIN = 1;  // ms

    if (handle.edge === 'start') {
      const prev = handle.index > 0 ? slices[handle.index - 1] : null;
      const lower = prev ? prev.start_ms + MIN : 0;
      const upper = s.end_ms - MIN;
      ms = Math.max(lower, Math.min(upper, ms));
      const shared = prev && Math.abs(prev.end_ms - s.start_ms) < 1;
      s.start_ms = ms; this._recomputeSlice(s);
      if (shared) { prev.end_ms = ms; this._recomputeSlice(prev); }
    } else {
      const next = handle.index < slices.length - 1 ? slices[handle.index + 1] : null;
      const lower = s.start_ms + MIN;
      const upper = next ? next.end_ms - MIN : durMs;
      ms = Math.max(lower, Math.min(upper, ms));
      const shared = next && Math.abs(s.end_ms - next.start_ms) < 1;
      s.end_ms = ms; this._recomputeSlice(s);
      if (shared) { next.start_ms = ms; this._recomputeSlice(next); }
    }
  },

  // Play from the current playhead position to the end of the file (real seek).
  // Reuses the slice-extract path so it works on every backend (pygame/NSSound
  // can't seek directly). Used by the Play button and by click-to-seek.
  async playFromCurrent() {
    const file = APP_STATE.slicer_file;
    if (!file || !this.fileInfo) return;
    const startMs = Math.max(0, this.currentTime * 1000);
    const durMs = this.fileInfo.duration * 1000;

    this.playEnd = null;          // play through to the end of the file
    this._inSlicePreview = false; // this is full playback, not a slice preview
    this.previewSliceIndex = -1;
    this.playing = true;
    $('#slicer-play').textContent = '⏸';
    this.startPlayheadUpdate();

    if (startMs > 1) {
      // Extract [startMs, end] to a temp WAV and play it from its start
      await pywebview.api.slicer_preview_slice(file, startMs, durMs);
    } else {
      await pywebview.api.preview_play(file);
    }
  },

  // Called when external playback state changes
  onPlaybackStopped() {
    this.playing = false;
    this.playEnd = null;
    this._inSlicePreview = false;
    this.previewSliceIndex = -1;
    $('#slicer-play').textContent = '▶';
    this.drawWaveform();
  }
};

// Slicer event setup
function setupSlicerEvents() {
  // Open button
  $('#open-slicer')?.addEventListener('click', () => Slicer.open());
  
  // Close button
  $('#slicer-close')?.addEventListener('click', () => Slicer.close());
  
  // Browse button for loading a file into slicer
  $('#slicer-browse-file')?.addEventListener('click', async () => {
    const result = await pywebview.api.slicer_browse_file();
    if (result.success && result.path) {
      await Slicer.open(result.path);
    }
  });
  
  // Arrow key navigation for slice list
  document.addEventListener('keydown', (e) => {
    if (!Slicer.isOpen) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); Slicer.selectNextSlice(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); Slicer.selectPrevSlice(); }
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); Slicer.undo(); }
  });

  // Undo button
  $('#slicer-undo')?.addEventListener('click', () => Slicer.undo());
  
  // Mode selector
  $('#slicer-mode')?.addEventListener('change', () => Slicer.updateModeControls());
  
  // Auto slice button
  $('#slicer-auto-btn')?.addEventListener('click', () => Slicer.runAutoSlice());
  
  // Slice list actions
  $('#slicer-add-marker')?.addEventListener('click', () => Slicer.addMarkerAtCursor());
  $('#slicer-clear-all')?.addEventListener('click', () => Slicer.clearAll());
  
  // Export
  $('#slicer-export-btn')?.addEventListener('click', () => Slicer.export());
  $('#slicer-browse-output')?.addEventListener('click', async () => {
    const result = await pywebview.api.slicer_browse_output();
    if (result.success && result.path) {
      $('#slicer-output-dir').value = result.path;
    }
  });
  
  // Transport controls - hooked to actual playback
  $('#slicer-play')?.addEventListener('click', async () => {
    if (Slicer.playing) {
      await pywebview.api.preview_stop();
      Slicer.playing = false;
      $('#slicer-play').textContent = '▶';
    } else if (APP_STATE.slicer_file) {
      await Slicer.playFromCurrent();  // honours the current playhead position
    }
  });
  
  $('#slicer-volume')?.addEventListener('input', (e) => {
    const vol = parseInt(e.target.value, 10);
    pywebview.api.set_option('slicer_volume', vol);
  });
  
  $('#slicer-stop')?.addEventListener('click', async () => {
    await pywebview.api.preview_stop();
    Slicer._inSlicePreview = false;
    Slicer.previewSliceIndex = -1;
    Slicer.playing = false;
    Slicer.currentTime = 0;
    $('#slicer-play').textContent = '▶';
    Slicer.updateTimeDisplay();
    Slicer.drawWaveform();
  });
  
  // Canvas click to seek (accounting for viewport)
  $('#slicer-canvas')?.addEventListener('click', (e) => {
    if (Slicer._panMoved) { Slicer._panMoved = false; return; }
    if (Slicer._dragMoved) { Slicer._dragMoved = false; return; }
    const canvas = e.target;
    const rect = canvas.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    const timeFrac = Slicer.viewStart + pct * (Slicer.viewEnd - Slicer.viewStart);
    Slicer.currentTime = timeFrac * (Slicer.fileInfo?.duration || 0);
    Slicer.updateTimeDisplay();
    Slicer.drawWaveform();
    // If audio is playing, re-seek it to the clicked position (real seek)
    if (Slicer.playing) Slicer.playFromCurrent();
  });
  
  // Double-click on canvas to insert slice marker at clicked position
  $('#slicer-canvas')?.addEventListener('dblclick', (e) => {
    if (!Slicer.fileInfo) return;
    const rect = e.target.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    const timeFrac = Slicer.viewStart + pct * (Slicer.viewEnd - Slicer.viewStart);
    const timeMs = timeFrac * Slicer.fileInfo.duration * 1000;
    Slicer.addMarkerAtCursor(timeMs);
  });
  
  // Mouse wheel zoom - X zoom on wheel, Y zoom on Shift+wheel
  $('#slicer-canvas')?.addEventListener('wheel', (e) => {
    e.preventDefault();
    const canvas = e.target;
    const rect = canvas.getBoundingClientRect();
    const cursorFrac = (e.clientX - rect.left) / rect.width;
    
    if (e.shiftKey) {
      // Y zoom (amplitude)
      const delta = e.deltaY > 0 ? 0.8 : 1.25;
      Slicer.ampScale = Math.max(0.5, Math.min(8.0, Slicer.ampScale * delta));
    } else {
      // X zoom (time) centered on cursor
      const viewRange = Slicer.viewEnd - Slicer.viewStart;
      const zoomFactor = e.deltaY > 0 ? 1.2 : 0.8;
      const newRange = Math.max(0.02, Math.min(1.0, viewRange * zoomFactor));
      
      // Zoom centered on cursor position
      const anchor = Slicer.viewStart + cursorFrac * viewRange;
      let newStart = anchor - cursorFrac * newRange;
      let newEnd = newStart + newRange;
      
      // Clamp to valid range
      if (newStart < 0) {
        newEnd -= newStart;
        newStart = 0;
      }
      if (newEnd > 1) {
        newStart -= (newEnd - 1);
        newEnd = 1;
      }
      
      Slicer.viewStart = Math.max(0, newStart);
      Slicer.viewEnd = Math.min(1, newEnd);
    }
    Slicer.drawWaveform();
  }, { passive: false });
  
  // Pan with middle-click or Alt+drag; left-click on a boundary handle drags it
  $('#slicer-canvas')?.addEventListener('mousedown', (e) => {
    if (e.button === 1 || e.altKey) {  // middle-click or Alt+drag
      Slicer.isPanning = true;
      Slicer._panMoved = false;
      Slicer.panStartX = e.clientX;
      Slicer.panStartViewStart = Slicer.viewStart;
      e.preventDefault();
      return;
    }
    if (e.button === 0) {  // left-click: grab a boundary handle if one is near
      const handle = Slicer.hitTestHandle(e.clientX);
      if (handle) {
        Slicer.pushHistory();  // snapshot pre-drag state for undo
        Slicer.draggingMarker = handle;
        Slicer._dragMoved = false;
        e.preventDefault();
      }
    }
  });

  // Cursor feedback: ew-resize when hovering a draggable boundary
  $('#slicer-canvas')?.addEventListener('mousemove', (e) => {
    if (Slicer.draggingMarker || Slicer.isPanning) return;
    const canvas = e.currentTarget;
    canvas.style.cursor = Slicer.hitTestHandle(e.clientX) ? 'ew-resize' : 'default';
  });
  
  // Zoom reset button
  $('#slicer-zoom-reset')?.addEventListener('click', () => {
    Slicer.viewStart = 0.0;
    Slicer.viewEnd = 1.0;
    Slicer.ampScale = 1.0;
    Slicer.drawWaveform();
  });
  
  // Threshold sliders
  $('#silence-threshold')?.addEventListener('input', (e) => {
    $('#silence-threshold-val').textContent = `${e.target.value} dB`;
  });
  
  $('#transient-threshold')?.addEventListener('input', (e) => {
    $('#transient-threshold-val').textContent = e.target.value + '×';
  });

  // Target-count fields override their length/sensitivity control — reflect that
  $('#fixed-target-count')?.addEventListener('input', () => Slicer.updateTargetOverrides());
  $('#transient-target-count')?.addEventListener('input', () => Slicer.updateTargetOverrides());
  
  // Window resize - redraw waveform
  window.addEventListener('resize', () => {
    if (Slicer.isOpen) {
      Slicer.drawWaveform();
    }
  });
}

// Global mouse handlers for waveform panning + boundary dragging
window.addEventListener('mousemove', (e) => {
  if (!Slicer.isOpen) return;

  // Dragging a slice boundary takes priority over panning
  if (Slicer.draggingMarker) {
    const canvas = $('#slicer-canvas');
    if (!canvas) return;
    Slicer._dragMoved = true;
    const rect = canvas.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const timeFrac = Slicer.viewStart + pct * (Slicer.viewEnd - Slicer.viewStart);
    const ms = timeFrac * (Slicer.fileInfo?.duration || 0) * 1000;
    Slicer.moveBoundary(Slicer.draggingMarker, ms);
    Slicer.drawWaveform();  // live waveform feedback; table updates on release
    return;
  }

  if (!Slicer.isPanning) return;
  Slicer._panMoved = true;
  const canvas = $('#slicer-canvas');
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const dx = (e.clientX - Slicer.panStartX) / rect.width;
  const viewRange = Slicer.viewEnd - Slicer.viewStart;
  let newStart = Math.max(0, Math.min(1 - viewRange, Slicer.panStartViewStart - dx * viewRange));
  Slicer.viewStart = newStart;
  Slicer.viewEnd = newStart + viewRange;
  Slicer.drawWaveform();
});

window.addEventListener('mouseup', () => {
  Slicer.isPanning = false;
  if (Slicer.draggingMarker) {
    // Commit the edited slices to the backend + refresh the table once the drag ends
    if (Slicer._dragMoved) {
      pywebview.api.slicer_set_slices(APP_STATE.slicer_slices || []);
      Slicer.renderSliceList();
    } else {
      Slicer._history.pop();  // no movement — discard the snapshot taken on mousedown
      Slicer.updateUndoButton();
    }
    Slicer.draggingMarker = null;
  }
});

// Update renderPatch to handle slicer state
const originalRenderPatch = renderPatch;
renderPatch = function(patch) {
  originalRenderPatch(patch);
  
  const keys = Object.keys(patch);
  
  if (keys.includes('slicer_open')) {
    Slicer.isOpen = APP_STATE.slicer_open;
    Slicer.render();
  }
  
  if (keys.includes('slicer_waveform') || keys.includes('slicer_slices') || 
      keys.includes('slicer_file_info')) {
    if (Slicer.isOpen) {
      Slicer.render();
    }
  }
  
  if (keys.includes('slicer_progress') || keys.includes('slicer_exporting') || 
      keys.includes('slicer_export_result')) {
    Slicer.updateProgress();
  }
  
  // Handle external playback stop
  if (keys.includes('is_playing') && !APP_STATE.is_playing && Slicer.playing && !Slicer._inSlicePreview) {
    Slicer.onPlaybackStopped();
  }
  
  // Audition Stack state
  if (keys.includes('audition_open')) {
    Audition.isOpen = APP_STATE.audition_open;
    Audition.render();
  }
  if (keys.includes('audition_tracks') || keys.includes('audition_master_bpm') || 
      keys.includes('audition_loop') || keys.includes('audition_status') || 
      keys.includes('audition_rendering') || keys.includes('audition_selection')) {
    if (Audition.isOpen) {
      Audition.render();
    }
    // Re-render Deck B to update stack indicators
    if (keys.includes('audition_selection')) {
      renderDeckB();
    }
  }
};

// ============================================================================
// Audition Stack
// ============================================================================

const Audition = {
  isOpen: false,
  
  open() {
    pywebview.api.audition_open_modal();
  },
  
  close() {
    pywebview.api.audition_close();
    this.isOpen = false;
    this.render();
  },
  
  render() {
    const modal = $('#audition-modal');
    if (!modal) return;
    modal.classList.toggle('hidden', !this.isOpen);
    if (!this.isOpen) return;
    
    this.renderSlots();
    this.updateStatus();
    
    // Update global controls
    const masterBpmInput = $('#audition-master-bpm');
    if (masterBpmInput) masterBpmInput.value = APP_STATE.audition_master_bpm || 120;
    const loopCb = $('#audition-loop');
    if (loopCb) loopCb.checked = APP_STATE.audition_loop || false;
    
    // Disable preview while rendering
    const previewBtn = $('#audition-preview');
    if (previewBtn) previewBtn.disabled = APP_STATE.audition_rendering || false;
  },
  
  renderSlots() {
    const container = $('#audition-slots');
    if (!container) return;
    
    const tracks = APP_STATE.audition_tracks || [null, null, null, null];
    
    container.innerHTML = tracks.map((track, i) => {
      if (!track) {
        return `
          <div class="audition-slot audition-slot-empty">
            <div class="audition-slot-header">Slot ${i + 1}</div>
            <div class="audition-slot-empty-text">Empty</div>
            <button class="btn-small audition-browse-track" data-index="${i}">Browse</button>
          </div>
        `;
      }
      
      const bpmSyncChecked = track.bpm_sync ? 'checked' : '';
      const mutedChecked = track.muted ? 'checked' : '';
      const soloChecked = track.solo ? 'checked' : '';
      const sourceBpmDisplay = track.source_bpm ? `~${Math.round(track.source_bpm)} BPM` : '—';
      
      return `
        <div class="audition-slot">
          <div class="audition-slot-header">
            <span>Slot ${i + 1}</span>
            <span class="audition-slot-name" title="${escapeHtml(track.path || '')}">${escapeHtml(track.name || '')}</span>
          </div>
          <div class="audition-slot-controls">
            <div class="audition-control-row">
              <label class="check-label"><input type="checkbox" class="audition-mute" data-index="${i}" ${mutedChecked} /> Mute</label>
              <label class="check-label"><input type="checkbox" class="audition-solo" data-index="${i}" ${soloChecked} /> Solo</label>
            </div>
            <div class="audition-control-row">
              <label>Vol</label>
              <input type="range" class="audition-volume" data-index="${i}" min="0" max="100" value="${track.volume || 80}" />
              <span class="audition-val">${track.volume || 80}%</span>
            </div>
            <div class="audition-control-row">
              <label>Offset ~</label>
              <input type="number" class="audition-offset text-input" data-index="${i}" value="${track.offset_ms || 0}" min="-2000" max="2000" step="10" />
              <span class="audition-val">ms</span>
            </div>
            <div class="audition-control-row">
              <label>Pitch ~</label>
              <input type="number" class="audition-pitch text-input" data-index="${i}" value="${track.pitch || 0}" min="-12" max="12" step="1" />
              <span class="audition-val">st</span>
            </div>
            <div class="audition-control-row">
              <label class="check-label"><input type="checkbox" class="audition-bpm-sync" data-index="${i}" ${bpmSyncChecked} /> BPM sync</label>
              <span class="audition-val">${sourceBpmDisplay}</span>
            </div>
            <div class="audition-slot-actions">
              <button class="btn-small audition-browse-track" data-index="${i}">Browse</button>
              <button class="btn-small audition-remove-track" data-index="${i}">Remove</button>
            </div>
          </div>
        </div>
      `;
    }).join('');
    
    // Attach event listeners to dynamic controls
    container.querySelectorAll('.audition-browse-track').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const idx = parseInt(e.currentTarget.dataset.index);
        const result = await pywebview.api.audition_browse_track(idx);
        if (result.success && result.path) {
          // Track updated by state push
        }
      });
    });
    
    container.querySelectorAll('.audition-remove-track').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const idx = parseInt(e.currentTarget.dataset.index);
        pywebview.api.audition_remove_track(idx);
      });
    });
    
    container.querySelectorAll('.audition-mute').forEach(cb => {
      cb.addEventListener('change', (e) => {
        const idx = parseInt(e.currentTarget.dataset.index);
        pywebview.api.audition_set_track(idx, { muted: e.target.checked });
      });
    });
    
    container.querySelectorAll('.audition-solo').forEach(cb => {
      cb.addEventListener('change', (e) => {
        const idx = parseInt(e.currentTarget.dataset.index);
        pywebview.api.audition_set_track(idx, { solo: e.target.checked });
      });
    });
    
    container.querySelectorAll('.audition-volume').forEach(input => {
      input.addEventListener('input', (e) => {
        const idx = parseInt(e.currentTarget.dataset.index);
        const val = parseInt(e.target.value, 10);
        const valEl = e.target.nextElementSibling;
        if (valEl) valEl.textContent = val + '%';
        pywebview.api.audition_set_track(idx, { volume: val });
      });
    });
    
    container.querySelectorAll('.audition-offset').forEach(input => {
      input.addEventListener('change', (e) => {
        const idx = parseInt(e.currentTarget.dataset.index);
        pywebview.api.audition_set_track(idx, { offset_ms: parseInt(e.target.value, 10) || 0 });
      });
    });
    
    container.querySelectorAll('.audition-pitch').forEach(input => {
      input.addEventListener('change', (e) => {
        const idx = parseInt(e.currentTarget.dataset.index);
        pywebview.api.audition_set_track(idx, { pitch: parseInt(e.target.value, 10) || 0 });
      });
    });
    
    container.querySelectorAll('.audition-bpm-sync').forEach(cb => {
      cb.addEventListener('change', (e) => {
        const idx = parseInt(e.currentTarget.dataset.index);
        pywebview.api.audition_set_track(idx, { bpm_sync: e.target.checked });
      });
    });
  },
  
  updateStatus() {
    const statusEl = $('#audition-status');
    if (!statusEl) return;
    const status = APP_STATE.audition_status || '';
    const rendering = APP_STATE.audition_rendering || false;
    statusEl.textContent = status;
    statusEl.classList.toggle('rendering', rendering);
  },
  
  async preview() {
    const result = await pywebview.api.audition_render_and_play();
    if (!result.success) {
      log(result.error || 'Preview failed', 'error');
    }
  },
  
  async stop() {
    await pywebview.api.audition_stop();
  }
};

function setupAuditionEvents() {
  $('#btn-audition')?.addEventListener('click', () => Audition.open());
  $('#audition-close')?.addEventListener('click', () => Audition.close());
  
  $('#audition-preview')?.addEventListener('click', () => Audition.preview());
  $('#audition-stop')?.addEventListener('click', () => Audition.stop());
  
  $('#audition-master-bpm')?.addEventListener('change', (e) => {
    pywebview.api.audition_set_master_bpm(parseFloat(e.target.value));
  });
  
  $('#audition-loop')?.addEventListener('change', (e) => {
    pywebview.api.set_option('audition_loop', e.target.checked);
  });
}

// Start once pywebview is ready
window.addEventListener('pywebviewready', () => {
  init();
  setupSlicerEvents();
  setupAuditionEvents();
});
