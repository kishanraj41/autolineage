"""Scikit-learn hook provider. Hooks the complete ML lifecycle."""

import sys
from functools import wraps
from typing import Dict, Any, List, Optional
from . import BaseHookProvider, _is_library_frame

_METRIC_FUNCTIONS = [
    'accuracy_score', 'balanced_accuracy_score',
    'f1_score', 'precision_score', 'recall_score',
    'roc_auc_score', 'average_precision_score',
    'log_loss', 'brier_score_loss',
    'mean_squared_error', 'mean_absolute_error',
    'r2_score', 'explained_variance_score',
    'mean_absolute_percentage_error', 'median_absolute_error', 'max_error',
    # Returns a report string, not a float. Hooked so the LabelEncoder
    # calls inside it are not recorded as their own operations.
    'classification_report',
]

_COMPOSITE_CLASSES = frozenset({'Pipeline', 'ColumnTransformer'})

_SEARCH_CLASSES = ('GridSearchCV', 'RandomizedSearchCV')

_ESTIMATOR_MODULES = [
    ('sklearn.ensemble', [
        'RandomForestClassifier', 'RandomForestRegressor',
        'GradientBoostingClassifier', 'GradientBoostingRegressor',
        'AdaBoostClassifier', 'AdaBoostRegressor',
        'BaggingClassifier', 'BaggingRegressor',
        'ExtraTreesClassifier', 'ExtraTreesRegressor',
        'HistGradientBoostingClassifier', 'HistGradientBoostingRegressor',
    ]),
    ('sklearn.linear_model', [
        'LinearRegression', 'LogisticRegression', 'Ridge', 'Lasso',
        'ElasticNet', 'SGDClassifier', 'SGDRegressor',
    ]),
    ('sklearn.tree', ['DecisionTreeClassifier', 'DecisionTreeRegressor']),
    ('sklearn.svm', ['SVC', 'SVR', 'LinearSVC', 'LinearSVR']),
    ('sklearn.neighbors', ['KNeighborsClassifier', 'KNeighborsRegressor']),
    ('sklearn.naive_bayes', ['GaussianNB', 'MultinomialNB', 'BernoulliNB']),
]

_PREPROCESSOR_CLASSES = [
    ('sklearn.preprocessing', 'StandardScaler'),
    ('sklearn.preprocessing', 'MinMaxScaler'),
    ('sklearn.preprocessing', 'RobustScaler'),
    ('sklearn.preprocessing', 'MaxAbsScaler'),
    ('sklearn.preprocessing', 'Normalizer'),
    ('sklearn.preprocessing', 'LabelEncoder'),
    ('sklearn.preprocessing', 'OneHotEncoder'),
    ('sklearn.preprocessing', 'OrdinalEncoder'),
    ('sklearn.preprocessing', 'LabelBinarizer'),
    ('sklearn.preprocessing', 'Binarizer'),
    ('sklearn.preprocessing', 'PolynomialFeatures'),
    ('sklearn.preprocessing', 'FunctionTransformer'),
    ('sklearn.impute', 'SimpleImputer'),
    ('sklearn.compose', 'ColumnTransformer'),
    ('sklearn.pipeline', 'Pipeline'),
    ('sklearn.feature_selection', 'SelectKBest'),
    ('sklearn.feature_selection', 'VarianceThreshold'),
    ('sklearn.decomposition', 'PCA'),
    ('sklearn.feature_extraction.text', 'CountVectorizer'),
    ('sklearn.feature_extraction.text', 'TfidfVectorizer'),
]


