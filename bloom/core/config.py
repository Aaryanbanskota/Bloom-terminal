"""
bloom.core.config
-----------------
Application-level configuration values.
Sensitive or environment-specific settings live here.
"""

import os

# App metadata
APP_NAME = "Bloom Terminal"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Bloom"

# XP formula constants
XP_PER_SUCCESS = 10
XP_PER_FAILURE = 5
LEVEL_FORMULA_EXPONENT = 0.6  # level = int((xp / 100) ** exponent) + 1

# Intro auto-dismiss delay (milliseconds)
INTRO_DISMISS_MS = 60_000

# Hint display interval (milliseconds, random between min and max)
HINT_INTERVAL_MIN_MS = 90_000
HINT_INTERVAL_MAX_MS = 180_000

# Shell buffer read size
PTY_READ_SIZE = 4096

# Tab defaults
DEFAULT_TAB_LABEL = "Shell"

# Debug flag — set BLOOM_DEBUG=1 in the environment to enable
DEBUG = os.environ.get("BLOOM_DEBUG", "0") == "1"
