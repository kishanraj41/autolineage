"""Scikit-learn hook provider. Hooks the complete ML lifecycle."""

from functools import wraps
from typing import Dict, Any, List, Optional
from . import BaseHookProvider

_METRIC_FUNCTIONS = [
    'accuracy_score', 'balanced_accuracy_score',
    'f1_score', 'precision_score', 'recall_score',
    'roc_auc_score', 'average_precision_score',
    'log_loss', 'brier_score_loss',
    'mean_squared_error', 'mean_absolute_error',
    'r2_score', 'explained_variance_score',
    'mean_absolute_percentage_error', 'median_absolute_error', 'max_error',
]

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
]


class SklearnHooks(BaseHookProvider):
    name = "sklearn"
    required_package = "sklearn"

    def __init__(self):
        super().__init__()
        # Depth counter: track at depth 0 (user) and 1 (Pipeline internals).
        # Skip depth >= 2 (e.g. DecisionTree inside RandomForest).
        self._hook_depth = 0

    def install(self, tracker) -> int:
        self._tracker = tracker
        count = 0
        count += self._hook_train_test_split()
        count += self._hook_estimator_methods()
        count += self._hook_preprocessor_methods()
        count += self._hook_metrics()
        return count

    def uninstall(self) -> None:
        import importlib
        for key, orig in self._originals.items():
            try:
                parts = key.rsplit('.', 1)
                if len(parts) == 2:
                    mod = importlib.import_module(parts[0])
                    setattr(mod, parts[1], orig)
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
            if provider._hook_depth >= 1:
                return orig_fn(self_est, X, y, **kwargs)
            provider._hook_depth += 1
            try:
                result, duration = provider._timed(orig_fn, self_est, X, y, **kwargs)
            finally:
                provider._hook_depth -= 1

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
            # Predict hooks use stricter guard: depth >= 1 blocks nested predicts.
            # This prevents RandomForest.predict from recording all N inner
            # DecisionTree.predict_proba calls. User-level predict is depth 0.
            if provider._hook_depth >= 1:
                return orig_fn(self_est, X, **kwargs)
            provider._hook_depth += 1
            try:
                result, duration = provider._timed(orig_fn, self_est, X, **kwargs)
            finally:
                provider._hook_depth -= 1

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
            if provider._hook_depth >= 1:
                return orig_fn(self_est, X, y, **kwargs)
            provider._hook_depth += 1
            try:
                result, duration = provider._timed(orig_fn, self_est, X, y, **kwargs)
            finally:
                provider._hook_depth -= 1
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

        @wraps(orig_fn)
        def hooked(self_t, X, y=None, **kwargs):
            if provider._hook_depth >= 1:
                return orig_fn(self_t, X, y, **kwargs) if y is not None else orig_fn(self_t, X, **kwargs)
            provider._hook_depth += 1
            try:
                if y is not None:
                    result, duration = provider._timed(orig_fn, self_t, X, y, **kwargs)
                else:
                    result, duration = provider._timed(orig_fn, self_t, X, **kwargs)
            finally:
                provider._hook_depth -= 1

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

        @wraps(orig_fn)
        def hooked(self_t, X, y=None, **kwargs):
            if provider._hook_depth >= 1:
                return orig_fn(self_t, X, y, **kwargs) if y is not None else orig_fn(self_t, X, **kwargs)
            provider._hook_depth += 1
            try:
                if y is not None:
                    result, duration = provider._timed(orig_fn, self_t, X, y, **kwargs)
                else:
                    result, duration = provider._timed(orig_fn, self_t, X, **kwargs)
            finally:
                provider._hook_depth -= 1

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
                    # Block internal LabelEncoder calls triggered by metrics
                    if provider._hook_depth >= 1:
                        return orig_fn(y_true, y_pred, *args, **kwargs)
                    provider._hook_depth += 1
                    try:
                        result, duration = provider._timed(
                            orig_fn, y_true, y_pred, *args, **kwargs)
                    finally:
                        provider._hook_depth -= 1
                    rec = provider._make_record(
                        category="evaluate", operation=fn_name,
                        parameters=provider._safe_params({
                            'metric': fn_name,
                            'value': float(result) if isinstance(result, (int, float)) else str(result)[:100],
                        }),
                        rows_before=len(y_true) if hasattr(y_true, '__len__') else None,
                        duration_ms=duration,
                        metadata={'metric_name': fn_name,
                                  'metric_value': float(result) if isinstance(result, (int, float)) else None})
                    provider._emit(rec)
                    return result
                return hooked

            setattr(sklearn.metrics, func_name, make_hook(func_name, orig))
            count += 1

        # Defensive check: warn if a sklearn metric has already been imported
        # into a user namespace before hooks were installed. Such early-bound
        # references will bypass our wrappers and silently produce no
        # [evaluate] lineage records, which is one of the most common
        # debugging traps for new users.
        self._warn_about_early_metric_imports(sklearn.metrics)
        return count

    @staticmethod
    def _warn_about_early_metric_imports(metrics_module) -> None:
        """Detect metrics imported into __main__ before install_all().

        When a user writes `from sklearn.metrics import f1_score` at the
        top of their script and calls install_all() afterwards, the local
        `f1_score` name still points at the original (unhooked) function.
        Calling that local name will compute the metric correctly but
        will NOT produce a lineage record. We surface a one-line warning
        so the user can either reorder imports or use the
        `import autolineage.auto` shortcut, which guarantees hooks are
        installed before any sklearn import in their own code.
        """
        import sys
        import warnings

        main = sys.modules.get('__main__')
        if main is None:
            return

        # Build a lookup of original function id() -> name so we can
        # detect references that point at the unwrapped function.
        # The originals are stored as __wrapped__ on the new functions.
        unwrapped_ids = {}
        for fn_name in _METRIC_FUNCTIONS:
            current = getattr(metrics_module, fn_name, None)
            if current is None:
                continue
            unwrapped = getattr(current, '__wrapped__', None)
            if unwrapped is not None:
                unwrapped_ids[id(unwrapped)] = fn_name

        if not unwrapped_ids:
            return

        leaked = []
        for attr in dir(main):
            if attr.startswith('_'):
                continue
            try:
                val = getattr(main, attr)
            except Exception:
                continue
            if callable(val) and id(val) in unwrapped_ids:
                metric_name = unwrapped_ids[id(val)]
                leaked.append((attr, metric_name))

        if leaked:
            names = ', '.join(f"{local} (= {orig})" for local, orig in leaked)
            warnings.warn(
                f"AutoLineage: the following sklearn metrics were imported "
                f"BEFORE install_all() and will not be tracked: {names}. "
                f"To fix: either move 'from sklearn.metrics import ...' to "
                f"after the autolineage hook installation, or use "
                f"'import autolineage.auto' at the very top of your script.",
                stacklevel=3,
            )
