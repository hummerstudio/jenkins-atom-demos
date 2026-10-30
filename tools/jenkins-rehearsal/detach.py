#!/usr/bin/env python3
"""Run a program in its own session with stdio on a log file, then exit immediately.

`nohup cmd &` is not enough over ssh: the child stays in the ssh session and sshd keeps the channel open until
it exits, so `ssh host ./start.sh restart` appears to hang even though the server is up. A new session detaches it.

    detach.py <logfile> <program> [args...]
"""
import os
import subprocess
import sys

log_path, program, args = sys.argv[1], sys.argv[2], sys.argv[3:]
with open(log_path, "ab") as log:
    process = subprocess.Popen(
        [program] + args,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,   # setsid: no controlling terminal, nothing for sshd to wait on
        close_fds=True,
    )
print(process.pid)