class SklearnHooks(BaseHookProvider):
    name = "sklearn"
    required_package = "sklearn"

    def __init__(self):
        super().__init__()
        # ``_estimator_depth`` counts plain estimators currently on the
        # stack. Their internals (a tree inside a forest, a LabelEncoder
        # inside a metric) are not recorded. Composites (Pipeline,
        # ColumnTransformer) do not increment it, so their direct steps
        # are recorded. ``_suppress`` is set for the body of a search fit
        # so cross-validation folds stay out of the graph.
        self._hook_depth = 0
        self._estimator_depth = 0
        self._suppress = False

    def _enter(self, *, composite: bool = False) -> bool:
        """Return True when this call should be recorded.

        The caller must invoke ``_exit(composite=...)`` on the same path.
        """
        if self._suppress or self._estimator_depth >= 1:
            return False
        self._hook_depth += 1
        if not composite:
            self._estimator_depth += 1
        return True

    def _exit(self, *, composite: bool = False) -> None:
        self._hook_depth = max(0, self._hook_depth - 1)
        if not composite:
            self._estimator_depth = max(0, self._estimator_depth - 1)

    def install(self, tracker) -> int:
        self._tracker = tracker
        count = 0
        count += self._hook_train_test_split()
        count += self._hook_estimator_methods()
        count += self._hook_preprocessor_methods()
        count += self._hook_search()
        count += self._hook_metrics()
        count += self._hook_constructors()
        return count

    def uninstall(self) -> None:
        import importlib
        for key, orig in self._originals.items():
            try:
                module_path, attr = key.rsplit('.', 1)
                try:
                    owner = importlib.import_module(module_path)
                except Exception:
                    # Class method key: ``sklearn.ensemble.RandomForestClassifier.fit``
                    mod_path, class_name = module_path.rsplit('.', 1)
                    owner = getattr(importlib.import_module(mod_path), class_name)
                setattr(owner, attr, orig)
            except Exception:
                pass
        self._originals.clear()

    # --- train_test_split ---

    def _hook_train_test_split(self) -> int:
        try:
            import sklearn.model_selection as ms
        except ImportError:
            return 0

        orig = self._save_original(ms, 'train_test_split')
        provider = self

        @wraps(orig)
        def hooked(*arrays, **kwargs):
            result, duration = provider._timed(orig, *arrays, **kwargs)
            params = provider._safe_params({
                'test_size': kwargs.get('test_size'),
                'train_size': kwargs.get('train_size'),
                'random_state': kwargs.get('random_state'),
                'stratify': kwargs.get('stratify') is not None,
            })
            parent_ids = [provider._get_or_assign(a, source="split_input") for a in arrays]
            train_size = result[0].shape[0] if len(result) >= 2 and hasattr(result[0], 'shape') else None
            test_size = result[1].shape[0] if len(result) >= 2 and hasattr(result[1], 'shape') else None
            labels = ['train', 'test'] * (len(result) // 2)
            child_ids = [provider._get_or_assign(a, source=f"split_{l}") for a, l in zip(result, labels)]
            rec = provider._make_record(
                category="split", operation="train_test_split",
                parent_ids=parent_ids, child_id=child_ids[0] if child_ids else "",
                parameters=params,
                input_shape=tuple(arrays[0].shape) if hasattr(arrays[0], 'shape') else None,
                rows_before=arrays[0].shape[0] if hasattr(arrays[0], 'shape') else None,
                rows_after=train_size, duration_ms=duration,
                metadata={'train_size': train_size, 'test_size': test_size})
            provider._emit(rec)
            return result

        ms.train_test_split = hooked
        return 1

    # --- Estimator fit/predict/score ---

    def _hook_estimator_methods(self) -> int:
        import importlib
        count = 0
        for module_path, class_names in _ESTIMATOR_MODULES:
            try:
                mod = importlib.import_module(module_path)
            except ImportError:
                continue
            for class_name in class_names:
                cls = getattr(mod, class_name, None)
                if cls is None:
                    continue
                for method_name in ['fit', 'predict', 'predict_proba', 'score']:
                    if not hasattr(cls, method_name):
                        continue
                    key = f"{module_path}.{class_name}.{method_name}"
                    if key in self._originals:
                        continue
                    orig = getattr(cls, method_name)
                    self._originals[key] = orig
                    if method_name == 'fit':
                        setattr(cls, method_name, self._make_fit_hook(class_name, orig))
                    elif method_name == 'predict':
                        setattr(cls, method_name, self._make_predict_hook(class_name, orig, proba=False))
                    elif method_name == 'predict_proba':
                        setattr(cls, method_name, self._make_predict_hook(class_name, orig, proba=True))
                    elif method_name == 'score':
                        setattr(cls, method_name, self._make_score_hook(class_name, orig))
                    count += 1
        return count

    def _make_fit_hook(self, class_name, orig_fn):
        provider = self

        @wraps(orig_fn)
        def hooked(self_est, X, y=None, **kwargs):
            if not provider._enter():
                return orig_fn(self_est, X, y, **kwargs)
            try:
                result, duration = provider._timed(orig_fn, self_est, X, y, **kwargs)
            finally:
                provider._exit()

            params = {}
            try:
                params = provider._safe_params(self_est.get_params(deep=False))
            except Exception:
                pass
            parent_ids = []
            if X is not None:
                parent_ids.append(provider._get_or_assign(X, source="train_X"))
            if y is not None:
                parent_ids.append(provider._get_or_assign(y, source="train_y"))
            est_lid = provider._get_or_assign(self_est, source=f"{class_name}.fit")
            rec = provider._make_record(
                category="train", operation=f"{class_name}.fit",
                parent_ids=parent_ids, child_id=est_lid,
                parameters=params,
                input_shape=tuple(X.shape) if hasattr(X, 'shape') else None,
                rows_before=X.shape[0] if hasattr(X, 'shape') else None,
                duration_ms=duration,
                metadata={'estimator_type': type(self_est).__name__,
                          'n_features': X.shape[1] if hasattr(X, 'shape') and len(X.shape) > 1 else None})
            provider._emit(rec)
            return result
        return hooked

    def _make_predict_hook(self, class_name, orig_fn, proba=False):
        provider = self
        suffix = "predict_proba" if proba else "predict"

        @wraps(orig_fn)
        def hooked(self_est, X, **kwargs):
            # Nested predicts (each tree inside a forest) are not recorded.
            # A classifier called by a Pipeline still is: the pipeline is a
            # composite and does not set ``_estimator_depth``.
            if not provider._enter():
                return orig_fn(self_est, X, **kwargs)
            try:
                result, duration = provider._timed(orig_fn, self_est, X, **kwargs)
            finally:
                provider._exit()

            parent_ids = [provider._get_or_assign(X, source="predict_input")]
            est_lid = provider._get_id(self_est)
            if est_lid:
                parent_ids.append(est_lid)
            child_lid = provider._get_or_assign(result, source=f"{class_name}.{suffix}")
            rec = provider._make_record(
                category="predict", operation=f"{class_name}.{suffix}",
                parent_ids=parent_ids, child_id=child_lid,
                input_shape=tuple(X.shape) if hasattr(X, 'shape') else None,
                output_shape=tuple(result.shape) if hasattr(result, 'shape') else (len(result),),
                rows_before=X.shape[0] if hasattr(X, 'shape') else None,
                rows_after=result.shape[0] if hasattr(result, 'shape') else len(result),
                duration_ms=duration, metadata={'is_proba': proba})
            provider._emit(rec)
            return result
        return hooked

    def _make_score_hook(self, class_name, orig_fn):
        provider = self

        @wraps(orig_fn)
        def hooked(self_est, X, y, **kwargs):
            if not provider._enter():
                return orig_fn(self_est, X, y, **kwargs)
            try:
                result, duration = provider._timed(orig_fn, self_est, X, y, **kwargs)
            finally:
                provider._exit()
            rec = provider._make_record(
                category="evaluate", operation=f"{class_name}.score",
                parameters={'score_value': float(result)},
                input_shape=tuple(X.shape) if hasattr(X, 'shape') else None,
                rows_before=X.shape[0] if hasattr(X, 'shape') else None,
                duration_ms=duration, metadata={'score': float(result)})
            provider._emit(rec)
            return result
        return hooked

    # --- Preprocessor fit/transform ---

    def _hook_preprocessor_methods(self) -> int:
        import importlib
        count = 0
        for module_path, class_name in _PREPROCESSOR_CLASSES:
            try:
                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name, None)
            except (ImportError, AttributeError):
                continue
            if cls is None:
                continue
            for method_name in ['fit', 'transform', 'fit_transform']:
                if not hasattr(cls, method_name):
                    continue
                key = f"{module_path}.{class_name}.{method_name}"
                if key in self._originals:
                    continue
                orig = getattr(cls, method_name)
                self._originals[key] = orig
                if method_name == 'fit':
                    setattr(cls, method_name, self._make_preprocess_fit_hook(class_name, orig))
                else:
                    setattr(cls, method_name, self._make_preprocess_transform_hook(class_name, method_name, orig))
                count += 1
        return count

    def _make_preprocess_fit_hook(self, class_name, orig_fn):
        provider = self
        composite = class_name in _COMPOSITE_CLASSES

        @wraps(orig_fn)
        def hooked(self_t, X, y=None, **kwargs):
            if not provider._enter(composite=composite):
                return orig_fn(self_t, X, y, **kwargs) if y is not None else orig_fn(self_t, X, **kwargs)
            try:
                if y is not None:
                    result, duration = provider._timed(orig_fn, self_t, X, y, **kwargs)
                else:
                    result, duration = provider._timed(orig_fn, self_t, X, **kwargs)
            finally:
                provider._exit(composite=composite)

            parent_lid = provider._get_or_assign(X, source="preprocess_input")
            est_lid = provider._get_or_assign(self_t, source=f"{class_name}.fit")
            rec = provider._make_record(
                category="preprocess", operation=f"{class_name}.fit",
                parent_ids=[parent_lid], child_id=est_lid,
                input_shape=tuple(X.shape) if hasattr(X, 'shape') else None,
                rows_before=X.shape[0] if hasattr(X, 'shape') else None,
                duration_ms=duration)
            provider._emit(rec)
            return result
        return hooked

    def _make_preprocess_transform_hook(self, class_name, method_name, orig_fn):
        provider = self
        composite = class_name in _COMPOSITE_CLASSES

        @wraps(orig_fn)
        def hooked(self_t, X, y=None, **kwargs):
            if not provider._enter(composite=composite):
                return orig_fn(self_t, X, y, **kwargs) if y is not None else orig_fn(self_t, X, **kwargs)
            try:
                if y is not None:
                    result, duration = provider._timed(orig_fn, self_t, X, y, **kwargs)
                else:
                    result, duration = provider._timed(orig_fn, self_t, X, **kwargs)
            finally:
                provider._exit(composite=composite)

            parent_lid = provider._get_or_assign(X, source="transform_input")
            child_lid = provider._get_or_assign(result, source=f"{class_name}.{method_name}")
            added, removed = None, None
            if hasattr(X, 'columns') and hasattr(result, 'columns'):
                added, removed = provider._col_diff(X.columns, result.columns)
            rec = provider._make_record(
                category="preprocess", operation=f"{class_name}.{method_name}",
                parent_ids=[parent_lid], child_id=child_lid,
                input_shape=tuple(X.shape) if hasattr(X, 'shape') else None,
                output_shape=tuple(result.shape) if hasattr(result, 'shape') else None,
                columns_added=added, columns_removed=removed,
                rows_before=X.shape[0] if hasattr(X, 'shape') else None,
                rows_after=result.shape[0] if hasattr(result, 'shape') else None,
                duration_ms=duration)
            provider._emit(rec)
            return result
        return hooked

    # --- Parameter search ---

    def _hook_search(self) -> int:
        try:
            import sklearn.model_selection as ms
        except ImportError:
            return 0
        count = 0
        for class_name in _SEARCH_CLASSES:
            cls = getattr(ms, class_name, None)
            if cls is None or not hasattr(cls, 'fit'):
                continue
            key = f"sklearn.model_selection.{class_name}.fit"
            if key in self._originals:
                continue
            orig = getattr(cls, 'fit')
            self._originals[key] = orig
            setattr(cls, 'fit', self._make_search_fit_hook(class_name, orig))
            count += 1
        return count

    def _make_search_fit_hook(self, class_name, orig_fn):
        provider = self

        @wraps(orig_fn)
        def hooked(self_search, X, y=None, **kwargs):
            if provider._suppress or provider._estimator_depth >= 1:
                return orig_fn(self_search, X, y, **kwargs)
            provider._suppress = True
            try:
                result, duration = provider._timed(orig_fn, self_search, X, y, **kwargs)
            finally:
                provider._suppress = False

            best_score = getattr(self_search, 'best_score_', None)
            try:
                best_score = float(best_score) if best_score is not None else None
            except (TypeError, ValueError):
                best_score = None
            params = provider._safe_params({
                'best_params': getattr(self_search, 'best_params_', None),
                'best_score': best_score,
                'scoring': getattr(self_search, 'scoring', None),
                'cv': kwargs.get('cv', getattr(self_search, 'cv', None)),
            })
            parent_ids = []
            if X is not None:
                parent_ids.append(provider._get_or_assign(X, source="search_X"))
            if y is not None:
                parent_ids.append(provider._get_or_assign(y, source="search_y"))
            est_lid = provider._get_or_assign(self_search, source=f"{class_name}.fit")
            rec = provider._make_record(
                category="train", operation=f"{class_name}.fit",
                parent_ids=parent_ids, child_id=est_lid,
                parameters=params,
                input_shape=tuple(X.shape) if hasattr(X, 'shape') else None,
                rows_before=X.shape[0] if hasattr(X, 'shape') else None,
                duration_ms=duration,
                metadata={'best_score': best_score,
                          'best_params': params.get('best_params')})
            provider._emit(rec)
            return result
        return hooked

    # --- Construction (estimator configuration) ---

    def _hook_constructors(self) -> int:
        """Record each estimator or preprocessor the user constructs.

        One ``configure`` record per constructor call made from user code,
        with ``get_params(deep=False)`` and the caller's line. Constructions
        made by scikit-learn itself (``clone`` inside a search, the trees of
        a forest) are skipped: the frame that called ``__init__`` is checked,
        and only a non-library frame produces a record. Classes that do not
        define their own ``__init__`` (LabelEncoder) are left alone, because
        scikit-learn reads parameter names from ``cls.__init__``.
        """
        import importlib
        targets = []
        for module_path, class_names in _ESTIMATOR_MODULES:
            targets.extend((module_path, name) for name in class_names)
        targets.extend(_PREPROCESSOR_CLASSES)
        targets.extend(('sklearn.model_selection', name) for name in _SEARCH_CLASSES)

        count = 0
        for module_path, class_name in targets:
            try:
                cls = getattr(importlib.import_module(module_path), class_name, None)
            except ImportError:
                continue
            if cls is None or '__init__' not in cls.__dict__:
                continue
            key = f"{module_path}.{class_name}.__init__"
            if key in self._originals:
                continue
            orig = cls.__dict__['__init__']
            self._originals[key] = orig
            setattr(cls, '__init__', self._make_init_hook(class_name, orig))
            count += 1
        return count

    def _make_init_hook(self, class_name, orig_fn):
        provider = self

        @wraps(orig_fn)
        def hooked(self_est, *args, **kwargs):
            orig_fn(self_est, *args, **kwargs)
            # Only the class the user named is recorded: a subclass calling
            # super().__init__ would otherwise add a second record.
            if type(self_est).__name__ != class_name:
                return None
            if provider._suppress or provider._estimator_depth >= 1:
                return None
            try:
                caller = sys._getframe(1).f_code.co_filename
            except ValueError:
                return None
            if _is_library_frame(caller):
                return None
            params = {}
            try:
                params = provider._safe_params(self_est.get_params(deep=False))
            except Exception:
                pass
            rec = provider._make_record(
                category="configure", operation=f"{class_name}.__init__",
                parameters=params,
                metadata={'estimator_type': class_name})
            provider._emit(rec)
            return None
        return hooked

    # --- Metrics ---

    def _hook_metrics(self) -> int:
        try:
            import sklearn.metrics
        except ImportError:
            return 0

        count = 0
        provider = self

        for func_name in _METRIC_FUNCTIONS:
            if not hasattr(sklearn.metrics, func_name):
                continue
            key = f"sklearn.metrics.{func_name}"
            if key in self._originals:
                continue
            orig = getattr(sklearn.metrics, func_name)
            self._originals[key] = orig

            def make_hook(fn_name, orig_fn):
                @wraps(orig_fn)
                def hooked(y_true, y_pred, *args, **kwargs):
                    # Recording this call sets estimator depth so a
                    # LabelEncoder used inside the metric is not its own node.
                    if not provider._enter():
                        return orig_fn(y_true, y_pred, *args, **kwargs)
                    try:
                        result, duration = provider._timed(
                            orig_fn, y_true, y_pred, *args, **kwargs)
                    finally:
                        provider._exit()
                    numeric = result if isinstance(result, (int, float)) else None
                    if numeric is None:
                        try:
                            import numpy as np
                            if isinstance(result, np.floating):
                                numeric = float(result)
                        except Exception:
                            numeric = None
                    rec = provider._make_record(
                        category="evaluate", operation=fn_name,
                        parameters=provider._safe_params({
                            'metric': fn_name,
                            'value': numeric if numeric is not None else str(result)[:100],
                        }),
                        rows_before=len(y_true) if hasattr(y_true, '__len__') else None,
                        duration_ms=duration,
                        metadata={'metric_name': fn_name,
                                  'metric_value': numeric})
                    provider._emit(rec)
                    return result
                return hooked

            setattr(sklearn.metrics, func_name, make_hook(func_name, orig))
            count += 1

        # Early-bound imports (`from sklearn.metrics import f1_score` before
        # the hooks are installed) are detected and rebound by
        # HookRegistry._handle_early_imports once every provider is installed.
        return count
