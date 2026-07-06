"""Behavioral tests for the sync execution safety rails and state helpers."""

import time

import pytest

import operations
import state


def wait_for(cond, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def sync_ready(tmp_path):
    """Minimal state so run_sync() will start."""
    state.update({
        "sync_plan_ready": True,
        "sync_in_progress": False,
        "is_running": False,
        "convert_enabled": False,
        "move": False,
        "sync_mode": "additive",
        "dest": str(tmp_path),
    }, push=False)
    yield tmp_path
    state.update({"sync_plan": [], "sync_plan_ready": False}, push=False)


def delete_entry(path):
    return {"action": "delete", "src_name": "", "srcpath": None,
            "dest_path": str(path), "dest_display": path.name,
            "rel_sub": "", "new_name": "",
            "dest_size": path.stat().st_size if path.exists() else None}


class TestSyncDryRun:
    def test_dry_run_deletes_nothing_and_keeps_plan(self, sync_ready):
        victim = sync_ready / "victim.wav"
        victim.write_bytes(b"DATA")
        state.set("dry", True, push=False)
        state.set("sync_plan", [delete_entry(victim)], push=False)

        assert operations.run_sync()["success"]
        assert wait_for(lambda: not state.get("sync_in_progress"))
        assert victim.exists()
        assert state.get("sync_plan_ready") is True

    def test_real_run_deletes_and_clears_plan(self, sync_ready):
        victim = sync_ready / "victim.wav"
        victim.write_bytes(b"DATA")
        state.set("dry", False, push=False)
        state.set("sync_plan", [delete_entry(victim)], push=False)

        assert operations.run_sync()["success"]
        assert wait_for(lambda: not state.get("sync_in_progress"))
        assert not victim.exists()
        assert state.get("sync_plan_ready") is False


class TestSyncStaleness:
    def test_changed_file_not_deleted(self, sync_ready):
        victim = sync_ready / "victim.wav"
        victim.write_bytes(b"DATA")
        entry = delete_entry(victim)
        victim.write_bytes(b"DATA-CHANGED-SINCE-PLAN")  # size differs now

        state.set("dry", False, push=False)
        state.set("sync_plan", [entry], push=False)

        assert operations.run_sync()["success"]
        assert wait_for(lambda: not state.get("sync_in_progress"))
        assert victim.exists(), "changed file must survive a stale delete"

    def test_vanished_file_skipped_without_error(self, sync_ready):
        victim = sync_ready / "victim.wav"
        victim.write_bytes(b"DATA")
        entry = delete_entry(victim)
        victim.unlink()

        state.set("dry", False, push=False)
        state.set("sync_plan", [entry], push=False)

        assert operations.run_sync()["success"]
        assert wait_for(lambda: not state.get("sync_in_progress"))


class TestConcurrencyGuards:
    def test_run_sync_refused_while_running(self, sync_ready):
        state.set("is_running", True, push=False)
        state.set("sync_plan", [{"action": "skip"}], push=False)
        result = operations.run_sync()
        state.set("is_running", False, push=False)
        assert not result["success"]

    def test_run_tool_resets_is_running_on_bad_source(self):
        state.update({"is_running": True, "active_dir": "Z:/nope",
                      "source": "", "dest": "."}, push=False)
        operations.run_tool()
        assert state.get("is_running") is False


class TestStateHelpers:
    def test_add_log_pushes_single_entry(self, silent_state_push):
        state.clear_log()
        silent_state_push.clear()
        state.add_log("hello", "info")
        appends = [p for p in silent_state_push if "log_append" in p]
        assert len(appends) == 1
        assert appends[0]["log_append"]["message"] == "hello"

    def test_log_trimmed_to_500(self):
        state.clear_log()
        for i in range(520):
            state.add_log(f"line {i}")
        lines = state.get("log_lines")
        assert len(lines) == 500
        assert lines[-1]["message"] == "line 519"

    def test_set_status_clamps_progress(self):
        state.set_status("x", 150)
        assert state.get("progress") == 100
        state.set_status("x", -5)
        assert state.get("progress") == 0
