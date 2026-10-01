from django.core.management.base import BaseCommand, CommandError

from gestao.plataforma.auditoria import verificar_cadeia


class Command(BaseCommand):
    help = "Recalcula a cadeia de hashes da trilha de auditoria e acusa adulterações."

    def handle(self, *args, **opts):
        integra, total, quebra = verificar_cadeia()
        if not integra:
            raise CommandError(f"Cadeia de auditoria QUEBRADA no evento #{quebra}.")
        self.stdout.write(self.style.SUCCESS(f"Cadeia íntegra: {total} evento(s) verificados."))
