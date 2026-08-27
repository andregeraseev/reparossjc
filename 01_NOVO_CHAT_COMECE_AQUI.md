# 01 — Novo chat: comece aqui

Use esta mensagem em uma nova conversa do ChatGPT:

> Abra o repositório `andregeraseev/reparossjc` na branch `corporate-api-r1` e confirme o HEAD atual antes de alterar qualquer coisa. Leia `00_CONTINUIDADE_CORPORATE_API_R1.md`, `01_NOVO_CHAT_COMECE_AQUI.md` e `DEPLOY_CORPORATE_API_PYTHONANYWHERE.md`. Depois abra `andregeraseev/reparossjc-wear-`, branch `v18.27-corporate-api-r1`, e leia `AGENTS.md`, `00_CONTINUIDADE_REPAROS_SJC.md` e `qa/v18.27/AUDITORIA_CORPORATE_API_R1.md`. O backend já está implantado no PythonAnywhere e o health público respondeu `ok: true`; não refaça o deploy do zero. A produção usa `/home/AndreGeraseev/reparossjc_corporate_api_r1`, com WSGI carregando o arquivo privado `~/.rsjc_corporate_env.py`. Nunca peça nem exponha os valores desse arquivo. A pasta antiga `/home/AndreGeraseev/reparossjc` foi preservada como rollback e contém personalizações locais do site; não use reset/clean destrutivo. A próxima ação é no app: instalar o artifact `9625535347`, configurar API/token diretamente no aparelho e executar o fluxo E2E Portal Amil ↔ app.

## Resumo operacional
- Backend branch: `corporate-api-r1`.
- Commit funcional usado no clone de deploy: `dd1ed7116ac18e1602cfd8b6a96f0cfcb1100c55`.
- API base: `https://www.reparossjc.online/api/corporate/v1`.
- Health público confirmado após Reload.
- Portal: `https://www.reparossjc.online/corporativo/login/`.
- Segredos: apenas em `/home/AndreGeraseev/.rsjc_corporate_env.py`, permissão 600.
- Instalação antiga: `/home/AndreGeraseev/reparossjc`.
- Instalação atual: `/home/AndreGeraseev/reparossjc_corporate_api_r1`.
- WSGI atual: `/var/www/www_reparossjc_online_wsgi.py`.
- Banco da nova instalação foi migrado; 8 testes corporate passaram; bootstrap Amil passou.

## Não fazer
- não colocar secrets no Git;
- não pedir token/senha/Django secret no chat;
- não rodar `git reset --hard` ou `git clean` na produção antes de comparar os deltas locais;
- não apagar a pasta antiga;
- não refazer migrations/bootstrap sem entender o estado atual;
- não promover automaticamente para `main`.

## Próximo passo
Trabalhar no E2E físico do app Android, não em novo deploy backend. O app correspondente está em `andregeraseev/reparossjc-wear-`, branch `v18.27-corporate-api-r1`, artifact `9625535347`, gate técnico final verde.
