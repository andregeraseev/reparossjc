# 00 — Continuidade Backend Reparos SJC — Corporate + Support R1

**Atualizado em:** 28/08/2026  
**Repositório:** `andregeraseev/reparossjc`  
**Produção Corporate:** branch `corporate-api-r1`  
**Desenvolvimento Support:** branch `support-r1`  
**Site:** `https://www.reparossjc.online/`

> A produção Corporate API R1 Hardening1 já está implantada e funcionando. A branch `support-r1` é uma evolução isolada para a Central de Suporte e **NÃO está implantada em produção**. Não refaça o Corporate, não troque a produção de branch automaticamente e não habilite ingestão Support sem etapa controlada acompanhada pelo usuário.

## Leia nesta ordem nesta branch
1. `00_CONTINUIDADE_CORPORATE_API_R1.md`
2. `01_NOVO_CHAT_COMECE_AQUI.md`
3. arquivos `support_center/` e testes Support
4. `.github/workflows/` relacionados a Support
5. para contexto Corporate preservado: `corporate/views.py`, `corporate/services.py`, `corporate/models.py`, testes Corporate e `DEPLOY_CORPORATE_API_PYTHONANYWHERE.md`
6. no app: `andregeraseev/reparossjc-wear-`, branch `v18.27-support-r1`, ler `AGENTS.md`, `00_CONTINUIDADE_REPAROS_SJC.md` e `qa/v18.27/RELATORIO_SUPPORT_R1_REVIEW5_PDF_AI.md`.

# 1. Corporate API R1 — LIVE e preservar
Deploy atual no PythonAnywhere:
- instalação antiga/rollback: `/home/AndreGeraseev/reparossjc`;
- instalação Corporate atual: `/home/AndreGeraseev/reparossjc_corporate_api_r1`;
- WSGI: `/var/www/www_reparossjc_online_wsgi.py`;
- `project_home`: `/home/AndreGeraseev/reparossjc_corporate_api_r1`;
- env privado: `/home/AndreGeraseev/.rsjc_corporate_env.py`, permissão 600.

Workspace canônico:
`ws_d220bc64-2992-4c72-ab43-7d5c120c8946`.

Amil em produção:
- `slug=amil`;
- `demo=False`.

O fluxo Portal Amil ↔ API ↔ Android já foi validado fisicamente até agendamento. O Corporate Hardening1 adicionou oferta explícita de horários, descarte de horários passados, reserva/concorrência de slots e conflito seguro por `_serverVersion` obsoleta.

Não voltar para `ws_reparos_sjc`, `amil-demo` ou `demo=True`.

Não executar `git reset --hard`, `git clean`, reclone destrutivo, apagar rollback ou sobrescrever personalizações locais sem comparar deltas.

# 2. Support R1 backend — estado atual
Branch: `support-r1`.

HEAD funcional/testado antes de futuros commits de documentação:
`ed6c6202fd7cefe70127d47c476a29456a74c255`.

CI autoritativo:
- run `33168497303`;
- conclusão **success**;
- GitGuardian **success**.

## Objetivo
Central interna `/suporte/` para a equipe localizar contas por código `RSJC-XXXX-XXXX` e diagnosticar:
- aparelhos;
- versão/app/Android;
- saúde e armazenamento;
- eventos técnicos sanitizados;
- erros agrupados;
- snapshots;
- sincronização/backup;
- histórico/timeline;
- pacote de diagnóstico offline;
- chamados internos de suporte.

A Central é `is_staff`, auditada e somente leitura do aparelho nesta fase.

## Segurança/privacidade implementadas
- código `RSJC-XXXX-XXXX` é localizador, não autenticação;
- identidade da conta Support é independente do workspace comercial;
- servidor persiste hash da identidade e hash do token, não valores brutos;
- bootstrap repetido não pode substituir vínculo sem autenticação adequada;
- consentimento é por aparelho;
- snapshot não pode alterar consentimento;
- ingestão `continuous` sem consentimento registrado no servidor é rejeitada com 403;
- ingestão `manual`, disparada pelo usuário, permanece permitida;
- telemetria aceita somente dados estruturados/sanitizados;
- `action/entity` têm vocabulário técnico fechado;
- textos livres sensíveis como `message`, `stack`, `reason`, nomes, endereços, telefones, fotos e objetos comerciais completos não devem ser persistidos;
- limites de payload/rate limiting básico;
- retenção de eventos/snapshots/auditoria;
- pacote offline v3 sanitizado e importador com sanitização no servidor;
- sem shell, JS remoto, localStorage remoto ou comandos arbitrários.

## Kill switch
`RSJC_SUPPORT_INGEST_ENABLED`.

Quando houver deploy, produção deve começar com ingestão **DESLIGADA**.

# 3. App pareado atual — Support R1 Review5
Repo: `andregeraseev/reparossjc-wear-`  
Branch: `v18.27-support-r1`  
Versão: `18.27` / `1827`.

A Review5 do app foi criada após inspeção de um PDF real e já está verde. Ela é uma mudança **app-only** sobre o Support R1 Review4; não exige nova alteração backend antes do teste físico.

Workflow Review5:
- run `33170755436`;
- job `98847045795`;
- **success**;
- artifact ID `9685644132`;
- artifact `ReparosSJC-v18.27-Support-R1-Review5-PDF-AI`;
- mobile SHA-256 `5bfb7dba3a945724ae6dd9974db44cc42b538c6778b9c5632f363d9b76d7243f`.

Ela corrige:
- títulos de fotos do PDF que invadiam colunas;
- cabeçalhos `REGISTRO TÉCNICO`/`ENCERRAMENTO` visualmente desconexos;
- regra de IA excessivamente conservadora para anotações curtas de serviço executado.

Consultar o relatório no repo do app antes de qualquer mudança.

# 4. Próxima ação — NÃO é deploy backend ainda
Primeiro concluir a validação física do app Review5:
1. confirmar qual build está instalado no aparelho;
2. validar uma atualização segura da base física real para Review5, sem desinstalar;
3. testar PDF real e IA com anotação curta + fotos;
4. regressão Corporate completa;
5. regressão local da área Support.

Somente depois, com aprovação física, preparar deploy Support controlado:
1. backup SQLite da produção;
2. revisar diff `corporate-api-r1 → support-r1`;
3. `manage.py check` e migrations;
4. manter Corporate e site público intactos;
5. abrir `/suporte/` com login `is_staff`;
6. manter `RSJC_SUPPORT_INGEST_ENABLED` desligado;
7. validar telas e permissões;
8. habilitar ingestão somente para um aparelho de teste;
9. observar logs/volume/privacidade antes de ampliar.

# 5. Secrets — nunca expor
Nunca gravar em Git/log/docs/chat nem pedir ao usuário para colar:
- `DJANGO_SECRET_KEY`;
- `RSJC_CORPORATE_OPERATOR_TOKEN`;
- senha Amil;
- Support device token;
- keystore/senhas de assinatura;
- `OPENAI_API_KEY`;
- outras Secrets.

# 6. Rollback
Se uma futura implantação Support causar problema:
- não apagar a pasta nova nem banco;
- restaurar a configuração/WSGI Corporate anterior;
- Reload;
- investigar offline;
- preservar a pasta antiga e backups.

Rollback não autoriza limpeza destrutiva.
