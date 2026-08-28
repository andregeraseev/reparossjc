# 01 — Novo chat: comece aqui

Use esta mensagem em uma nova conversa do ChatGPT:

> Abra `andregeraseev/reparossjc` e confirme primeiro o HEAD das branches `corporate-api-r1` e `support-r1`. Leia `00_CONTINUIDADE_CORPORATE_API_R1.md`, `00_CONTINUIDADE_SUPPORT_R1.md`, `01_NOVO_CHAT_COMECE_AQUI.md` e `DEPLOY_SUPPORT_R1_PYTHONANYWHERE.md`. Depois abra o app `andregeraseev/reparossjc-wear-`, branch `v18.27-support-r1`, e leia `AGENTS.md`, `00_CONTINUIDADE_REPAROS_SJC.md`, `01_NOVO_CHAT_COMECE_AQUI.md`, `qa/v18.27/RELATORIO_SUPPORT_R1_REVIEW5_PDF_AI.md` e `qa/v18.27/ARQUITETURA_SUPPORT_R1.md`. Continue exatamente do estado atual; não recomece. O Corporate API R1 Hardening1 e a Central Support R1 Review4 estão LIVE na instalação `/home/AndreGeraseev/reparossjc_corporate_api_r1`. O código Support implantado é `4a4ca987484b4480c92ad56f91ef413902e98284`, na branch local `deploy-support-r1-20260828`; migration `support_center.0001_initial`, smoke Corporate+Support e integridade SQLite passaram. A ingestão Support está habilitada. O app Review5 foi instalado sem desinstalar no Samsung SM-S911B/Android 16 e vinculou a conta `RSJC-MGHL-U85Q`; importação offline, bootstrap online, envio manual e compartilhamento contínuo funcionaram. Não repetir deploy nem recriar Review5. Ainda faltam teste físico real de PDF/IA e regressão Corporate completa. Há 24 itens na fila local e somente 9,5% de espaço livre; não limpar dados/fila. A branch futura `corporate-provider-routing-r1` está verde, mas NÃO foi implantada ou mesclada. Nunca peça/exponha secrets e não promova automaticamente para `main`/`corporate-api-r1`.

## Estado operacional
### Corporate — LIVE
- branch: `corporate-api-r1`;
- workspace: `ws_d220bc64-2992-4c72-ab43-7d5c120c8946`;
- Amil: `slug=amil`, `demo=False`;
- produção: `/home/AndreGeraseev/reparossjc_corporate_api_r1`;
- rollback: `/home/AndreGeraseev/reparossjc`;
- WSGI: `/var/www/www_reparossjc_online_wsgi.py`;
- env privado: `/home/AndreGeraseev/.rsjc_corporate_env.py`, 600.

### Support backend — LIVE
- branch: `support-r1`;
- commit implantado: `4a4ca987484b4480c92ad56f91ef413902e98284`;
- branch local de produção: `deploy-support-r1-20260828`;
- CI run `33168497303`: **success**;
- GitGuardian: **success**;
- Central `/suporte/` protegida por `is_staff`;
- ingestão com kill switch `RSJC_SUPPORT_INGEST_ENABLED`;
- consentimento contínuo imposto também no servidor;
- identidade/token armazenados como hashes;
- telemetria sanitizada, vocabulário técnico fechado e retenção limitada;
- importação de diagnóstico offline v3;
- sem comandos remotos arbitrários.
- migration `support_center.0001_initial` aplicada;
- ingestão ativa (`True`);
- smoke final e integridade SQLite aprovados.

### App — Review5 atual
- repo: `andregeraseev/reparossjc-wear-`;
- branch: `v18.27-support-r1`;
- versão: `18.27` / `1827`;
- artifact `ReparosSJC-v18.27-Support-R1-Review5-PDF-AI`;
- artifact ID `9685644132`;
- run `33170755436`: **success**;
- mobile SHA-256 `5bfb7dba3a945724ae6dd9974db44cc42b538c6778b9c5632f363d9b76d7243f`.

## Próximo passo exato
1. Não repetir o deploy Support.
2. Testar PDF real com títulos longos e os novos cabeçalhos.
3. Testar IA com nota curta + fotos, sem aceitar fatos críticos inventados.
4. Rodar regressão Corporate completa.
5. Depois investigar os 24 itens pendentes da fila, sem apagar dados.
6. Liberar espaço no aparelho com cuidado; estado observado: 9,5% livre.

## Não fazer
- não recriar Review5;
- não refazer Corporate;
- não voltar workspace/Amil aos valores demo;
- não desinstalar o app para atualizar;
- não usar `git reset --hard`/`git clean` em produção;
- não apagar rollback;
- não expor secrets;
- não desligar/ligar Support ingest sem nova etapa controlada;
- não promover automaticamente para `main` ou `corporate-api-r1`.
