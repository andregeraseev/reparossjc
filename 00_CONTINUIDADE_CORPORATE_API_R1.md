# 00 — Continuidade Corporate API R1

**Atualizado em:** 27/08/2026 após E2E real e Hardening1 em produção  
**Repositório:** `andregeraseev/reparossjc`  
**Branch:** `corporate-api-r1`  
**Site/API:** `https://www.reparossjc.online/`

> Este backend já está implantado em produção e o Corporate API R1 Hardening1 já foi atualizado/recarregado no PythonAnywhere. Não refaça o deploy do zero, não substitua a instalação antiga e não reverta o workspace/Amil para os valores antigos. Preserve rollback, segredos fora do Git e personalizações locais do site público.

## Leia nesta ordem
1. `00_CONTINUIDADE_CORPORATE_API_R1.md`
2. `01_NOVO_CHAT_COMECE_AQUI.md`
3. `DEPLOY_CORPORATE_API_PYTHONANYWHERE.md`
4. `corporate/views.py`
5. `corporate/services.py`
6. `corporate/models.py`
7. `corporate/tests.py`
8. `corporate/test_availability_after_approval.py`
9. `.github/workflows/test-corporate-api-r1.yml`
10. no app Android: branch `v18.27-corporate-api-r1`, `00_CONTINUIDADE_REPAROS_SJC.md` e `qa/v18.27/RELATORIO_CORPORATE_HARDENING1.md`.

# Estado de produção
Deploy isolado no PythonAnywhere:
- instalação antiga preservada: `/home/AndreGeraseev/reparossjc`;
- instalação atual: `/home/AndreGeraseev/reparossjc_corporate_api_r1`;
- WSGI: `/var/www/www_reparossjc_online_wsgi.py`;
- `project_home`: `/home/AndreGeraseev/reparossjc_corporate_api_r1`;
- WSGI carrega `/home/AndreGeraseev/.rsjc_corporate_env.py` antes do Django;
- backup do WSGI anterior existe;
- pasta antiga não foi apagada e continua sendo rollback.

## Segredos
Segredos de produção ficam somente em:

`/home/AndreGeraseev/.rsjc_corporate_env.py`

Permissão: `600`.

Nunca gravar valores secretos no Git/log/docs/chat e nunca pedir que o usuário cole:
- `DJANGO_SECRET_KEY`;
- `RSJC_CORPORATE_OPERATOR_TOKEN`;
- `RSJC_AMIL_PASSWORD`;
- keystore/senhas de assinatura;
- outras Secrets.

### Valores não secretos confirmados
Workspace canônico de produção:

`ws_d220bc64-2992-4c72-ab43-7d5c120c8946`

Organização Amil:
- `slug=amil`;
- `demo=False`.

O valor antigo `ws_reparos_sjc` causou cenário **Online mas zero chamados** e não deve voltar como fallback silencioso de produção.

# E2E real já validado
O fluxo Portal Amil ↔ API ↔ Android foi testado fisicamente até agendamento.

Chamado legado de teste: `AMIL-DEMO-20260826-222945`.

Confirmado:
- portal criou chamado;
- app recebeu chamado e campos;
- app criou/vinculou orçamento;
- orçamento foi enviado via POST real e apareceu no portal;
- aprovação avançou o fluxo;
- disponibilidade chegou ao backend;
- após correções, horários chegaram ao portal;
- fluxo avançou até agendamento.

Não voltar para JSON manual como fluxo principal.

# Bugs de produção encontrados e corrigidos
## CORS health/WebView
`/health` foi ajustado para o Origin do WebView Android (`file://`/null), resolvendo `Failed to fetch` com backend saudável.

## Workspace divergente
Produção criava chamados no workspace antigo e o app consultava o UUID maduro. Foi corrigido o env e migrado o chamado existente. O usuário confirmou que o chamado passou a aparecer no celular.

## Prefixo demo
O bootstrap antigo deixava Amil como `amil-demo`, `demo=True`, gerando números `AMIL-DEMO-*`. O app Hotfix2b também foi corrigido para não bloquear um chamado real apenas pelo prefixo legado.

## Disponibilidade não ligada ao chamado
Diagnóstico mostrou snapshot com janelas e chamado aprovado sem `proposed_windows`. A correção inicial permitiu avançar até agendamento. O Hardening1 substituiu esse acoplamento automático por **oferta explícita por chamado**.

# Corporate API R1 Hardening1
Código funcional/testado antes dos commits de documentação:

`dda6ae0ff0b7b5e5ef1690b1d4c06799b9f28ab1`

