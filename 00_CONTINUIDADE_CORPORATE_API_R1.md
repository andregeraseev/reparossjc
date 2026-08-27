# 00 — Continuidade Corporate API R1

**Atualizado em:** 26/08/2026 após deploy real no PythonAnywhere  
**Repositório:** `andregeraseev/reparossjc`  
**Branch:** `corporate-api-r1`  
**Commit funcional usado no clone de deploy:** `dd1ed7116ac18e1602cfd8b6a96f0cfcb1100c55`  
**Site/API:** `https://www.reparossjc.online/`

> Este backend já está implantado em produção. Não refaça o deploy do zero e não substitua a instalação antiga sem necessidade. Preserve o rollback, os segredos fora do Git e as personalizações locais do site público.

## Leia nesta ordem
1. `00_CONTINUIDADE_CORPORATE_API_R1.md`
2. `01_NOVO_CHAT_COMECE_AQUI.md`
3. `DEPLOY_CORPORATE_API_PYTHONANYWHERE.md`
4. `corporate/urls.py`
5. `corporate/views.py`
6. `corporate/services.py`
7. `corporate/models.py`
8. `corporate/tests.py`
9. `.github/workflows/test-corporate-api-r1.yml`
10. no app Android: branch `v18.27-corporate-api-r1`, `00_CONTINUIDADE_REPAROS_SJC.md` e `qa/v18.27/AUDITORIA_CORPORATE_API_R1.md`.

## Estado de produção
O deploy foi feito em uma nova pasta isolada no PythonAnywhere.

- instalação antiga preservada: `/home/AndreGeraseev/reparossjc`;
- nova instalação em produção: `/home/AndreGeraseev/reparossjc_corporate_api_r1`;
- branch clonada: `corporate-api-r1`;
- commit clonado no momento do deploy: `dd1ed7116ac18e1602cfd8b6a96f0cfcb1100c55`;
- WSGI: `/var/www/www_reparossjc_online_wsgi.py`;
- `project_home` atual: `/home/AndreGeraseev/reparossjc_corporate_api_r1`;
- WSGI carrega `/home/AndreGeraseev/.rsjc_corporate_env.py` antes de `DJANGO_SETTINGS_MODULE=config.settings`;
- backup do WSGI anterior foi criado antes da virada.

A pasta antiga não foi apagada e serve como rollback rápido.

## Segredos
Os segredos de produção ficam somente em:

`/home/AndreGeraseev/.rsjc_corporate_env.py`

Permissão confirmada: `600`.

Variáveis presentes/esperadas:
- `DJANGO_SECRET_KEY`;
- `DJANGO_DEBUG=0`;
- `DJANGO_ALLOWED_HOSTS`;
- `DJANGO_CSRF_TRUSTED_ORIGINS`;
- `DJANGO_SECURE_SSL_REDIRECT=1`;
- `DJANGO_HSTS_SECONDS=31536000`;
- `RSJC_WORKSPACE_ID=ws_reparos_sjc`;
- `RSJC_CORPORATE_OPERATOR_TOKEN`;
- `RSJC_AMIL_USERNAME`;
- `RSJC_AMIL_PASSWORD`.

**Nunca** gravar esses valores no GitHub, issue, log, documentação ou chat. Em particular, não pedir ao usuário que cole token, senha Amil ou `DJANGO_SECRET_KEY` na conversa.

## Banco e testes executados
Na instalação isolada foram executados:

- `python manage.py check` → OK;
- `python manage.py makemigrations --check --dry-run` → `No changes detected`;
- `python manage.py migrate --noinput` → migrations de admin/auth/contenttypes/corporate/sessions OK;
- `python manage.py test corporate -v 1` → 8 testes OK;
- `python manage.py bootstrap_corporate_demo` → organização Amil + usuário portal criados.

### Nota sobre HTTPS nos testes
A primeira execução dos testes retornou 301 em 7 testes porque o ambiente privado de produção força HTTPS. Os testes foram reexecutados com `DJANGO_SECURE_SSL_REDIRECT=0` e `DJANGO_HSTS_SECONDS=0` **somente no processo de teste**, igual ao CI. Todos os 8 testes passaram. Não desativar HTTPS/HSTS em produção.

## Smoke tests antes da virada
Com Django Test Client e host `reparossjc.online`:
- `/api/corporate/v1/health` → 200;
- login do portal → True;
- `/corporativo/` autenticado → 200.

