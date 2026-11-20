"""Primitivas locais confinadas; locks de processo sem remover dados vizinhos."""

import ctypes
import json
import os
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from pipelines.collectors.wikipedia.manifest import digest, encode


def confined(root, relative):
    root = Path(root).resolve()
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"caminho fora da raiz: {relative}")
    current = path
    while current != root:
        if current.is_symlink() or current.is_junction():
            raise ValueError(f"link/junction não permitido no destino: {relative}")
        current = current.parent
    return path


def process_alive(pid):
    if type(pid) is not int or pid < 1:
        raise ValueError("PID inválido no lock")
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() != 87  # invalid parameter => PID inexistente
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        exit_code = ctypes.c_ulong()
        try:
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == 259  # STILL_ACTIVE; handle pode existir após a saída
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


@contextmanager
def source_lock(root):
    path = confined(root, ".locks/wikipedia.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    if path.exists():
        lock = json.loads(path.read_bytes())
        if process_alive(lock["pid"]):
            raise ValueError(f"Wikipedia já em execução: PID {lock['pid']}")
        if not lock.get("token"):
            raise ValueError("lock órfão sem identidade; inspecionar manualmente")
        # Journal é recuperado separadamente antes de qualquer build novo.
        path.unlink()
    with path.open("xb") as stream:
        stream.write(encode({"pid": os.getpid(), "token": token}))
        stream.flush()
        os.fsync(stream.fileno())
    try:
        yield
    finally:
        if path.exists() and json.loads(path.read_bytes()).get("token") == token:
            path.unlink()


def file_hash(path):
    return digest(Path(path).read_bytes())


def dependency_hashes(paths):
    return {str(Path(p).resolve()): file_hash(p) for p in paths}
