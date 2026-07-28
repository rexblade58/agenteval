"""Fixture: a mock agent that hangs (for timeout tests)."""

import time

time.sleep(30)
print("woke up")
