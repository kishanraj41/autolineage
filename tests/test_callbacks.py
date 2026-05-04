"""Tests for UnifiedTracker's callback registration API (v0.5.0+)."""

import pytest


class TestRegisterAssignIdCallback:
    def test_callback_fires_with_obj_and_lid(self):
        """assign_id must invoke registered callbacks with (obj, lid)
        after the lid has been computed and stored."""
        from autolineage.core.tracker import UnifiedTracker

        tracker = UnifiedTracker()
        fired: list = []

        tracker.register_assign_id_callback(lambda obj, lid: fired.append((obj, lid)))

        sentinel = {"id": "marker"}
        lid = tracker.assign_id(sentinel, source="test")

        assert len(fired) == 1
        fired_obj, fired_lid = fired[0]
        assert fired_obj is sentinel
        assert fired_lid == lid

    def test_multiple_callbacks_all_fire(self):
        """Every registered callback fires, in registration order."""
        from autolineage.core.tracker import UnifiedTracker

        tracker = UnifiedTracker()
        order: list = []
        tracker.register_assign_id_callback(lambda o, l: order.append("a"))
        tracker.register_assign_id_callback(lambda o, l: order.append("b"))
        tracker.register_assign_id_callback(lambda o, l: order.append("c"))

        tracker.assign_id({"x": 1}, source="test")

        assert order == ["a", "b", "c"]

    def test_callback_exception_does_not_propagate(self):
        """A buggy callback must be caught; assign_id keeps working and
        returns the lid normally."""
        from autolineage.core.tracker import UnifiedTracker

        tracker = UnifiedTracker()

        def angry(obj, lid):
            raise RuntimeError("simulated failure")

        tracker.register_assign_id_callback(angry)

        lid = tracker.assign_id({"x": 1}, source="test")
        assert isinstance(lid, str) and len(lid) > 0

    def test_one_buggy_callback_does_not_block_others(self):
        """If callback A raises, callback B must still fire."""
        from autolineage.core.tracker import UnifiedTracker

        tracker = UnifiedTracker()
        b_fired: list = []

        tracker.register_assign_id_callback(
            lambda o, l: (_ for _ in ()).throw(RuntimeError("a fails"))
        )
        tracker.register_assign_id_callback(lambda o, l: b_fired.append((o, l)))

        sentinel = {"x": 1}
        tracker.assign_id(sentinel, source="test")

        assert len(b_fired) == 1
        assert b_fired[0][0] is sentinel

    def test_no_callbacks_registered_is_a_no_op(self):
        """assign_id with zero callbacks must work normally."""
        from autolineage.core.tracker import UnifiedTracker

        tracker = UnifiedTracker()
        lid = tracker.assign_id({"x": 1}, source="test")
        assert isinstance(lid, str) and len(lid) > 0

    def test_callback_receives_lid_already_stored(self):
        """When the callback fires, the (obj -> lid) mapping is already
        queryable via tracker.get_id(obj). Important for downstream
        consumers that read tracker state during the callback."""
        from autolineage.core.tracker import UnifiedTracker

        tracker = UnifiedTracker()
        observed_lid_via_get_id: list = []

        def cb(obj, lid):
            observed_lid_via_get_id.append(tracker.get_id(obj))

        tracker.register_assign_id_callback(cb)

        sentinel = {"x": 1}
        lid = tracker.assign_id(sentinel, source="test")

        assert observed_lid_via_get_id == [lid]
