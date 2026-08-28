# 00 — Continuidade Support R1

**Atualizado em:** 28/08/2026 — produção validada

**Backend:** `andregeraseev/reparossjc`, branch `support-r1`

**App:** `andregeraseev/reparossjc-wear-`, branch `v18.27-support-r1`

> Esta frente é isolada da Corporate API R1 que está funcionando em produção. **Não fazer deploy automático e não mesclar para `corporate-api-r1`/`main`.** O Support R1 é uma Central de Suporte interna e começa somente leitura/diagnóstico; nenhum comando remoto arbitrário foi criado.

## Estado atual
O backend Support R1 Review4 está implementado, com gate verde e LIVE no PythonAnywhere.

- base funcional Review4: `ed6c6202fd7cefe70127d47c476a29456a74c255`;
- commit implantado: `4a4ca987484b4480c92ad56f91ef413902e98284`;
- branch local de produção: `deploy-support-r1-20260828`;
- workflow: `Test Reparos SJC Support R1`;
- run Review4: `33168497303`;
- conclusão: **success**;
- GitGuardian no mesmo head: **success**;
- implantado no PythonAnywhere em 28/08/2026;
- `RSJC_SUPPORT_INGEST_ENABLED=True` após validação inicial com ingestão desligada;
- smoke Corporate+Support e integridade SQLite aprovados.

## Identidade e acesso
- código `RSJC-XXXX-XXXX` é somente localizador para o suporte;
- a conta Support possui identidade própria e **não é identificada pelo workspace comercial**;
- a chave aleatória original da conta não é persistida no servidor: somente `SHA-256` em `account_key_hash`;
- cada aparelho tem `installationId` próprio e token aleatório;
- token do aparelho é persistido no servidor somente como hash;
- `/suporte/` exige usuário Django `is_staff`;
- páginas internas de suporte usam `no-cache` e acessos relevantes são auditados.

## Privacidade e telemetria
A Central recebe apenas dados técnicos sanitizados. Não devem entrar:
- senha, token, API key, keystore ou segredo;
- fotos;
- nome/telefone/endereço de clientes atendidos;
- conteúdo integral de clientes, orçamentos ou fichas;
- `message`, `stack`, `reason` ou outro texto livre de erro.

Proteções acumuladas Review2–Review4:
- consentimento contínuo é por aparelho;
- snapshot **não pode alterar consentimento**; somente `/api/support/v1/consent`;
- rotas removem query string/fragmento;
- `detail` usa allowlist técnica;
- `action` e `entity` agora usam vocabulário técnico estrito tanto online quanto offline;
- rótulo desconhecido vira `unknown_event` / `system`, sem preservar o texto enviado;
- eventos duplicados são reconhecidos por `eventId`;
- retenção por idade/quantidade + comando `python manage.py purge_support_data`.

## Modelos principais
- `SupportAccount` — código público, hash de identidade Support, workspace apenas como metadata;
- `SupportDevice` — aparelho/instalação, hash de token, consentimento por aparelho;
- `SupportEvent` — eventos técnicos estruturados;
- `SupportSnapshot` — snapshot de saúde;
- `SupportCase` — chamado interno;
- `SupportAccessLog` — auditoria de uso da Central.

## API
- `GET /api/support/v1/health`;
- `POST /api/support/v1/bootstrap`;
- `POST /api/support/v1/consent`;
- `POST /api/support/v1/events`;
- `POST /api/support/v1/snapshot`.

A ingestão só funciona quando `RSJC_SUPPORT_INGEST_ENABLED=1`.

## Central `/suporte/`
Já preparada para:
- procurar código de suporte;
- aparelhos/fontes de diagnóstico;
- saúde baseada no aparelho atual, sem celular antigo degradar a nota principal;
- versão/app/Android, último contato, backup, fila de sync, storage e Live Update;
- diagnóstico automático por regras;
- filtros por período/severidade/aparelho/ação;
- agrupamento de erros repetidos;
- resumo técnico copiável;
- importação de pacote offline;
- chamados internos Aberto / Investigando / Resolvido;
- auditoria de acesso.

## Pacote offline
Formato atual do app: `ReparosSJC_Support_Diagnostic`, versão 3.

- usa `supportAccountHash`, não a chave bruta da conta;
- instalação offline é representada como fonte separada;
- pacote é novamente sanitizado no servidor;
- `action/entity` manipulados manualmente também passam pela política estrita;
- limite de upload da Central: 1 MB.

## Relação com o app
O candidato atual do app é **Support R1 Review5 PDF + IA**, versão 18.27/1827. Foi instalado sem desinstalar no Samsung SM-S911B/Android 16 e preservou os dados locais. O piloto confirmou importação offline, bootstrap online, envio manual e compartilhamento contínuo.

Consultar no app:
- `qa/v18.27/ARQUITETURA_SUPPORT_R1.md`;
- `qa/v18.27/RELATORIO_SUPPORT_R1_REVIEW5_PDF_AI.md`;
- `00_CONTINUIDADE_REPAROS_SJC.md`.

## Próxima etapa segura
1. não repetir deploy ou migration;
2. testar PDF real Review5;
3. testar IA real com anotação curta + fotos;
4. rodar regressão Corporate completa;
5. investigar os 24 itens pendentes sem limpar fila/dados;
6. acompanhar retenção/volume da telemetria antes de ampliar para outros aparelhos.

## Não fazer
- não usar código de suporte como senha;
- não criar shell/JavaScript remoto/editor remoto de localStorage;
- não enviar objetos comerciais completos;
- não habilitar ingestão silenciosamente;
- não remover/alterar Corporate API para acomodar Support;
- não repetir deploy/migration nem mesclar para `corporate-api-r1`/`main` automaticamente.
