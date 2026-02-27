import state
import theme


def log(msg):
    state.log_text.configure(state="normal")
    m = msg.strip()
    if "[DRY]" in m:
        tag = "dry"
    elif m.startswith("MOVE"):
        tag = "move"
    elif m.startswith("COPY"):
        tag = "copy"
    elif m == "Done.":
        tag = "done"
    else:
        tag = "plain"
    state.log_text.insert("end", msg + "\n", tag)
    state.log_text.see("end")
    state.log_text.configure(state="disabled")


def setup_log_tags():
    state.log_text.tag_configure("plain", foreground=theme.FG_ON_SURF)
    state.log_text.tag_configure("move",  foreground=theme.C_MOVE)
    state.log_text.tag_configure("copy",  foreground=theme.C_COPY)
    state.log_text.tag_configure("dry",   foreground=theme.C_DRY)
    state.log_text.tag_configure("done",  foreground=theme.C_DONE, font=(theme.FONT_MONO, 9, "bold"))


def clear_log():
    state.log_text.configure(state="normal")
    state.log_text.delete("1.0", "end")
    state.log_text.configure(state="disabled")
