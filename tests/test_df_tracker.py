"""
Tests for in-memory DataFrame transformation tracking.

Tests the core innovation: automatic tracking of pandas DataFrame
transformations without any code changes from the user.
"""

import pytest
import pandas as pd
import numpy as np
import os
import tempfile

from autolineage.df_tracker import DataFrameLineageTracker, get_df_tracker, reset_df_tracker


@pytest.fixture(autouse=True)
def fresh_tracker():
    """Reset the global tracker before each test."""
    reset_df_tracker()
    yield
    reset_df_tracker()


class TestDataFrameLineageTracker:
    """Test the core DataFrame lineage tracker."""

    def test_register_df(self):
        tracker = DataFrameLineageTracker()
        df = pd.DataFrame({'a': [1, 2, 3]})
        lid = tracker.register_df(df, source="test")

        assert lid is not None
        assert lid in tracker.nodes
        assert tracker.nodes[lid]['source'] == "test"
        assert tracker.nodes[lid]['shape'] == (3, 1)
        assert df.attrs.get('_lineage_id') == lid

    def test_register_df_with_filepath(self):
        tracker = DataFrameLineageTracker()
        df = pd.DataFrame({'x': [1]})
        lid = tracker.register_df(df, source="read_csv", filepath="/data/test.csv")

        assert tracker._file_to_node["/data/test.csv"] == lid

    def test_get_lineage_id(self):
        tracker = DataFrameLineageTracker()
        df = pd.DataFrame({'a': [1]})
        lid = tracker.register_df(df)

        assert tracker.get_lineage_id(df) == lid

    def test_get_lineage_id_untracked(self):
        tracker = DataFrameLineageTracker()
        df = pd.DataFrame({'a': [1]})

        assert tracker.get_lineage_id(df) is None

    def test_record_transformation(self):
        tracker = DataFrameLineageTracker()
        parent = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
        tracker.register_df(parent, source="input")

        child = parent.dropna()  # won't be auto-tracked without hooks
        child_id = tracker.record_transformation(
            operation="dropna",
            parent_df=parent,
            result_df=child,
            params={'how': 'any'}
        )

        assert child_id is not None
        assert len(tracker.transformations) == 1
        t = tracker.transformations[0]
        assert t.operation == "dropna"
        assert t.input_shape == (3, 2)
        assert t.output_shape == (3, 2)

    def test_column_change_tracking(self):
        tracker = DataFrameLineageTracker()
        parent = pd.DataFrame({'a': [1], 'b': [2], 'c': [3]})
        tracker.register_df(parent)

        # Simulate column selection
        child = parent[['a', 'b']]
        tracker.record_transformation(
            operation="select_columns",
            parent_df=parent,
            result_df=child,
        )

        t = tracker.transformations[0]
        assert t.columns_removed == ['c']
        assert t.columns_added is None or t.columns_added == []

    def test_row_change_tracking(self):
        tracker = DataFrameLineageTracker()
        parent = pd.DataFrame({'a': [1, 2, 3, None]})
        tracker.register_df(parent)

        child = parent.dropna()
        tracker.record_transformation(
            operation="dropna",
            parent_df=parent,
            result_df=child,
        )

        t = tracker.transformations[0]
        assert t.rows_before == 4
        assert t.rows_after == 3

    def test_merge_tracking(self):
        tracker = DataFrameLineageTracker()
        left = pd.DataFrame({'key': [1, 2], 'val_l': ['a', 'b']})
        right = pd.DataFrame({'key': [1, 2], 'val_r': ['x', 'y']})
        tracker.register_df(left, source="left")
        tracker.register_df(right, source="right")

        result = pd.merge(left, right, on='key')
        tracker.record_transformation(
            operation="merge",
            parent_df=left,
            result_df=result,
            extra_parents=[right],
            params={'on': 'key', 'how': 'inner'}
        )

        t = tracker.transformations[0]
        assert len(t.parent_ids) == 2
        assert t.operation == "merge"

    def test_lineage_chain(self):
        tracker = DataFrameLineageTracker()
        df1 = pd.DataFrame({'a': [1, 2, None]})
        tracker.register_df(df1, source="raw")

        df2 = df1.dropna()
        id2 = tracker.record_transformation("dropna", df1, df2)

        df3 = df2.rename(columns={'a': 'value'})
        id3 = tracker.record_transformation("rename", df2, df3)

        chain = tracker.get_lineage_chain(id3)
        assert len(chain) == 2
        assert chain[0].operation == "dropna"
        assert chain[1].operation == "rename"

    def test_summary(self):
        tracker = DataFrameLineageTracker()
        df = pd.DataFrame({'a': [1, 2, None], 'b': [4, 5, 6]})
        tracker.register_df(df)

        df2 = df.dropna()
        tracker.record_transformation("dropna", df, df2)

        df3 = df2.rename(columns={'a': 'x'})
        tracker.record_transformation("rename", df2, df3)

        s = tracker.get_summary()
        assert s['total_transformations'] == 2
        assert s['operation_counts']['dropna'] == 1
        assert s['operation_counts']['rename'] == 1
        assert s['total_rows_filtered'] == 1

    def test_content_hash_changes(self):
        tracker = DataFrameLineageTracker()
        df1 = pd.DataFrame({'a': [1, 2, 3]})
        lid1 = tracker.register_df(df1)

        df2 = pd.DataFrame({'a': [4, 5, 6]})
        lid2 = tracker.register_df(df2)

        hash1 = tracker.nodes[lid1]['content_hash']
        hash2 = tracker.nodes[lid2]['content_hash']
        assert hash1 != hash2

    def test_full_graph_export(self):
        tracker = DataFrameLineageTracker()
        df = pd.DataFrame({'a': [1]})
        tracker.register_df(df, filepath="/test.csv")

        graph = tracker.get_full_graph()
        assert 'nodes' in graph
        assert 'edges' in graph
        assert 'file_mappings' in graph
        assert len(graph['nodes']) == 1


