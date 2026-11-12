"""Verificação de cobertura da correspondência contra a dim_parish (spec 004, FR-012).

Regra em `sdd/specs/004-correspondencia-freguesias/logic/derivacao-correspondencia.md` §4. Roda antes do dbt: em caso
de erro nada é promovido e a tabela anterior permanece.
"""

from collections.abc import Collection, Mapping

import pandas as pd

MAX_LISTED = 50


class CrosswalkCoverageError(ValueError):
    """A correspondência não cobre a dimensão; a promoção deve ser reprovada.

    Atributos (listas ordenadas de códigos, vazias quando não há problema do tipo): ``parishes_without_origin``,
    ``codes_2013_without_destination``, ``unknown_destinations``.
    """

    def __init__(
        self,
        *,
        parishes_without_origin: list[str],
        codes_2013_without_destination: list[str],
        unknown_destinations: list[str],
        names: Mapping[str, str] | None = None,
    ) -> None:
        self.parishes_without_origin = parishes_without_origin
        self.codes_2013_without_destination = codes_2013_without_destination
        self.unknown_destinations = unknown_destinations
        names = names or {}

        def listing(label: str, codes: list[str], *, named: bool = False) -> list[str]:
            if not codes:
                return []
            shown = [f"{code} {names[code]}" if named and code in names else code for code in codes[:MAX_LISTED]]
            more = f" … e mais {len(codes) - MAX_LISTED}" if len(codes) > MAX_LISTED else ""
            return [f"  {label} ({len(codes)}): {', '.join(shown)}{more}"]

        lines = [
            "cobertura reprovada",
            *listing("freguesias da dim_parish sem origem", parishes_without_origin, named=True),
            *listing("códigos de 2013 sem destino", codes_2013_without_destination),
            *listing("destinos fora da dim_parish", unknown_destinations),
        ]
        super().__init__("\n".join(lines))


def verify_coverage(
    crosswalk: pd.DataFrame,
    dim_parish_codes: Collection[str],
    codes_2013: Collection[str],
    *,
    names: Mapping[str, str] | None = None,
) -> None:
    """Levanta ``CrosswalkCoverageError`` se (a) alguma freguesia da dimensão não tem origem, (b) algum código
    de 2013 da tabela do INE não tem destino ou (c) algum destino não existe na dimensão.

    ``names`` (`{dicofre: nome}`) só enriquece a mensagem da lacuna (a).
    """
    destinations, origins = set(crosswalk["dicofre_2025"]), set(crosswalk["dicofre_2013"])
    dimension, expected_2013 = set(dim_parish_codes), set(codes_2013)
    without_origin = sorted(dimension - destinations)
    without_destination = sorted(expected_2013 - origins)
    unknown = sorted(destinations - dimension)
    if without_origin or without_destination or unknown:
        raise CrosswalkCoverageError(
            parishes_without_origin=without_origin,
            codes_2013_without_destination=without_destination,
            unknown_destinations=unknown,
            names=names,
        )
