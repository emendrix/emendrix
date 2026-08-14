"""Smoke test: the package imports and reports a version.

Deliberately trivial. Its job is to prove the toolchain (src layout, editable
install, pytest discovery, mypy --strict over tests) is wired up correctly.
"""

from importlib.metadata import version

import emendrix


def test_package_imports() -> None:
    assert emendrix.__doc__ is not None


def test_version_is_exposed_and_agrees_with_the_distribution() -> None:
    """`__version__` and `pyproject.toml` are two places one number lives; they must agree.

    Asserted against the installed distribution rather than against a literal, so a release
    bump does not require editing a test, and so the failure mode this actually guards
    against, bumping one of the two and forgetting the other, is the one it catches.
    """
    assert emendrix.__version__ == version("emendrix")
