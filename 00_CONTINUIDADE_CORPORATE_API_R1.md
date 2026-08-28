# 00 — Continuidade Backend Reparos SJC — Corporate + Support R1

**Atualizado em:** 28/08/2026

**Repositório:** `andregeraseev/reparossjc`

**Base Corporate:** branch `corporate-api-r1`

**Código Support:** branch `support-r1`

**Site:** `https://www.reparossjc.online/`

> A produção Corporate API R1 Hardening1 continua funcionando. A Central Support R1 Review4 foi implantada de forma controlada em 28/08/2026, na mesma instalação isolada, e está LIVE com ingestão habilitada. Não refaça o Corporate, não repita o deploy Support e não altere o kill switch sem uma nova etapa controlada acompanhada pelo usuário.

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

# 2. Support R1 backend — LIVE
Branch: `support-r1`.

Código implantado no PythonAnywhere:
- diretório: `/home/AndreGeraseev/reparossjc_corporate_api_r1`;
- branch local de implantação: `deploy-support-r1-20260828`;
- commit implantado: `4a4ca987484b4480c92ad56f91ef413902e98284`;
- base funcional Review4: `ed6c6202fd7cefe70127d47c476a29456a74c255`.

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

Estado confirmado após Reload e smoke final: **habilitado (`True`)**.

### Implantação validada em 28/08/2026
- backup pré-Support: `db.sqlite3.backup-pre-support-20260828-132054`;
- SHA-256 do banco e do backup no momento da cópia: `3629e5de6709b690f7f8ac681bc92141eaa0e1c7228171e0ec4906f405ec2640`;
- migration aplicada: `support_center.0001_initial`;
- `manage.py check`: sem problemas;
- `makemigrations --check --dry-run`: sem mudanças;
- `PRAGMA integrity_check`: `ok`;
- Central `/suporte/`: protegida e acessível por usuário dedicado `is_staff`;
- smoke final: `/`, `/seguranca`, health Corporate, health Support e login Corporate retornaram 200;
- `/suporte/` sem autenticação retornou 302 para login;
- bootstrap vazio retornou 400, confirmando endpoint ativo e validando payload.

### Piloto físico confirmado
- Review5 instalada no Samsung SM-S911B, app 18.27/1827, Android 16, sem desinstalar;
- código da conta piloto: `RSJC-MGHL-U85Q` — localizador, não senha;
- importação offline, bootstrap online, envio manual e compartilhamento contínuo foram validados;
- último estado observado: 42 eventos e 3 snapshots recebidos;
- a fonte offline e o aparelho online aparecem como dois registros, comportamento esperado; não excluir o histórico offline;
- fila local permanece com 24 itens pendentes e armazenamento com 9,5% livre; não limpar dados/fila antes do diagnóstico.

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

# 4. Próxima ação
Não mexer novamente na implantação Support. Prosseguir pelo app, em etapas curtas:
1. testar fisicamente um PDF real com títulos longos e os novos cabeçalhos;
2. testar IA com anotação curta + fotos, sem aceitar fatos críticos inventados;
3. executar regressão Corporate completa;
4. depois investigar, sem apagar, os 24 itens pendentes da fila local;
5. liberar espaço no aparelho com cuidado, preservando dados do app.

## Frente futura separada — múltiplas lojas/provedores
- branch: `corporate-provider-routing-r1`;
- commit remoto: `818e139bf10b2646d8f28c73ac7d0ecc0c8a03b1`;
- CI run `33174687493`: **success**, 44 testes;
- permite que cada loja veja apenas provedores autorizados e escolha exatamente um destinatário;
- **não está implantada nem mesclada** em `support-r1`, `corporate-api-r1` ou produção.

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
Se a implantação Support causar problema:
- primeiro definir `RSJC_SUPPORT_INGEST_ENABLED=0` no ambiente privado e fazer Reload;
- não apagar banco, fontes offline, pasta ativa ou backups;
- se necessário restaurar a configuração/WSGI Corporate anterior;
- investigar offline preservando evidências.

Rollback não autoriza limpeza destrutiva.