CI autoritativo:
- workflow `Test Reparos SJC Corporate API R1`;
- run `33068714283`;
- conclusão **success**;
- 17 testes corporate passaram;
- `manage.py check` passou;
- `makemigrations --check --dry-run` sem deltas;
- migrations em CI OK;
- gate estático/security OK.

## Regras endurecidas
### Oferta explícita
Publicar o snapshot global de disponibilidade não move automaticamente todo chamado aprovado para `waiting_schedule`.

Para oferecer horários a um chamado, o operador/app envia explicitamente um subconjunto de janelas seguras para aquele chamado.

### Horários passados
Backend descarta janelas passadas. App Hardening1 também filtra localmente.

### Reserva e concorrência
Quando o portal escolhe um horário:
- o slot é reservado para o chamado;
- sai do snapshot disponível;
- é removido das opções de outros chamados concorrentes;
- nova publicação não pode reintroduzir silenciosamente o slot enquanto reservado.

### Estado obsoleto
Contrato com `_serverVersion` obsoleta retorna conflito `409` em vez de sobrescrever estado novo do servidor.

### Reabertura segura
Operador pode limpar um `schedule_request` obsoleto e republicar o slot quando o fluxo é conscientemente reaberto.

### Organização production-safe
Uma organização já promovida para produção não pode ser rebaixada pelo upsert do operador para `demo=True`/`amil-demo`.

# Atualização de produção Hardening1 — CONCLUÍDA
O usuário executou update do clone de produção com backup SQLite prévio.

Saída confirmada:

```text
System check identified no issues (0 silenced).
Operations to perform:
  Apply all migrations: admin, auth, contenttypes, corporate, sessions
Running migrations:
  No migrations to apply.
Amil portal ready for user amil (updated)
=== CORPORATE HARDENING OK ===
workspace: ws_d220bc64-2992-4c72-ab43-7d5c120c8946
organizacao: Amil
slug: amil
demo: False
```

Depois o usuário fez **Reload** na aba Web do PythonAnywhere e confirmou `Tudo certo`.

Portanto o backend Hardening1 está **LIVE**. Não há ação de deploy backend pendente antes do próximo teste físico do app.

# App correspondente
Repo: `andregeraseev/reparossjc-wear-`  
Branch: `v18.27-corporate-api-r1`  
Versão: `18.27` / `1827`.

App Hardening1 build/gate commit antes dos commits de documentação:
`b17c72354625f09862c0cbdc2997f219945c7cf7`

Workflow:
`Build Reparos SJC 18.27 Corporate API R1 Hardening1`

- run `33069438318`;
- job `98507603066`;
- success;
- artifact `9645288248`;
- artifact `ReparosSJC-v18.27-Corporate-API-R1-Hardening1`;
- digest `sha256:43387516a1583c5409f32f8a203fe64a3e14d664f0e2b557491eb19ca8d32eeb`.

**Estado físico atual:** o celular ainda está na Hotfix2b. O Hardening1 está pronto e passou teste de upgrade Hotfix2b → Hardening1 no Android 16, mas ainda não foi instalado pelo usuário depois do Reload do backend.

# Próxima ação do projeto
Não mexer no backend antes do teste salvo alguma falha real.

1. Instalar o APK mobile Hardening1 por cima da Hotfix2b, sem desinstalar.
2. Confirmar app Online e dados/token preservados.
3. Criar novo chamado real no Portal Amil; número esperado agora `AMIL-*`, não `AMIL-DEMO-*`.
4. E2E: chamado → orçamento → aprovação → seleção explícita de horários → portal escolhe → app revalida → agendamento maduro.
5. Testar dois chamados concorrendo pelo mesmo slot.
6. Testar estado stale/ocupado e esperar conflito seguro/republicação, nunca dupla marcação.

# Personalizações locais do site público — IMPORTANTE
A instalação antiga contém alterações locais não commitadas e stash `backup-pre-corporate-api-r1-20260826`. O deploy isolado preservou home, `/seguranca`, estáticos, favicon e CSP compatível com django-csp 4.x.

**Não executar** `git reset --hard`, `git clean`, reclone destrutivo, apagar pasta antiga ou sobrescrever arquivos de produção sem comparar deltas locais.

# Rollback
Se site quebrar por alteração futura:
1. não apagar a nova pasta;
2. restaurar WSGI anterior ou apontar `project_home` para `/home/AndreGeraseev/reparossjc`;
3. Reload;
4. investigar offline antes de nova virada.

Rollback não autoriza apagar banco/arquivos nem limpar a instalação atual.
