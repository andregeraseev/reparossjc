# 01 — Novo chat: comece aqui

Use esta mensagem em uma nova conversa do ChatGPT:

> Abra `andregeraseev/reparossjc` na branch `corporate-api-r1` e confirme o HEAD atual antes de alterar qualquer coisa. Leia `00_CONTINUIDADE_CORPORATE_API_R1.md`, `01_NOVO_CHAT_COMECE_AQUI.md` e `DEPLOY_CORPORATE_API_PYTHONANYWHERE.md`. Depois abra o app `andregeraseev/reparossjc-wear-`, branch `v18.27-corporate-api-r1`, e leia `AGENTS.md`, `00_CONTINUIDADE_REPAROS_SJC.md`, `01_NOVO_CHAT_COMECE_AQUI.md` e `qa/v18.27/RELATORIO_CORPORATE_HARDENING1.md`. Continue exatamente do estado atual. O fluxo Portal Amil ↔ API ↔ Android já foi validado fisicamente até agendamento com a Hotfix2b. O backend Corporate API R1 Hardening1 já foi atualizado no PythonAnywhere e já recebeu Reload: `manage.py check` sem problemas, sem migrations novas, workspace `ws_d220bc64-2992-4c72-ab43-7d5c120c8946`, organização Amil `slug=amil`, `demo=False`. NÃO refaça o deploy backend do zero. O próximo passo é instalar no Android, por cima e sem desinstalar, o APK `ReparosSJC-mobile-v18.27-Corporate-API-R1-Hardening1.apk`, que já passou gate e upgrade Hotfix2b → Hardening1 no Android 16. Depois fazer um novo E2E completo, incluindo seleção explícita de horários, concorrência de slots e cenário stale. Nunca peça nem exponha secrets. Não promover automaticamente para `main`.

## Estado operacional
- Backend branch: `corporate-api-r1`.
- Hardening funcional/testado antes dos commits de documentação: `dda6ae0ff0b7b5e5ef1690b1d4c06799b9f28ab1`.
- CI backend: run `33068714283`, **success**, 17 testes.
- API: `https://www.reparossjc.online/api/corporate/v1`.
- Portal: `https://www.reparossjc.online/corporativo/login/`.
- Workspace: `ws_d220bc64-2992-4c72-ab43-7d5c120c8946`.
- Amil: `slug=amil`, `demo=False`.
- Produção: `/home/AndreGeraseev/reparossjc_corporate_api_r1`.
- Rollback preservado: `/home/AndreGeraseev/reparossjc`.
- WSGI: `/var/www/www_reparossjc_online_wsgi.py`.
- Secrets: `/home/AndreGeraseev/.rsjc_corporate_env.py`, permissão 600.

## Backend Hardening1 já LIVE
O usuário executou atualização com backup do banco e confirmou:

```text
System check identified no issues (0 silenced).
No migrations to apply.
Amil portal ready for user amil (updated)
=== CORPORATE HARDENING OK ===
workspace: ws_d220bc64-2992-4c72-ab43-7d5c120c8946
organizacao: Amil
slug: amil
demo: False
```

Depois fez Reload no PythonAnywhere e confirmou que ficou tudo certo.

## Regras que agora devem ser preservadas
- snapshot global de disponibilidade não auto-oferece horários a todos os chamados;
- oferta de horários é um subconjunto explícito por chamado;
- horários passados são descartados;
- escolha no portal reserva o slot e o retira de concorrentes;
- slot reservado não reaparece numa nova publicação;
- `_serverVersion` obsoleta retorna `409`;
- operador pode conscientemente limpar pedido obsoleto/reabrir;
- organização Amil não pode voltar para demo por upsert.

## App pareado
Repo: `andregeraseev/reparossjc-wear-`  
Branch: `v18.27-corporate-api-r1`  
Versão: 18.27 / 1827.

Hardening1 gate/build commit antes dos commits de documentação:
`b17c72354625f09862c0cbdc2997f219945c7cf7`

- run `33069438318`;
- job `98507603066`;
- success;
- artifact `9645288248`;
- digest `sha256:43387516a1583c5409f32f8a203fe64a3e14d664f0e2b557491eb19ca8d32eeb`.

O celular **ainda está na Hotfix2b**. Hardening1 ainda não foi instalado fisicamente depois do backend Reload.

## Próximo passo exato
1. Instalar Hardening1 por cima da Hotfix2b, sem desinstalar.
2. Confirmar dados/token e Online.
3. Novo chamado Amil deve nascer `AMIL-*`, sem `DEMO`.
4. Validar chamado → orçamento → aprovação.
5. No app escolher explicitamente alguns horários futuros para aquele chamado.
6. Portal deve ver somente os horários escolhidos.
7. Portal escolhe slot; app revalida e agenda.
8. Testar dois chamados concorrentes no mesmo slot.
9. Testar stale/ocupado com conflito seguro.

## Não fazer
- não refazer backend do zero;
- não voltar para `ws_reparos_sjc`;
- não voltar Amil para `amil-demo`/`demo=True`;
- não pedir token/senha/Django secret no chat;
- não usar `git reset --hard`/`git clean` na produção;
- não apagar a pasta antiga;
- não promover automaticamente para `main`.
