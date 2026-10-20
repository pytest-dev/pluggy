from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any
from typing import cast
from typing import TypeVar
import warnings

import pytest

from pluggy._hooks import _kwonly_argnames
from pluggy._hooks import varnames
from pluggy._hooks import warn_keyword_only_parameters
from pluggy._manager import _formatdef


def test_varnames() -> None:
    def f(x) -> None:
        i = 3  # noqa #pragma: no cover

    class A:
        def f(self, y) -> None:
            pass  # pragma: no cover

    class B:
        def __call__(self, z) -> None:
            pass  # pragma: no cover

    assert varnames(f) == (("x",), ())
    assert varnames(A().f) == (("y",), ())
    assert varnames(B()) == (("z",), ())


def test_varnames_default() -> None:
    def f(x, y=3) -> None:
        pass

    assert varnames(f) == (("x",), ("y",))


def test_varnames_class() -> None:
    class C:
        def __init__(self, x) -> None:
            pass

    class D:
        pass

    class E:
        def __init__(self, x) -> None:
            pass

    class F:
        pass

    assert varnames(C) == (("x",), ())
    assert varnames(D) == ((), ())
    assert varnames(E) == (("x",), ())
    assert varnames(F) == ((), ())


def test_varnames_keyword_only() -> None:
    def f1(x, *, y) -> None:
        pass

    def f2(x, *, y=3) -> None:
        pass

    def f3(x=1, *, y=3) -> None:
        pass

    assert varnames(f1) == (("x",), ())
    assert varnames(f2) == (("x",), ())
    assert varnames(f3) == ((), ("x",))


def test_formatdef() -> None:
    def function1():
        pass

    assert _formatdef(function1) == "function1()"

    def function2(arg1):
        pass

    assert _formatdef(function2) == "function2(arg1)"

    def function3(arg1, arg2="qwe"):
        pass

    assert _formatdef(function3) == "function3(arg1, arg2='qwe')"

    def function4(arg1, *args, **kwargs):
        pass

    assert _formatdef(function4) == "function4(arg1, *args, **kwargs)"


def test_varnames_decorator() -> None:
    F = TypeVar("F", bound=Callable[..., Any])

    def my_decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)  # pragma: no cover

        return cast(F, wrapper)

    @my_decorator
    def example(a, b=123) -> None:
        pass

    class Example:
        @my_decorator
        def example_method(self, x, y=1) -> None:
            pass

    ex_inst = Example()

    assert varnames(example) == (("a",), ("b",))
    # Unbound: self is stripped because it's in _IMPLICIT_NAMES and qualname is dotted.
    assert varnames(Example.example_method) == (("x",), ("y",))
    # Bound: self is already consumed.
    assert varnames(ex_inst.example_method) == (("x",), ("y",))


def test_varnames_bound_method_from_module_function() -> None:
    """A module-level function assigned to a class attribute becomes a bound
    method when accessed on an instance, but its __qualname__ has no dot.
    varnames must still strip the first parameter."""

    def standalone(self, x) -> None:
        pass  # pragma: no cover

    class MyClass:
        method = standalone

    assert varnames(MyClass().method) == (("x",), ())


def test_varnames_unconventional_first_param_name() -> None:
    """Bound methods strip unconditionally, but unbound methods with
    non-standard first parameter names preserve all arguments."""

    class MyClass:
        def method(this, x) -> None:
            pass  # pragma: no cover

    # Bound: stripped regardless of name.
    assert varnames(MyClass().method) == (("x",), ())
    # Unbound with dotted qualname but non-implicit name: NOT stripped.
    assert varnames(MyClass.method) == (("this", "x"), ())


def test_varnames_classmethod() -> None:
    class MyClass:
        @classmethod
        def cm(cls, x, y=1) -> None:
            pass  # pragma: no cover

    # Classmethods are always bound (even from the class).
    assert varnames(MyClass.cm) == (("x",), ("y",))
    assert varnames(MyClass().cm) == (("x",), ("y",))


def test_varnames_staticmethod() -> None:
    class MyClass:
        @staticmethod
        def sm(x, y=1) -> None:
            pass  # pragma: no cover

    # Staticmethods have no implicit first arg.
    assert varnames(MyClass.sm) == (("x",), ("y",))
    assert varnames(MyClass().sm) == (("x",), ("y",))


def test_varnames_hookspec_without_self() -> None:
    """Hookspec-style class methods without self/cls preserve all parameters.

    This is the convention used by projects like pytest-timeout where hookspec
    classes define methods without ``self`` since they serve as pure signatures.
    By default varnames does not warn; the warning is emitted when
    ``legacy_noself=True`` is passed (as HookSpec.__init__ does).
    """

    class MySpecs:
        def my_hook(item, extra) -> None:
            pass  # pragma: no cover

    # Accessed as unbound: first arg is not an implicit name, keep it.
    assert varnames(MySpecs.my_hook) == (("item", "extra"), ())
    # Accessed as bound (via instance): first arg is stripped.
    assert varnames(MySpecs().my_hook) == (("extra",), ())


def test_varnames_legacy_noself_warns() -> None:
    """With ``legacy_noself=True``, varnames warns when it encounters a
    class method whose first parameter is not an implicit name."""
    import warnings

    class MySpecs:
        def my_hook(item, extra) -> None:
            pass  # pragma: no cover

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = varnames(MySpecs.my_hook, legacy_noself=True)
    assert result == (("item", "extra"), ())
    assert len(w) == 1
    assert issubclass(w[0].category, DeprecationWarning)
    assert "'item' is not 'self'" in str(w[0].message)


