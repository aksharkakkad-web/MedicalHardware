"""Evaluation tests without shadowing the production ``evals`` package."""

from pkgutil import extend_path


__path__ = extend_path(__path__, __name__)
