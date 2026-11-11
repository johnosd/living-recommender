"""Resolução de nomes de município para o código oficial `dico`.

Regra de `sdd/specs/002-ingestao-pordata-ine/logic/ingestao-datasets.md` §5: um nome da fonte
vale se estiver na tabela de sinônimos (grafia exata) ou se o nome normalizado casar com
**um único** município. Ambiguidade e ausência nunca são resolvidas por palpite.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping

from pipelines.collectors.caop.names import normalize_name


class UnresolvedMunicipalities(ValueError):
    """Há nomes sem correspondência única; `names` lista todos, ordenados."""

    def __init__(self, names: Iterable[str]):
        self.names = sorted(set(names))
        super().__init__(f"municípios sem correspondência: {', '.join(self.names)}")


def resolve_municipality_names(
    names: Iterable[str],
    municipalities: Mapping[str, str],
    synonyms: Mapping[str, str],
) -> dict[str, str]:
    """Mapeia cada nome da fonte para um `dico`.

    `municipalities` é `{dico: nome_oficial}`; `synonyms` é `{grafia_exata_da_fonte: dico}`.
    Levanta `UnresolvedMunicipalities` se algum nome ficar sem correspondência única.
    """
    by_normalized: dict[str, list[str]] = defaultdict(list)
    for dico, official_name in municipalities.items():
        by_normalized[normalize_name(official_name)].append(dico)

    resolved: dict[str, str] = {}
    unresolved: list[str] = []
    for name in dict.fromkeys(names):
        if name in synonyms:
            dico = synonyms[name]
            if dico in municipalities:
                resolved[name] = dico
            else:
                unresolved.append(name)  # a seed aponta para um código que a CAOP não tem
            continue
        try:
            candidates = by_normalized.get(normalize_name(name), [])
        except ValueError:  # nome vazio
            candidates = []
        if len(candidates) == 1:
            resolved[name] = candidates[0]
        else:
            unresolved.append(name)  # nenhum candidato, ou ambíguo (homônimo sem sinônimo)
    if unresolved:
        raise UnresolvedMunicipalities(unresolved)
    return resolved
