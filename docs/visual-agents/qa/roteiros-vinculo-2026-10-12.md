# Roteiros — associação do candidato ao gate concluído

RO01/RO02/RO03: **concluídas tecnicamente**, sem homologação visual do usuário.
Esta conferência atualiza o registro; não adiciona redesign nem nova regra.

O gate `gate-propagacao-125caa7f.log` encerrou com 2.343 testes aprovados e
`tudo verde`. A matriz ainda dizia que estava em execução. O checkpoint
de implementação é d27329c, cuja conferência financeira removeu a variante
horizontal substituída. As capturas e a revisão estão em `roteiros-revisao.json`.

Conferência atual contra o candidato: seis dos sete hashes preservados;
templates de Roteiros, view e itinerário sem diff desde d27329c. A diferença
posterior em components.css é aditiva. O hero com múltiplas ações tem cobertura
de 360/768/1024/1440 em `diario-hero-compat.json`, sem axe no header, overflow ou
erro de console. A nova variante de vazio do Painel não é consumida por Roteiros.

O manifesto `roteiros-vinculo-gate.json` registra hashes e evidências.
Revisão independente somente leitura confirmou a associação e não encontrou
defeito remanescente. Não se apresenta esse gate histórico como validação global
de todo o HEAD atual. Os testes específicos cobrem criar/salvar roteiro,
aplicação em Ofício, menu/criação a partir do roteiro, busca HTMX e teclado.

Lacunas funcionais preexistentes: campos de efetivo/observações ainda ausentes
da folha; não foram implementados nesta migração visual. Não há nova alegação
de paridade com o legado em execução. Avisos de SQL históricos não representam
uma medição atual de latência. Referências detalhadas em `docs/parity/roteiros.md`.

Limpeza confirmada: cinco regras da conferência horizontal removidas e includes
migrados; bases do itinerário, mapa e documentos são usos legítimos mantidos.
