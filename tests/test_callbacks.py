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


class TestRegisterPostRecordCallback:
    def _make_record(self, **overrides):
        from autolineage.core import TransformationRecord
        defaults = dict(
            library="pandas",
            category="transform",
            operation="filter",
            child_id="lid-child",
            parent_ids=["lid-parent"],
            duration_ms=12.5,
        )
        defaults.update(overrides)
        return TransformationRecord(**defaults)

    def test_callback_fires_with_record(self):
        """record() must invoke registered callbacks with the
        TransformationRecord that was just appended."""
        from autolineage.core.tracker import UnifiedTracker

        tracker = UnifiedTracker()
        fired: list = []
        tracker.register_post_record_callback(lambda r: fired.append(r))

        rec = self._make_record()
        tracker.record(rec)

        assert len(fired) == 1
        assert fired[0] is rec

    def test_record_already_in_records_when_callback_fires(self):
        """By the time the callback runs, ``tracker.records[-1]`` is the
        same record. Downstream consumers can rely on tracker state being
        consistent inside the callback."""
        from autolineage.core.tracker import UnifiedTracker

        tracker = UnifiedTracker()
        observed_last: list = []

        def cb(r):
            observed_last.append(tracker.records[-1])

        tracker.register_post_record_callback(cb)
        rec = self._make_record()
        tracker.record(rec)

        assert observed_last == [rec]

    def test_multiple_callbacks_fire_in_order(self):
        from autolineage.core.tracker import UnifiedTracker

        tracker = UnifiedTracker()
        order: list = []
        tracker.register_post_record_callback(lambda r: order.append("a"))
        tracker.register_post_record_callback(lambda r: order.append("b"))

        tracker.record(self._make_record())
        assert order == ["a", "b"]

    def test_callback_exception_does_not_propagate(self):
        from autolineage.core.tracker import UnifiedTracker

        tracker = UnifiedTracker()

        def angry(r):
            raise RuntimeError("simulated failure")

        tracker.register_post_record_callback(angry)
        # Must not raise
        tracker.record(self._make_record())
        # Record was still appended despite the buggy callback
        assert len(tracker.records) == 1

    def test_one_buggy_callback_does_not_block_others(self):
        from autolineage.core.tracker import UnifiedTracker

        tracker = UnifiedTracker()
        b_fired: list = []

        tracker.register_post_record_callback(
            lambda r: (_ for _ in ()).throw(RuntimeError("a fails"))
        )
        tracker.register_post_record_callback(lambda r: b_fired.append(r))

        rec = self._make_record()
        tracker.record(rec)
        assert b_fired == [rec]

    def test_no_callbacks_registered_is_a_no_op(self):
        from autolineage.core.tracker import UnifiedTracker

        tracker = UnifiedTracker()
        tracker.record(self._make_record())
        assert len(tracker.records) == 1


class TestGetOrAssignFiresCallbackOnReuse:
    """v0.6.1 regression: get_or_assign must fire the assign_id callback
    even when an existing lid is returned (e.g., DataFrame whose
    attrs['_lineage_id'] was preserved across a pandas operation).

    Without this, downstream consumers like RudriQ only ever see the
    first object instance that got the lid; subsequent instances with
    the same lid (a NEW DataFrame from sort_values that pandas gave
    the same attrs) are missed by id() lookups, breaking identity-
    based cross-domain correlation."""

    def test_get_or_assign_fires_callback_when_lid_already_assigned(self):
        from autolineage.core.tracker import UnifiedTracker

        tracker = UnifiedTracker()
        fired: list = []
        tracker.register_assign_id_callback(
            lambda obj, lid: fired.append((id(obj), lid))
        )

        # First object: no existing lid; assign_id fires once.
        obj_a = {"name": "a"}
        lid_a = tracker.get_or_assign(obj_a, source="test")
        assert len(fired) == 1
        assert fired[0] == (id(obj_a), lid_a)

        # Second call with the SAME object: already has a lid (via
        # _id_to_lid since dict has no attrs). Callback should fire
        # AGAIN with the same (id, lid) pair, signaling "downstream
        # may want to refresh its mapping".
        lid_a2 = tracker.get_or_assign(obj_a, source="test")
        assert lid_a2 == lid_a
        assert len(fired) == 2
        assert fired[1] == (id(obj_a), lid_a)

    def test_callback_fires_for_new_instance_with_preserved_lid(self):
        """Simulates the pandas-attrs scenario: a new object instance
        whose attrs already carry a previously-assigned lineage ID.
        get_or_assign should NOT mint a new lid (returning the existing
        one), but SHOULD fire the callback so consumers can mirror
        ``id(new_instance) -> lid``."""
        from autolineage.core.tracker import UnifiedTracker

        class _Attrsy:
            """Mimics a pandas DataFrame: has an attrs dict that
            preserves the lineage_id across instances."""
            def __init__(self, attrs):
                self.attrs = attrs

        shared_attrs = {}
        first = _Attrsy(shared_attrs)
        tracker = UnifiedTracker()

        fired: list = []
        tracker.register_assign_id_callback(
            lambda obj, lid: fired.append((id(obj), lid))
        )

        lid = tracker.get_or_assign(first, source="seed")
        assert len(fired) == 1
        assert fired[0] == (id(first), lid)

        # Second instance with the SAME attrs dict (so the same
        # _lineage_id key) — simulates pandas returning a fresh
        # DataFrame from sort_values that preserved attrs.
        second = _Attrsy(shared_attrs)
        assert id(second) != id(first)
        lid2 = tracker.get_or_assign(second, source="reuse")
        assert lid2 == lid
        # Callback fired again, this time with the second instance's id.
        assert len(fired) == 2
        assert fired[1] == (id(second), lid)
        assert fired[1][0] != fired[0][0]  # different ids, same lid
