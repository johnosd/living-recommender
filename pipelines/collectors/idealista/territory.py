"""Correspondência exata de territórios, sem geocodificação nem palpites."""

import csv
import re
from collections import defaultdict
from pathlib import Path, PurePosixPath

from pipelines.collectors.caop.names import normalize_name
from pipelines.collectors.idealista.snapshot import IdealistaError

SEEDS = Path(__file__).resolve().parents[3] / "analytics" / "dbt" / "seeds"


def read_seed(name: str) -> list[dict]:
    with (SEEDS / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


class TerritoryResolver:
    def __init__(self, municipalities, parishes, *, file_localities=None, parish_synonyms=None):
        self.municipalities = set(municipalities["dico"])
        self.by_name = defaultdict(list)
        self.parishes = {}
        self.by_parish_name = defaultdict(set)
        for row in municipalities.itertuples(index=False):
            self.by_name[normalize_name(row.official_name)].append(row.dico)
        for row in parishes.itertuples(index=False):
            self.parishes[row.dicofre] = row.dico
            self.by_parish_name[(row.dico, normalize_name(row.official_name))].add(row.dicofre)
        aliases = parish_synonyms if parish_synonyms is not None else read_seed("parish_synonyms.csv")
        for row in aliases:
            if self.parishes.get(row["dicofre"]) != row["dico"]:
                raise IdealistaError("sinônimo de freguesia aponta para código CAOP inválido")
            self.by_parish_name[(row["dico"], normalize_name(row["source_name"]))].add(row["dicofre"])
        rows = file_localities if file_localities is not None else read_seed("idealista_file_localities.csv")
        self.file_localities = {}
        for row in rows:
            key = (normalize_name(row["source_region"]), normalize_name(row["locality_raw"]))
            if key in self.file_localities:
                raise IdealistaError("seed de arquivos repete região/localidade")
            self.file_localities[key] = row

    def resolve_file(self, relative: str) -> dict:
        path = PurePosixPath(relative)
        region = path.parts[0] if len(path.parts) > 1 else ""
        locality = re.split(r"-Paginas", path.stem, maxsplit=1, flags=re.IGNORECASE)[0]
        alias = self.file_localities.get((normalize_name(region or "_"), normalize_name(locality)))
        if alias:
            level = alias["locality_level"]
            dico, dicofre = alias.get("dico") or None, alias.get("dicofre") or None
            if level not in ("municipio", "freguesia", "regiao"):
                raise IdealistaError(f"nível territorial inválido na seed: {relative}")
            if level == "regiao":
                if dico or dicofre:
                    raise IdealistaError("região não pode ter código municipal/freguesia")
            elif dico not in self.municipalities:
                raise IdealistaError(f"município da seed ausente na CAOP: {relative}")
            if dicofre and self.parishes.get(dicofre) != dico:
                raise IdealistaError(f"freguesia da seed não pertence ao município: {relative}")
            if level == "freguesia" and not dicofre:
                raise IdealistaError(f"freguesia da seed sem código: {relative}")
        else:
            candidates = self.by_name.get(normalize_name(locality), [])
            if len(candidates) != 1:
                raise IdealistaError(f"município sem correspondência única: {relative}")
            dico, dicofre, level = candidates[0], None, "municipio"
        return {"dico": dico, "dicofre": dicofre, "locality_level": level,
                "locality_raw": locality, "source_region": region,
                "parish_match_method": "arquivo" if dicofre else "nao_resolvido"}

    def resolve_listing(self, file_territory: dict, title: str | None) -> dict:
        result = dict(file_territory)
        if result["dicofre"] or not result["dico"]:
            return result
        locality = (title or "").rsplit(",", 1)[-1].strip()
        matches = self.by_parish_name.get((result["dico"], normalize_name(locality)), set()) if locality else set()
        if len(matches) == 1:
            result.update(dicofre=next(iter(matches)), parish_match_method="titulo_exato_ou_sinonimo")
        return result
