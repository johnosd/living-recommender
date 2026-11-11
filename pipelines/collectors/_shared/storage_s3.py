"""Storage S3 com as mesmas chaves relativas e a mesma interface do LocalStorage."""

from pathlib import Path
from uuid import uuid4

from botocore.exceptions import ClientError

from pipelines.collectors._shared.storage import InvalidKey, validate_key

# 412: o objeto já existe. 409: outra escrita condicional concorrente na mesma chave.
_EXISTS = {"PreconditionFailed", "ConditionalRequestConflict"}


class S3Storage:
    """Credenciais vêm só da cadeia padrão do boto3 (ambiente, perfil ou papel IAM)."""

    def __init__(self, bucket: str, prefix: str = "", *, client=None):
        if not bucket:
            raise ValueError("bucket obrigatório")
        prefix = prefix.strip("/")
        if prefix:
            validate_key(prefix)
        self.bucket = bucket
        self.prefix = f"{prefix}/" if prefix else ""
        if client is None:
            import boto3  # só o modo S3 precisa do SDK; o modo local não lê credenciais

            client = boto3.client("s3")
        self.client = client

    def _object_key(self, key: str) -> str:
        return self.prefix + validate_key(key)

    def _put(self, key: str, body) -> None:
        # IfNoneMatch="*" faz o S3 recusar a escrita se a chave já existir (nunca sobrescreve).
        try:
            self.client.put_object(
                Bucket=self.bucket, Key=self._object_key(key), Body=body, IfNoneMatch="*"
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] in _EXISTS:
                raise FileExistsError(key) from exc
            raise

    def put(self, key: str, content: bytes) -> None:
        if not isinstance(content, bytes):
            raise TypeError("content deve ser bytes")
        self._put(key, content)

    def put_file(self, key: str, source: str | Path) -> None:
        # put_object aceita até 5 GB; os ZIPs da CAOP têm cerca de 100 MB.
        with Path(source).open("rb") as stream:
            self._put(key, stream)

    def get(self, key: str) -> bytes:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=self._object_key(key))["Body"].read()
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(key) from exc
            raise

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._object_key(key))

    def delete_prefix(self, prefix: str) -> None:
        if not prefix.endswith("/") or len(prefix.split("/")) < 3:
            raise InvalidKey("prefixo de limpeza deve identificar um run")
        for key in self.list_keys(prefix):
            self.delete(key)

    def list_keys(self, prefix: str = "") -> set[str]:
        if prefix:
            validate_key(prefix.rstrip("/"))
        keys = set()
        pages = self.client.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=self.prefix + prefix
        )
        for page in pages:
            keys.update(item["Key"][len(self.prefix):] for item in page.get("Contents", []))
        return keys

    def preflight(self) -> None:
        """Prova escrita e remoção no destino antes de gastar rede com o download."""
        key = f".probe/{uuid4().hex}"
        self.put(key, b"probe")
        self.delete(key)
