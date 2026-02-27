# All mutable application state.
#
# Every other module does `import state` (NOT `from state import x`) and
# accesses values as `state.root`, `state.dir_browser`, etc.  Attribute
# mutation on the module object is visible everywhere — this is the standard
# Python pattern for shared mutable globals across a multi-file app.

root              = None
active_dir_var    = None
source_var        = None
dest_var          = None
move_var          = None
dry_var           = None
src_count_var     = None
preview_count_var = None
status_var        = None
progress_var      = None
preview_tree      = None
log_text          = None
run_btn           = None
dir_browser       = None
nav_path_var      = None
_status_dot       = None

_browser_items     = []
_browser_press_idx = None   # listbox index held during mouse press; None if not pressing
_preview_after     = None
_is_dark           = True   # current theme state
_dpi_scale         = 1.0    # pixels-per-96-dpi-pixel; set once at startup
profile_var        = None   # tk.StringVar — key into constants.PROFILES; default "Generic"
struct_mode_var    = None   # tk.StringVar — "flat" | "mirror" | "parent"
no_rename_var      = None
_tooltip_win       = None   # active hover tooltip Toplevel (or None)
_tooltip_item      = None   # item_id currently shown in tooltip

_playback_file     = None   # Path of file currently loaded (or None)
_is_playing        = False  # True while pygame.mixer is playing
transport_prev_btn = None   # ttk.Button refs for enable/disable
transport_play_btn = None
transport_next_btn = None
