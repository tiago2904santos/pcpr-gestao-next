"""Integrações com sistemas externos (ADR 0019).

Cada integração é um subpacote com configuração, porta tipada, adaptadores (simulado por
padrão), erros próprios e serviço. Contextos de negócio dependem daqui; daqui não se
importa nenhum contexto de negócio.
"""
