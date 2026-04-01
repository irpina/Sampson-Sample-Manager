# ui/ — Frontend (HTML/CSS/JS)

Single-page app rendered by PyWebView. All UI logic in `app.js`; styling in `style.css`; structure in `index.html`.

## Files

| File | Description |
|------|-------------|
| `index.html` | App shell — HTML structure, no logic |
| `app.js` | All JS: state sync, rendering, event handlers, API calls |
| `style.css` | CSS variables, dark/light themes, layout |
| `sampsontransparentwhite.png` | Logo for dark mode (white logo) |
| `sampsontransparent2.png` | Logo for light mode (dark logo) |

**Logo files must stay in `ui/`** — PyWebView uses `http_server=False` (file:// URLs) and WKWebView's sandbox blocks `../` parent directory access.

---

## app.js Architecture

### State
```js
const APP_STATE = {};   // mirrors Python state dict
```
Updated by `window._onStateUpdate(patch)` — called from Python via `state.push_keys()`.

### Init
```js
window.addEventListener('pywebviewready', init);
```
`init()` calls `pywebview.api.get_state()`, then `renderAll()`.

### Rendering
- `renderAll()` — full render on init or theme change
- `renderPatch(patch)` — selective render when state keys change
  - `dir_entries` / `active_dir` / `src_count` → `renderDeckA()`
  - option keys → `renderCenterPanel()`
  - `status` / `progress` / `is_running` → `renderStatus()`
  - `log_lines` → `renderLog()`
  - `preview_entries` / `dest` / `is_playing` → `renderDeckB()`

### Theme
```js
function toggleTheme()   // called by #theme-toggle click
function updateLogo(isDark)  // swaps logo src
```
Adds/removes `body.light-mode` class. Calls `pywebview.api.set_option('is_dark', ...)`.

### API Calls
All backend calls via `pywebview.api.*`. Pattern:
```js
await pywebview.api.method_name(args);
// Results come back via state push, not return value
```

---

## style.css Architecture

### CSS Variables

Dark mode (default) defined in `:root`:
```css
--bg-root, --bg-surface, --bg-surface-2, --border
--text, --text-muted
--cyan, --cyan-dark, --cyan-tint
--amber, --amber-dark, --amber-tint
--green
--radius, --header-height
```

Light mode (70s groovy) overrides in `body.light-mode`:
```css
--bg-root: #f5e6c8    /* parchment cream */
--bg-surface: #ede0b0  /* harvest wheat */
--cyan: #6b9e4f        /* avocado green */
--amber: #d4622a       /* burnt orange */
--green: #8b6914       /* goldenrod */
/* etc. */
```

### Layout
```
.app (flex column, 100vh)
  .header (fixed height: var(--header-height))
  .main-grid (flex row, flex: 1)
    .deck-a  (flex: 3, full height, border-left: 4px cyan)
    .center-col (flex: 2, flex column)
      .center-panel (flex: 1, scrollable)
      .status-bar
      .log-panel
    .deck-b  (flex: 3, full height, border-left: 4px amber)
```

Both deck accent bars extend full height naturally — no calc() hacks.

### Key CSS Rules

- `.deck-a .deck-header` / `.deck-b .deck-header`: use `var(--cyan-tint)` / `var(--amber-tint)` (theme-aware)
- `.btn-run:hover` / `.btn-play:hover`: use `filter: brightness(0.85)` (theme-neutral)
- `.btn-transport`: styled consistently with other buttons (background, border, hover)
- Logo: `.logo { overflow: hidden; height: 28px; width: 120px }` + `#logo-img { object-fit: cover; object-position: center 40% }` for white logo padding compensation

---

## Critical Rules

- **Never use `../` paths for assets** — use relative paths from `ui/` (e.g. `sampsontransparentwhite.png`, not `../sampsontransparentwhite.png`)
- **All API results come via state push** — don't rely on return values from `pywebview.api.*` for data; check `APP_STATE` after the push
- **`window._onStateUpdate(patch)`** must remain available — Python calls it via `evaluate_js()`
- **`isEditing` flag** prevents keyboard navigation while an inline BPM/key edit is active — check it before handling `keydown`
- **`escapeHtml()`** must be used on all user-controlled strings rendered into innerHTML
- **`pywebviewready`** event fires when the bridge is ready — do NOT call `pywebview.api.*` before this event
