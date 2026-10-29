"""Porta única de IA (AUT-96, ADR 0019 e ADR 0048).

Recebe e devolve só primitivos (instruções, blocos de dados, esquema JSON) e não conhece
ofício, plano, prestação nem servidor: quem decide o que vai ao modelo, o que volta e o que
vale é o contexto `gestao.assistencia` (com os ganchos dos contextos de negócio).

Adaptadores: `simulado` (padrão em todo ambiente; sem rede), `gravado` (testes) e
`anthropic` (Messages API por HTTPS; desligado por padrão e nunca no PREVIEW).
"""
