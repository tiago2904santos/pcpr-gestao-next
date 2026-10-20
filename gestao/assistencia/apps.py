from django.apps import AppConfig


class AssistenciaConfig(AppConfig):
    name = "gestao.assistencia"
    label = "assistencia"
    verbose_name = "Assistência por IA e Central de ajuda"

    def ready(self) -> None:
        from django.utils.module_loading import autodiscover_modules

        from gestao.plataforma import recursos

        from . import navegacao, usos_proprios  # noqa: F401  (menu e usos da própria app)
        from .rotinas import registrar

        # IA desligada (ADR 0050): o painel, as sugestões e a Central de ajuda respondem 404.
        recursos.registrar_rotas("assistencia", recursos.IA)
        recursos.registrar_rotas("ajuda", recursos.IA)

        # Cada contexto registra os seus usos em `<app>/ia_usos.py` (ganchos.registrar_uso);
        # a assistência não importa nenhum deles (import-linter).
        autodiscover_modules("ia_usos")
        registrar()
