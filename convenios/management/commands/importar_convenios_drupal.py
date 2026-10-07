import csv
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

from convenios.importacao import importar, ler_xml


class _SimulacaoDesfeitaError(Exception):
    pass


class Command(BaseCommand):
    help = "Importa convênios da exportação XML do estagio.uff.br (RF07). Pode rodar de novo."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("arquivo", type=Path, help="conveniosestagio.xml exportado do Drupal")
        parser.add_argument("--simular", action="store_true", help="não grava nada no banco")
        parser.add_argument(
            "--relatorio",
            type=Path,
            default=Path("reports/importacao.csv"),
            help="CSV com rejeitados e avisos (padrão: reports/importacao.csv)",
        )

    def handle(self, *_args: Any, **opcoes: Any) -> None:
        registros = ler_xml(opcoes["arquivo"])
        try:
            with transaction.atomic():
                relatorio = importar(registros)
                if opcoes["simular"]:
                    raise _SimulacaoDesfeitaError
        except _SimulacaoDesfeitaError:
            self.stdout.write("Simulação: nada foi gravado.")

        caminho: Path = opcoes["relatorio"]
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with caminho.open("w", newline="", encoding="utf-8-sig") as arquivo:  # Excel abre direto
            saida = csv.writer(arquivo, delimiter=";")
            saida.writerow(["situação", "nó no Drupal", "título", "motivo"])
            saida.writerows(("rejeitado", *linha) for linha in relatorio.rejeitados)
            saida.writerows(("aviso", *linha) for linha in relatorio.avisos)

        self.stdout.write(
            f"{len(registros)} registros lidos: {relatorio.criados} criados, "
            f"{relatorio.atualizados} atualizados, {len(relatorio.rejeitados)} rejeitados, "
            f"{len(relatorio.avisos)} avisos. Relatório: {caminho}"
        )
