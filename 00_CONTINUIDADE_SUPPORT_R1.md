# 00 — Continuidade Support R1

**Atualizado em:** 28/08/2026 — Review3  
**Backend:** `andregeraseev/reparossjc`, branch `support-r1`  
**App:** `andregeraseev/reparossjc-wear-`, branch `v18.27-support-r1`

> Esta frente é isolada da Corporate API R1 que está funcionando em produção. **Não fazer deploy automático e não mesclar para `corporate-api-r1`/`main`.** O Support R1 é uma Central de Suporte interna e começa somente leitura/diagnóstico; nenhum comando remoto arbitrário foi criado.

## Estado atual
O backend Support R1 Review3 está implementado e com gate técnico verde.

- head funcional Review3: `69763e99f2d076cdb21fd83e186a506ae5667261`;
- workflow: `Test Reparos SJC Support R1`;
- run Review3: `33167859251`;
- job: `98837478461`;
- conclusão: **success**;
- GitGuardian no mesmo head: **success**;
- PR Draft: #2 `Support R1 Review3 — Central de Suporte interna`;
- **não implantado no PythonAnywhere**;
- `RSJC_SUPPORT_INGEST_ENABLED` permanece como kill switch e o default de produção é desligado.

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

Proteções Review2/Review3:
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
O candidato atual do app é **Support R1 Review3**, ainda em gate técnico no momento deste commit de documentação. A Review3 adiciona SHA-256 nativo na bridge Android com fallback WebCrypto e preserva toda a Review2: armazenamento privado de installation/token/consentimento, sem bootstrap silencioso, pacote offline v3 e safe rebind.

Consultar no app:
- `qa/v18.27/ARQUITETURA_SUPPORT_R1.md`;
- `qa/v18.27/RELATORIO_SUPPORT_R1_REVIEW3.md` quando presente;
- `00_CONTINUIDADE_REPAROS_SJC.md`.

## Próxima etapa segura
1. concluir gate do APK Review3;
2. não instalar/deployar automaticamente;
3. quando houver acompanhamento do usuário, implantar backend Support no PythonAnywhere **com ingestão desligada**;
4. migrar/check/reload e abrir `/suporte/`;
5. somente depois ativar ingestão e instalar um único APK Review3 para teste físico;
6. validar primeiro código real `RSJC-XXXX-XXXX`, diagnóstico manual e pacote offline;
7. só então avaliar expansão.

## Não fazer
- não usar código de suporte como senha;
- não criar shell/JavaScript remoto/editor remoto de localStorage;
- não enviar objetos comerciais completos;
- não habilitar ingestão silenciosamente;
- não remover/alterar Corporate API para acomodar Support;
- não mesclar nem implantar antes do teste físico/controlado.
