"""Storage local com as mesmas chaves relativas usadas no S3."""

import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from uuid import uuid4


class InvalidKey(ValueError):
    """Chave de objeto inválida ou fora da raiz."""


def _canonical_path(path: Path) -> Path:
    """Iguala a forma normal e a forma estendida do mesmo caminho Windows."""
    value = str(path)
    if os.name == "nt":
        if value.startswith("\\\\?\\UNC\\"):
            value = "\\\\" + value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
    return Path(value)


def validate_key(key: str) -> str:
    if not isinstance(key, str) or not key or "\\" in key:
        raise InvalidKey(f"chave inválida: {key!r}")
    path = PurePosixPath(key)
    if path.is_absolute() or any(part in ("", ".", "..") for part in key.split("/")):
        raise InvalidKey(f"chave inválida: {key!r}")
    return key


class LocalStorage:
    def __init__(self, root: str | Path = ".data"):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = self.root.joinpath(*validate_key(key).split("/"))
        resolved = _canonical_path(path.resolve())
        root = _canonical_path(self.root)
        if not resolved.is_relative_to(root):
            raise InvalidKey(f"chave fora da raiz: {key!r}")
        return path

    def put(self, key: str, content: bytes) -> None:
        if not isinstance(content, bytes):
            raise TypeError("content deve ser bytes")
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".object-", dir=path.parent)
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def put_file(self, key: str, source: str | Path) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".object-", dir=path.parent)
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as output, Path(source).open("rb") as input_stream:
                shutil.copyfileobj(input_stream, output, length=1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
            os.link(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def get_file(self, key: str, destination: str | Path) -> None:
        with self._path(key).open("rb") as input_stream, Path(destination).open("wb") as output:
            shutil.copyfileobj(input_stream, output, length=1024 * 1024)

    def local_path(self, key: str) -> Path:
        """Expõe caminho validado para leitores locais de arquivos grandes."""
        return self._path(key)

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def delete_prefix(self, prefix: str) -> None:
        if not prefix.endswith("/") or len(prefix.split("/")) < 3:
            raise InvalidKey("prefixo de limpeza deve identificar um run")
        for key in self.list_keys(prefix):
            self.delete(key)

    def list_keys(self, prefix: str = "") -> set[str]:
        if prefix:
            validate_key(prefix.rstrip("/"))
        return {
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*")
            if path.is_file()
            and not path.name.startswith(".object-")
            and path.relative_to(self.root).as_posix().startswith(prefix)
        }

    def preflight(self) -> None:
        key = f".probe/{uuid4().hex}"
        self.put(key, b"probe")
        self.delete(key)