class TestTransformHooksIntegration:
    """
    Test that transform hooks actually fire when using pandas normally.
    These tests require hooks to be installed.
    """

    @pytest.fixture(autouse=True)
    def install_hooks(self):
        """Install transform hooks for these tests."""
        from autolineage.transform_hooks import install_transform_hooks, uninstall_transform_hooks
        reset_df_tracker()
        install_transform_hooks()
        yield
        uninstall_transform_hooks()
        reset_df_tracker()

    def test_dropna_auto_tracked(self):
        df = pd.DataFrame({'a': [1, None, 3]})
        get_df_tracker().register_df(df, source="test")

        result = df.dropna()

        dt = get_df_tracker()
        assert len(dt.transformations) >= 1
        ops = [t.operation for t in dt.transformations]
        assert 'dropna' in ops

    def test_fillna_auto_tracked(self):
        df = pd.DataFrame({'a': [1, None, 3]})
        get_df_tracker().register_df(df, source="test")

        result = df.fillna(0)

        dt = get_df_tracker()
        ops = [t.operation for t in dt.transformations]
        assert 'fillna' in ops

    def test_rename_auto_tracked(self):
        df = pd.DataFrame({'a': [1], 'b': [2]})
        get_df_tracker().register_df(df, source="test")

        result = df.rename(columns={'a': 'x'})

        dt = get_df_tracker()
        ops = [t.operation for t in dt.transformations]
        assert 'rename' in ops
        # Check column-level tracking
        rename_t = [t for t in dt.transformations if t.operation == 'rename'][0]
        assert 'a' in rename_t.columns_removed
        assert 'x' in rename_t.columns_added

    def test_merge_auto_tracked(self):
        left = pd.DataFrame({'key': [1, 2], 'a': [10, 20]})
        right = pd.DataFrame({'key': [1, 2], 'b': [30, 40]})
        get_df_tracker().register_df(left, source="left")
        get_df_tracker().register_df(right, source="right")

        result = left.merge(right, on='key')

        dt = get_df_tracker()
        merge_t = [t for t in dt.transformations if t.operation == 'merge']
        assert len(merge_t) >= 1
        assert len(merge_t[0].parent_ids) == 2  # Both inputs tracked

    def test_concat_auto_tracked(self):
        df1 = pd.DataFrame({'a': [1, 2]})
        df2 = pd.DataFrame({'a': [3, 4]})
        get_df_tracker().register_df(df1, source="part1")
        get_df_tracker().register_df(df2, source="part2")

        result = pd.concat([df1, df2])

        dt = get_df_tracker()
        concat_t = [t for t in dt.transformations if t.operation == 'concat']
        assert len(concat_t) >= 1
        assert len(concat_t[0].parent_ids) == 2

    def test_groupby_sum_auto_tracked(self):
        df = pd.DataFrame({'key': ['a', 'b', 'a'], 'val': [1, 2, 3]})
        get_df_tracker().register_df(df, source="test")

        result = df.groupby('key')['val'].sum()

        dt = get_df_tracker()
        ops = [t.operation for t in dt.transformations]
        assert 'groupby.sum' in ops

    def test_boolean_filter_auto_tracked(self):
        df = pd.DataFrame({'a': [10, 20, 30]})
        get_df_tracker().register_df(df, source="test")

        result = df[df['a'] > 15]

        dt = get_df_tracker()
        filter_t = [t for t in dt.transformations if t.operation == 'filter']
        assert len(filter_t) >= 1
        assert filter_t[0].rows_before == 3
        assert filter_t[0].rows_after == 2

    def test_column_select_auto_tracked(self):
        df = pd.DataFrame({'a': [1], 'b': [2], 'c': [3]})
        get_df_tracker().register_df(df, source="test")

        result = df[['a', 'b']]

        dt = get_df_tracker()
        select_t = [t for t in dt.transformations if t.operation == 'select_columns']
        assert len(select_t) >= 1
        assert 'c' in select_t[0].columns_removed

    def test_assign_auto_tracked(self):
        df = pd.DataFrame({'a': [1, 2]})
        get_df_tracker().register_df(df, source="test")

        result = df.assign(b=lambda x: x['a'] * 2)

        dt = get_df_tracker()
        assign_t = [t for t in dt.transformations if t.operation == 'assign']
        assert len(assign_t) >= 1
        assert 'b' in assign_t[0].columns_added

    def test_chained_operations(self):
        """Test that a chain of operations creates a proper lineage."""
        df = pd.DataFrame({
            'a': [1, None, 3, 4],
            'b': [10, 20, 30, 40],
            'c': ['x', 'y', 'x', 'y']
        })
        get_df_tracker().register_df(df, source="raw")

        result = (
            df
            .dropna()
            .rename(columns={'a': 'value'})
            .sort_values('value')
        )

        dt = get_df_tracker()
        ops = [t.operation for t in dt.transformations]
        assert 'dropna' in ops
        assert 'rename' in ops
        assert 'sort_values' in ops
        assert len(dt.transformations) >= 3

    def test_query_auto_tracked(self):
        df = pd.DataFrame({'a': [1, 2, 3, 4, 5]})
        get_df_tracker().register_df(df, source="test")

        result = df.query('a > 3')

        dt = get_df_tracker()
        ops = [t.operation for t in dt.transformations]
        assert 'query' in ops

    def test_drop_duplicates_auto_tracked(self):
        df = pd.DataFrame({'a': [1, 1, 2, 2]})
        get_df_tracker().register_df(df, source="test")

        result = df.drop_duplicates()

        dt = get_df_tracker()
        ops = [t.operation for t in dt.transformations]
        assert 'drop_duplicates' in ops
