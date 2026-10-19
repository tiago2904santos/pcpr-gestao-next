# WhatsApp Business como canal principal do sistema de testes

- **Decisão do usuário:** 18/10/2026.
- **Situação (18/10/2026):** implementado e testado com o simulador; integração real pronta,
  mas não ativada nem validada com a Meta — ver [implementação do piloto](../automacao/implementacao-piloto.md)
  e o [roteiro do LAB](../ops/lab-whatsapp-ia.md).
- **Decisão estrutural:** [ADR 0046](../adr/0046-whatsapp-principal-no-sistema-de-testes.md).

## Contexto e público

O usuário esclareceu que este site é um sistema de testes independente, não é um site oficial
da polícia e não vai operar com policiais. As viagens, pessoas, diárias e documentos dos
cenários são fictícios. Os nomes dos módulos e as referências históricas do repositório não
determinam a identidade do responsável pelo piloto nem tornam seus participantes policiais.

A análise de 17/10/2026 partiu de uma implantação institucional policial. Essa premissa fica
substituída para o piloto aqui descrito. Não se exige autorização da PCPR ou uma exceção para
órgão policial para desenvolver este sistema de testes. Também não se declara que a Meta
aprovou a conta: o cadastro do responsável real e os requisitos normais da plataforma continuam.

## Saída manual vigente

A decisão posterior do usuário adota [pendências manuais](envios-manuais.md) para a saída:
WhatsApp Business do operador, mensagem única por servidor/prestação e PDFs baixados para
anexar à mão. Somente KM é um link pessoal. `AUTOMACAO_TRANSPORTE=manual` é o padrão;
não usa a API nem IA para enviar. O piloto da API abaixo permanece como alternativa
explícita para outro cenário; não é necessário para este fluxo manual.

## Canal e experiência

1. **Principal:** WhatsApp Business Platform, pela API oficial Cloud API. O aplicativo
   WhatsApp Business operado à mão não substitui a integração automática.
2. **Apoio:** portal para formulários, documentos e histórico; notificações internas para o
   operador; e-mail opcional. SMTP institucional não é pré-requisito do piloto WhatsApp.
3. **Contingência:** copiar mensagem, envio manual registrado ou acesso ao portal quando o
   canal principal estiver indisponível, sem troca silenciosa para outro canal.
4. **Identificação:** conta e mensagens identificam o responsável real e o caráter de teste,
   sem sugerir vínculo oficial com a polícia.
5. **Público:** apenas participantes de teste autorizados, com contato verificado e opt-in.
   Os contatos de entrega podem ser reais; os dados administrativos e PDFs são sintéticos.

## Fluxos incluídos

- Avisos de liberação fictícia de diárias e lembretes de comprovante.
- Link de KM na véspera e avisos de pendências do diário fictício.
- Documentos disponíveis, DB/RT para assinatura de teste e avisos de substituição.
- Recebimento de mensagens e documentos sintéticos, confirmação e encaminhamento ao operador.
- Situação da entrega (enviada, entregue, lida ou falhou) e atendimento determinístico de
  dúvidas com link ao portal. IA é uma evolução opcional, sem executar atos administrativos.

## Ambientes e ativação planejada

- **Simulador local:** continua sendo o padrão dos testes automatizados; não chama a Meta.
- **LAB dedicado ao teste da Cloud API:** integração externa com recursos de teste
  disponibilizados pelo onboarding da Meta, credenciais separadas, acesso autenticado,
  lista fechada de destinatários, limites de envio e dados sintéticos. Os recursos e limites
  efetivamente disponíveis devem ser conferidos no painel antes do ensaio.
- **PREVIEW/DEMO público sem senha:** permanece simulado e sem credenciais reais. Nenhum visitante
  pode cadastrar um número arbitrário ou provocar uma mensagem externa.
- O canal começa **desligado**, podendo ser ligado no LAB após os critérios de aceite.
  `bloqueado` é reservado a impedimento efetivamente identificado, não ao nome do repositório.
- Configurar contas, inserir segredos, publicar webhooks e enviar mensagens são etapas futuras
  de implantação; esta revisão altera documentação e não realiza essas ações.

## Responsabilidades e critérios de aceite

O PCPR conserva regras, permissões, estado, contatos e auditoria. O n8n transporta e registra
resultados; o webhook de entrada direto no PCPR (variante V2 do protótipo) é o caminho preferido.

Antes de ligar o LAB: conta e recursos de teste disponíveis; opt-in e destinatários permitidos
conferidos pelo servidor; credenciais fora do repositório; webhook HTTPS autenticado pela
assinatura do provedor; verificação GET; janela de atendimento e modelos aprovados quando
exigidos; reserva/idempotência; tratamento de resultado desconhecido; desligamento; retenção
medida; envio/recebimento e status testados ponta a ponta. Destinatário fora da lista ou sem
opt-in deve produzir zero chamada de envio à Meta. Mensagens e documentos deixam claro que
diárias, viagens e assinaturas pertencem a uma simulação.

## Fontes e limites

- [Política oficial do WhatsApp Business](https://whatsappbusiness.com/policy/), consultada em
  18/10/2026: identidade correta, opt-in, modelos e janela de atendimento. A restrição dirigida
  a autoridades policiais permanece pertinente a eventual uso institucional futuro.
- [Início da Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started):
  referência para o onboarding. A leitura automatizada recebeu HTTP 429 em 18/10/2026;
  limites, recursos de teste e exigências de verificação não foram reconfirmados nesta revisão.
- Evidência interna: esclarecimento do usuário nesta conversa e resultados locais de
  [T1–T13 e TW0–TW13](../automacao/prototipo/README.md), que não comprovam operação na Meta.