def test_varnames_legacy_noself_no_warn_with_self() -> None:
    """With ``legacy_noself=True``, no warning when the method has ``self``."""
    import warnings

    class MySpecs:
        def my_hook(self, item, extra) -> None:
            pass  # pragma: no cover

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = varnames(MySpecs.my_hook, legacy_noself=True)
    assert result == (("item", "extra"), ())
    assert len(w) == 0


def test_varnames_no_legacy_noself_no_warn() -> None:
    """Without ``legacy_noself``, no warning even for class methods without self."""
    import warnings

    class MySpecs:
        def my_hook(item, extra) -> None:
            pass  # pragma: no cover

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = varnames(MySpecs.my_hook)
    assert result == (("item", "extra"), ())
    assert len(w) == 0


def test_varnames_legacy_noself_suppressed_for_timeout_hooks() -> None:
    """The deprecation warning is suppressed for known upstream-fixed packages."""
    import warnings

    class TimeoutHooks:
        def pytest_timeout_set_timer(item, settings) -> None:
            pass  # pragma: no cover

        def pytest_timeout_cancel_timer(item) -> None:
            pass  # pragma: no cover

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result_set = varnames(TimeoutHooks.pytest_timeout_set_timer, legacy_noself=True)
        result_cancel = varnames(
            TimeoutHooks.pytest_timeout_cancel_timer, legacy_noself=True
        )
    assert result_set == (("item", "settings"), ())
    assert result_cancel == (("item",), ())
    assert len(w) == 0


def test_varnames_unresolvable_annotation() -> None:
    """Test that varnames works with annotations that cannot be resolved.

    In Python 3.14+, inspect.signature() tries to resolve string annotations
    by default, which can fail if the annotation refers to a type that isn't
    importable. Using __code__ directly avoids this issue.
    """

    def func_with_bad_annotation(
        x: "NonExistentType",  # type: ignore[name-defined]  # noqa: F821
        y,
    ) -> None:
        pass

    assert varnames(func_with_bad_annotation) == (("x", "y"), ())


def test_kwonly_argnames_forms() -> None:
    """``_kwonly_argnames`` normalizes callables the same way ``varnames`` does.

    These parameters are not part of ``varnames`` results, so they need to be
    reported separately (see ``test_warnings.py``).
    """

    def function(a, b=1, *, c, d=2) -> None:
        pass  # pragma: no cover

    class CallableObject:
        def __call__(self, q, *, cobalt) -> None:
            pass  # pragma: no cover

    class Methods:
        def method(self, a, *, kwonly, other=2) -> None:
            pass  # pragma: no cover

        @classmethod
        def cm(cls, a, *, kwonly) -> None:
            pass  # pragma: no cover

        @staticmethod
        def sm(a, *, kwonly) -> None:
            pass  # pragma: no cover

    F = TypeVar("F", bound=Callable[..., Any])

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)  # pragma: no cover

        return cast(F, wrapper)

    @decorator
    def decorated(a, *, decorated_kwonly=3) -> None:
        pass  # pragma: no cover

    assert _kwonly_argnames(function) == ("c", "d")
    assert _kwonly_argnames(lambda a: None) == ()
    assert _kwonly_argnames(Methods.cm) == ("kwonly",)
    assert _kwonly_argnames(Methods.sm) == ("kwonly",)
    assert _kwonly_argnames(Methods.method) == ("kwonly", "other")
    assert _kwonly_argnames(Methods().method) == ("kwonly", "other")
    assert _kwonly_argnames(CallableObject()) == ("cobalt",)
    assert _kwonly_argnames(decorated) == ("decorated_kwonly",)
    # Callables without a code object, and classes whose __init__ has no
    # keyword-only parameters.
    assert _kwonly_argnames(len) == ()
    assert _kwonly_argnames(type("Bare", (), {})) == ()

    class RaisingCall:
        def __getattr__(self, name):
            if name == "__call__":
                raise RuntimeError("boom")  # pragma: no cover
            raise AttributeError(name)  # pragma: no cover

    def broken_wrapped(*args, **kwargs) -> None:
        pass  # pragma: no cover

    broken_wrapped.__wrapped__ = 42  # type: ignore[attr-defined]

    # Never raise on exotic callables, just report nothing.
    assert _kwonly_argnames(RaisingCall()) == ()
    assert _kwonly_argnames(broken_wrapped) == ()
    assert _kwonly_argnames(5) == ()
    assert _kwonly_argnames(None) == ()


def test_warn_keyword_only_parameters_directly() -> None:
    """The helper warns with the given description, pointing at the caller."""

    def func(a, *, kwonly) -> None:
        pass  # pragma: no cover

    with pytest.warns(DeprecationWarning, match=r"func\(a, \*, kwonly\)") as wc:
        warn_keyword_only_parameters(func, what="func(a, *, kwonly)", stacklevel=2)
    assert len(wc.list) == 1
    assert Path(wc.list[0].filename).name == "test_helpers.py"

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        warn_keyword_only_parameters(lambda a, b=1: None, what="lambda", stacklevel=2)
