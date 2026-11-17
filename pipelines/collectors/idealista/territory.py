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
        # Seed exclusiva do metadado novo: não muda a interpretação histórica dos títulos.
        self.metadata_synonyms = {}
        for row in read_seed("idealista_metadata_parish_synonyms.csv"):
            key = (row["dico"], normalize_name(row["source_name"]))
            if key in self.metadata_synonyms:
                raise IdealistaError("seed de metadados repete município/freguesia")
            self.metadata_synonyms[key] = row["dicofre"]

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

    def resolve_metadata(self, row: dict) -> dict:
        """A hierarquia da captura nunca transforma distrito/ilha em município homônimo."""
        municipality = (row.get("Município") or "").strip()
        subregion = (row.get("Sub-região") or "").strip()
        region = (row.get("Região") or "").strip()
        parish = (row.get("Freguesia") or "").strip()
        if not municipality:
            if not (subregion or region):
                raise IdealistaError("metadados territoriais sem município nem região declarada")
            return {"dico": None, "dicofre": None, "locality_level": "regiao",
                    "locality_raw": subregion or region, "source_region": row.get("Região"),
                    "parish_match_method": "nao_resolvido"}
        # Reutiliza seeds explícitas: a origem nova é plana e não tem região no caminho.
        result = self.resolve_file(municipality + ".json")
        result["source_region"] = row.get("Região")
        if result["dicofre"]:
            result["parish_match_method"] = "metadado_seed"
            return result
        if parish:
            matches = self.by_parish_name.get((result["dico"], normalize_name(parish)), set())
            if len(matches) == 1:
                result.update(dicofre=next(iter(matches)), parish_match_method="metadado_exato_ou_sinonimo")
            elif not matches:
                alias = self.metadata_synonyms.get((result["dico"], normalize_name(parish)))
                if alias:
                    # Confere na dimensão usada no build, inclusive quando for uma fixture parcial.
                    if self.parishes.get(alias) != result["dico"]:
                        raise IdealistaError("sinônimo de metadado aponta para código CAOP inválido")
                    result.update(dicofre=alias, parish_match_method="metadado_seed")
            return result
        return self.resolve_listing(result, row.get("Titulo"))
