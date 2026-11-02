"""Keeps Windows awake while a long run works (no settings changed; same request video players make).
    pythonw -m ecosim.keepawake <flag file>     -> stops when the flag file appears."""
import ctypes
import os
import sys
import time

flag = sys.argv[1] if len(sys.argv) > 1 else 'done.flag'
ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)    # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
while not os.path.exists(flag):
    time.sleep(30)
ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
