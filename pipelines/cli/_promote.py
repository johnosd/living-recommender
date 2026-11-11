"""Promoção atômica de diretórios construídos em área temporária, por caminho.

Cada tabela do lake é promovida sozinha. Trocar `lake/bronze` ou `lake/silver` inteiros apagaria
as tabelas de outras features (plan 002, R-006): o build da CAOP e o das observações convivem.
"""

import os
import shutil
from collections.abc import Sequence
from pathlib import Path


def promote_paths(root: Path, candidate: Path, relative_paths: Sequence[str]) -> list[str]:
    """Move `candidate/<rel>` para `root/<rel>`, guardando backup; desfaz tudo se algum passo falhar.

    Caminhos ausentes no candidato são ignorados. Devolve os caminhos promovidos.
    """
    changed: list[tuple[Path, Path, Path, bool, str]] = []
    try:
        for relative in relative_paths:
            staged = candidate / relative
            if not staged.exists():
                continue
            current = root / relative
            backup = current.with_name(f".previous-{current.name}-{candidate.name}")
            current.parent.mkdir(parents=True, exist_ok=True)
            had_previous = current.exists()
            if had_previous:
                os.replace(current, backup)
            try:
                os.replace(staged, current)
            except OSError:
                if had_previous:
                    os.replace(backup, current)
                raise
            changed.append((current, staged, backup, had_previous, relative))
    except OSError:
        for current, staged, backup, had_previous, _ in reversed(changed):
            os.replace(current, staged)
            if had_previous:
                os.replace(backup, current)
        raise
    for _, _, backup, had_previous, _ in changed:
        if had_previous:
            shutil.rmtree(backup)
    return [relative for *_, relative in changed]
