"""Disputa determinística entre processos pela recuperação do mesmo lock órfão."""

import json
import queue
import subprocess
import sys
import threading
from pathlib import Path

WORKER = '''
import os, sys
from pathlib import Path
from pipelines.collectors.wikipedia import local

original_alive = local.process_alive
def gated_alive(pid):
    if pid == 999999999:
        print('STALE_READ', flush=True)
        assert sys.stdin.readline().strip() == 'CHECK'
        return False
    return original_alive(pid)
local.process_alive = gated_alive
try:
    with local.source_lock(Path(sys.argv[1])):
        print('ACQUIRED:' + str(os.getpid()), flush=True)
        assert sys.stdin.readline().strip() == 'RELEASE'
except ValueError:
    print('BUSY', flush=True)
'''


def read_line(process):
    messages = queue.Queue()
    threading.Thread(target=lambda: messages.put(process.stdout.readline().strip()), daemon=True).start()
    return messages.get(timeout=15)


def send(process, message):
    process.stdin.write(message + "\n")
    process.stdin.flush()


def test_wikipedia_orphan_recovery_never_removes_another_process_lock(tmp_path):
    lock_path = tmp_path / ".locks/wikipedia.json"
    lock_path.parent.mkdir()
    lock_path.write_text(json.dumps({"pid": 999999999, "token": "orphan"}), encoding="utf-8")
    processes = []

    def start():
        process = subprocess.Popen([sys.executable, "-c", WORKER, str(tmp_path)],
            cwd=Path(__file__).resolve().parents[2], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8")
        processes.append(process)
        return process

    try:
        first = start()
        assert read_line(first) == "STALE_READ"
        second = start()
        second_state = read_line(second)
        assert second_state in {"STALE_READ", "BUSY"}
        send(first, "CHECK")
        acquired = read_line(first)
        assert acquired.startswith("ACQUIRED:")
        owner = json.loads(lock_path.read_bytes())
        assert owner["pid"] == int(acquired.split(":")[1])
        if second_state == "STALE_READ":
            # Reproduz o código antigo: B apaga o novo lock após A entrar.
            send(second, "CHECK")
            second_state = read_line(second)
        assert second_state == "BUSY", "dois processos entraram na região protegida"
        assert json.loads(lock_path.read_bytes()) == owner
        send(first, "RELEASE")
        for process in processes:
            _, error = process.communicate(timeout=15)
            assert process.returncode == 0, error
        assert not lock_path.exists()
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=15)