Depois de preservar o site público:
- `/` → 200;
- `/seguranca` → 200;
- `/api/corporate/v1/health` → 200;
- `/corporativo/` → 200.

## Produção pública confirmada
Após alterar o WSGI e fazer Reload, o usuário confirmou:

`https://www.reparossjc.online/api/corporate/v1/health`

retornando:

```json
{"ok": true, "service": "reparossjc-corporate", "version": 1, "time": "2026-08-27T00:21:43.202163+00:00"}
```

Logo a API pública Corporate R1 está **online**.

## Rotas
- `/api/corporate/v1/health`;
- `/api/corporate/v1/operator/requests`;
- `/api/corporate/v1/operator/requests/<request_id>`;
- `/api/corporate/v1/operator/availability`;
- `/api/corporate/v1/portal/requests`;
- `/corporativo/login/`;
- `/corporativo/logout/`;
- `/corporativo/`;
- `/corporativo/chamados/novo/`;
- `/corporativo/chamados/<request_id>/aprovar/`;
- `/corporativo/chamados/<request_id>/agendar/`.

## Regras arquiteturais
- backend é autoritativo para estado/concurrency;
- portal é autenticado e limitado à organização;
- portal não recebe agenda privada;
- disponibilidade pública contém somente janelas seguras;
- servidor revalida horário antes de aceitar solicitação;
- agendamento final continua confirmado pelo operador no app;
- contrato `ReparosSJC_Corporate_Request` v1;
- idempotência por workspace + organização/parceiro + externalRequestId;
- Amil é organização inicial/demo; estrutura é genérica para outras empresas.

## Personalizações locais do site público — IMPORTANTE
Antes do deploy, a instalação antiga estava no commit `d98590addc18929cf7478def49e24cb74b34c389` da `main`, porém continha alterações locais não commitadas:
- `config/settings.py`;
- `config/urls.py`;
- `meu_site/templates/home.html`;
- `meu_site/views.py`;
- `meu_site/static/`;
- `meu_site/templates/seguranca.html`;
- `static/favicon.ico`;
- além de um `db.sqlite3.backup-20260826-222515` de 0 bytes e `.views.py.swp`.

Foi criado stash `backup-pre-corporate-api-r1-20260826` e depois aplicado com `git stash apply`; portanto o stash deve continuar disponível na pasta antiga.

Para preservar o site durante o deploy, foram copiados da pasta antiga para a nova:
- `home.html`;
- `views.py`;
- `seguranca.html`;
- `meu_site/static/`;
- `static/favicon.ico`.

`config/urls.py` da nova instalação foi mesclado localmente para manter:
- `path("", home, name="home")`;
- `path("seguranca", seguranca, name="seguranca")`;
- `path("", include("corporate.urls"))`.

A configuração de segurança antiga também usava `django-csp`. No PythonAnywhere está instalada versão compatível com django-csp 4.x, então as diretivas antigas foram convertidas localmente para `CONTENT_SECURITY_POLICY = {"DIRECTIVES": ...}` e `manage.py check` passou.

### Consequência
A produção contém deltas locais do site que podem não existir byte a byte nesta branch GitHub. **Não executar `git reset --hard`, `git clean`, reclone sobre a pasta de produção ou checkout destrutivo antes de comparar os arquivos locais.** Esta documentação registra o estado, mas não substitui uma futura sincronização exata dos arquivos locais de produção com o Git.

## Próxima ação do projeto
O backend não precisa de novo deploy agora. A próxima ação está no app Android:

- repo `andregeraseev/reparossjc-wear-`;
- branch `v18.27-corporate-api-r1`;
- artifact `9625535347`;
- instalar por cima, sem desinstalar;
- API `https://www.reparossjc.online/api/corporate/v1`;
- token obtido apenas no terminal PythonAnywhere e colado diretamente no app;
- confirmar Online;
- executar E2E real Portal Amil → app → orçamento → aprovação → disponibilidade → horário → confirmação.

## Rollback
Se o site quebrar por alteração futura:
1. não apagar a nova pasta;
2. restaurar o backup do WSGI ou voltar `project_home` para `/home/AndreGeraseev/reparossjc`;
3. Reload na aba Web;
4. investigar offline antes de nova virada.

Não usar rollback como desculpa para apagar bancos/arquivos ou limpar a instalação nova.
