"""Shared pytest config."""

import warnings

import pytest

# Silence asyncio "unhandled exception" warnings from cancelled signal tasks
warnings.filterwarnings("ignore", category=DeprecationWarning, module="asyncio")
