from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from convenios.alertas import enviar_alertas


class Command(BaseCommand):
    help = "Envia à Divisão de Estágio os alertas de vencimento de convênio. Rodar 1x por dia."

    def handle(self, *_args: Any, **_options: Any) -> None:
        if not settings.DIVISAO_EMAIL:
            raise CommandError("Defina DIVISAO_EMAIL para enviar os alertas.")
        enviados = enviar_alertas()
        self.stdout.write(f"{enviados} alerta(s) enviado(s).")
