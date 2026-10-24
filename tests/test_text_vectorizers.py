"""CountVectorizer and TfidfVectorizer calls are recorded at the user's line.

On the email-sorting development script these fit_transform and transform
calls were pipeline lines with no record. TfidfVectorizer implements them
by calling CountVectorizer, and CountVectorizer.fit calls fit_transform, so
only the method the user wrote is recorded.
"""

import inspect

import pytest

sklearn = pytest.importorskip("sklearn")

from autolineage.core.tracker import UnifiedTracker  # noqa: E402
from autolineage.hooks.registry import HookRegistry  # noqa: E402

_DOCS = ["a cat sat", "a dog ran", "a cat and a dog"]


def _ops(tracker, category):
    return [(r.operation, r.metadata.get("source_line"))
            for r in tracker.records if r.category == category]


@pytest.fixture
def hooked():
    tracker = UnifiedTracker()
    registry = HookRegistry()
    registry.install_all(tracker)
    try:
        yield tracker
    finally:
        registry.uninstall_all()


def test_count_vectorizer_records_fit_transform_and_transform(hooked):
    from sklearn.feature_extraction.text import CountVectorizer
    vec = CountVectorizer()
    fit_line = inspect.currentframe().f_lineno + 1
    fitted = vec.fit_transform(_DOCS)
    transform_line = inspect.currentframe().f_lineno + 1
    transformed = vec.transform(["a cat"])
    assert _ops(hooked, "preprocess") == [
        ("CountVectorizer.fit_transform", fit_line),
        ("CountVectorizer.transform", transform_line),
    ]
    fit_rec = next(r for r in hooked.records if r.operation == "CountVectorizer.fit_transform")
    assert fit_rec.output_shape == tuple(fitted.shape)
    assert fit_rec.rows_after == fitted.shape[0]
    assert transformed.shape[1] == fitted.shape[1]


def test_tfidf_does_not_record_the_count_vectorizer_it_calls(hooked):
    from sklearn.feature_extraction.text import TfidfVectorizer
    vec = TfidfVectorizer()
    fit_line = inspect.currentframe().f_lineno + 1
    vec.fit_transform(_DOCS)
    transform_line = inspect.currentframe().f_lineno + 1
    vec.transform(["a cat"])
    assert _ops(hooked, "preprocess") == [
        ("TfidfVectorizer.fit_transform", fit_line),
        ("TfidfVectorizer.transform", transform_line),
    ]


def test_fit_does_not_also_record_fit_transform(hooked):
    from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
    CountVectorizer().fit(_DOCS)
    TfidfVectorizer().fit(_DOCS)
    assert [op for op, _ in _ops(hooked, "preprocess")] == [
        "CountVectorizer.fit",
        "TfidfVectorizer.fit",
    ]


def test_constructor_records_params_and_clone_still_works(hooked):
    from sklearn.base import clone
    from sklearn.feature_extraction.text import TfidfVectorizer
    line = inspect.currentframe().f_lineno + 1
    vec = TfidfVectorizer(max_features=10, ngram_range=(1, 2))
    copy = clone(vec)
    configure = [r for r in hooked.records if r.category == "configure"]
    assert [r.operation for r in configure] == ["TfidfVectorizer.__init__"]
    assert configure[0].metadata["source_line"] == line
    assert configure[0].parameters["max_features"] == 10
    assert copy.get_params()["max_features"] == 10
    assert copy.get_params()["ngram_range"] == (1, 2)
