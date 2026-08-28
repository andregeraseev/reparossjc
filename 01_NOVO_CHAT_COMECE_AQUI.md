# 01 — Novo chat: comece aqui

Use esta mensagem em uma nova conversa do ChatGPT:

> Abra `andregeraseev/reparossjc` e confirme primeiro o estado das branches `corporate-api-r1` e `support-r1`. A produção Corporate continua em `corporate-api-r1`; a Central de Suporte está em desenvolvimento isolado na `support-r1`. Trabalhe na `support-r1` somente se a tarefa for Support. Leia `00_CONTINUIDADE_CORPORATE_API_R1.md` e `01_NOVO_CHAT_COMECE_AQUI.md` antes de alterar qualquer coisa. Depois abra o app `andregeraseev/reparossjc-wear-`, branch `v18.27-support-r1`, e leia `AGENTS.md`, `00_CONTINUIDADE_REPAROS_SJC.md`, `01_NOVO_CHAT_COMECE_AQUI.md`, `qa/v18.27/RELATORIO_SUPPORT_R1_REVIEW5_PDF_AI.md` e `qa/v18.27/ARQUITETURA_SUPPORT_R1.md`. Continue exatamente do estado atual; não recomece. O Corporate API R1 Hardening1 já está LIVE no PythonAnywhere e o fluxo Portal Amil ↔ API ↔ Android já funcionou fisicamente até agendamento. NÃO refaça o Corporate. O backend Support Review4 está codificado e com gate verde, mas NÃO está implantado em produção. HEAD funcional/testado conhecido `ed6c6202fd7cefe70127d47c476a29456a74c255`, run `33168497303` success + GitGuardian success. O servidor já impõe consentimento: modo `continuous` sem consentimento do aparelho recebe 403, enquanto envio `manual` solicitado pelo usuário continua permitido. O app atual é Support R1 Review5 PDF + IA, versão 18.27/1827; gate `33170755436` success, artifact ID `9685644132`, mobile SHA-256 `5bfb7dba3a945724ae6dd9974db44cc42b538c6778b9c5632f363d9b76d7243f`. Review5 é app-only e já corrigiu overflow de títulos fotográficos, design de `REGISTRO TÉCNICO`/`ENCERRAMENTO` e IA excessivamente conservadora para notas curtas. Não recrie Review5. A próxima etapa é primeiro validar fisicamente Review5 e a atualização a partir da base que realmente está instalada no celular; não presuma que Review4 já está instalada e nunca desinstale. Só depois preparar deploy Support no PythonAnywhere com backup e `RSJC_SUPPORT_INGEST_ENABLED` desligado inicialmente. Nunca peça/exponha secrets e não faça merge/deploy automático.

## Estado operacional
### Corporate — LIVE
- branch: `corporate-api-r1`;
- workspace: `ws_d220bc64-2992-4c72-ab43-7d5c120c8946`;
- Amil: `slug=amil`, `demo=False`;
- produção: `/home/AndreGeraseev/reparossjc_corporate_api_r1`;
- rollback: `/home/AndreGeraseev/reparossjc`;
- WSGI: `/var/www/www_reparossjc_online_wsgi.py`;
- env privado: `/home/AndreGeraseev/.rsjc_corporate_env.py`, 600.

### Support backend — pronto para teste, NÃO LIVE
- branch: `support-r1`;
- HEAD funcional/testado conhecido: `ed6c6202fd7cefe70127d47c476a29456a74c255`;
- CI run `33168497303`: **success**;
- GitGuardian: **success**;
- Central `/suporte/` protegida por `is_staff`;
- ingestão com kill switch `RSJC_SUPPORT_INGEST_ENABLED`;
- consentimento contínuo imposto também no servidor;
- identidade/token armazenados como hashes;
- telemetria sanitizada, vocabulário técnico fechado e retenção limitada;
- importação de diagnóstico offline v3;
- sem comandos remotos arbitrários.

### App — Review5 atual
- repo: `andregeraseev/reparossjc-wear-`;
- branch: `v18.27-support-r1`;
- versão: `18.27` / `1827`;
- artifact `ReparosSJC-v18.27-Support-R1-Review5-PDF-AI`;
- artifact ID `9685644132`;
- run `33170755436`: **success**;
- mobile SHA-256 `5bfb7dba3a945724ae6dd9974db44cc42b538c6778b9c5632f363d9b76d7243f`.

## Próximo passo exato
1. Não mexer no backend de produção ainda.
2. Confirmar qual APK/build está no aparelho físico.
3. Se a base instalada for anterior à Review4, fazer gate `base física → Review5` com `adb install -r` ou definir cadeia segura.
4. Instalar Review5 sem desinstalar.
5. Testar PDF com títulos longos + novos cabeçalhos.
6. Testar IA com nota curta + fotos: texto deve ficar mais completo, mas sem inventar diagnóstico/teste/vazamento/medidas/material/modelo/etc.
7. Rodar regressão Corporate.
8. Depois, e somente depois, planejar deploy `support-r1` com backup, checks/migrations e ingestão desligada primeiro.

## Não fazer
- não recriar Review5;
- não refazer Corporate;
- não voltar workspace/Amil aos valores demo;
- não desinstalar o app para atualizar;
- não usar `git reset --hard`/`git clean` em produção;
- não apagar rollback;
- não expor secrets;
- não habilitar Support ingest automaticamente;
- não promover automaticamente para `main` ou `corporate-api-r1`.
