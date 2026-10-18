"""Migração única dos sistemas antigos (Gerenciador de Viagens e Eventos Sociais) para este.

Lê os bancos antigos só para leitura (URLs em variáveis de ambiente, nunca no repositório),
grava pelo ORM com a correspondência "id antigo → id novo" em `MapaLegado` e gera um relatório
de conferência sem dados pessoais. Rodar de novo não duplica: o que já tem correspondência é
pulado (ou atualizado, quando a etapa diz).
"""
