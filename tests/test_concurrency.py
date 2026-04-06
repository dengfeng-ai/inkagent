"""Tests for concurrency safety: ContextVar isolation and per-session locking."""

import threading
import time

import pytest

from inkagent import session
from inkagent.session import (
    get_conversation,
    get_session_lock,
    inject_message,
    make_message,
    save_conversation,
)


pytestmark = pytest.mark.usefixtures("tmp_memory_dir")


# ---------------------------------------------------------------------------
# ContextVar isolation
# ---------------------------------------------------------------------------

class TestContextVarIsolation:
    def test_default_value(self):
        assert session.current_session_id.get() == "cli"

    def test_set_and_get(self):
        session.current_session_id.set("tg_123")
        assert session.current_session_id.get() == "tg_123"

    def test_threads_have_independent_values(self):
        """Each thread should see its own value of current_session_id."""
        results = {}
        barrier = threading.Barrier(2)

        def worker(name: str, value: str) -> None:
            session.current_session_id.set(value)
            barrier.wait()  # both threads set before either reads
            time.sleep(0.01)  # small delay to increase chance of cross-read
            results[name] = session.current_session_id.get()

        t1 = threading.Thread(target=worker, args=("t1", "session_A"))
        t2 = threading.Thread(target=worker, args=("t2", "session_B"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results["t1"] == "session_A"
        assert results["t2"] == "session_B"

    def test_thread_does_not_affect_main(self):
        session.current_session_id.set("main_session")

        def worker():
            session.current_session_id.set("thread_session")

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        assert session.current_session_id.get() == "main_session"


# ---------------------------------------------------------------------------
# Per-session locking
# ---------------------------------------------------------------------------

class TestSessionLock:
    def test_same_session_returns_same_lock(self):
        lock1 = get_session_lock("s1")
        lock2 = get_session_lock("s1")
        assert lock1 is lock2

    def test_different_sessions_get_different_locks(self):
        lock1 = get_session_lock("s1")
        lock2 = get_session_lock("s2")
        assert lock1 is not lock2

    def test_lock_serializes_access(self):
        """Two threads on the same session should not overlap."""
        sid = "locked_session"
        order = []
        lock = get_session_lock(sid)

        def worker(name: str, delay: float) -> None:
            with lock:
                order.append(f"{name}_start")
                time.sleep(delay)
                order.append(f"{name}_end")

        t1 = threading.Thread(target=worker, args=("first", 0.05))
        t2 = threading.Thread(target=worker, args=("second", 0.01))
        t1.start()
        time.sleep(0.01)  # ensure t1 acquires first
        t2.start()
        t1.join()
        t2.join()

        # first must complete before second starts
        assert order == ["first_start", "first_end", "second_start", "second_end"]

    def test_different_sessions_run_concurrently(self):
        """Two threads on different sessions should run in parallel."""
        timestamps = {}
        barrier = threading.Barrier(2)

        def worker(sid: str) -> None:
            lock = get_session_lock(sid)
            with lock:
                barrier.wait()  # both must be holding their locks at the same time
                timestamps[sid] = time.monotonic()

        t1 = threading.Thread(target=worker, args=("sess_A",))
        t2 = threading.Thread(target=worker, args=("sess_B",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Both reached the barrier while holding locks — they ran concurrently
        assert "sess_A" in timestamps
        assert "sess_B" in timestamps


# ---------------------------------------------------------------------------
# inject_message with locking
# ---------------------------------------------------------------------------

class TestInjectMessageLocking:
    def test_inject_waits_for_lock(self):
        """inject_message should block if another thread holds the session lock."""
        sid = "inject_lock_test"
        lock = get_session_lock(sid)
        order = []

        lock.acquire()
        order.append("main_acquired")

        def injector():
            order.append("injector_waiting")
            inject_message(sid, "assistant", "from cron")
            order.append("injector_done")

        t = threading.Thread(target=injector)
        t.start()
        time.sleep(0.05)  # give injector time to block

        # injector should be waiting, not done
        assert "injector_done" not in order

        order.append("main_releasing")
        lock.release()
        t.join()

        assert order == [
            "main_acquired",
            "injector_waiting",
            "main_releasing",
            "injector_done",
        ]

        # Message should have been injected
        conv = get_conversation(sid)
        assert len(conv) == 1
        assert conv[0]["content"] == "from cron"

    def test_concurrent_inject_no_message_loss(self):
        """Multiple concurrent inject_message calls should not lose messages."""
        sid = "multi_inject"
        n_threads = 10

        def injector(i: int) -> None:
            inject_message(sid, "user", f"msg_{i}")

        threads = [threading.Thread(target=injector, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        conv = get_conversation(sid)
        assert len(conv) == n_threads
        contents = {m["content"] for m in conv}
        assert contents == {f"msg_{i}" for i in range(n_threads)}
