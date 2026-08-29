# Continuidade — Reparos SJC v18.30 Portais em produção

Atualizado em 29/08/2026 após os hotfixes de sessão/logout e renderização de orçamento.

## Comece por aqui no próximo chat

Abra primeiro o app `andregeraseev/reparossjc-wear-`, branch `v18.30-portals-r1`, e leia `AGENTS.md`, `01_NOVO_CHAT_COMECE_AQUI.md` e `qa/v18.30/GATE_PORTAL_OPERATIONS_R1.md`.

Depois abra o backend `andregeraseev/reparossjc`, branch de implantação `deploy-portals-v18.30-20260829`, e leia `01_NOVO_CHAT_COMECE_AQUI.md` e este arquivo.

Continue exatamente do estado abaixo. Não recomece, não reestruture, não desinstale o app, não limpe dados/filas, não exponha secrets e não promova nada automaticamente para `main`.

## Estado autoritativo do app 18.30

- repo: `andregeraseev/reparossjc-wear-`
- branch: `v18.30-portals-r1`
- HEAD confirmado: `3f10f3ab4888eaaaf8945d522ac41a38dc0c8467`
- versão: `18.30` / versionCode `1830`
- applicationId: `br.com.reparossjc.field`
- CI final aprovado: run `33261933602`, job `99125245486`
- artifact: `ReparosSJC-v18.30-Portal-Operations-R1`, artifact ID `9717582539`
- artifact digest: `sha256:37287d10b6bf538df0dfa58f068e897e60e53e47aefce035ff46e7acf7f38d31`
- Mobile SHA-256: `1fabe7d1dc1ea9febdf28377acbe88d016bef2a193cda0f894d1211b162369b1`
- Wear SHA-256: `df1dc19b76a1cee5ce9833c47b804550971ddd6a7367d74a80b37d5a4705a85d`
- source ZIP SHA-256: `d76624e7390d07cce10ea8306d619845a6d7687836becb7b45020d4e9ba01174`
- upgrade gate Android 16 passou com `adb install -r`, preservando `firstInstallTime`; nunca desinstalar para atualizar.

## Estado autoritativo do backend implantado

- repo: `andregeraseev/reparossjc`
- branch de integração/implantação: `deploy-portals-v18.30-20260829`
- HEAD remoto atual: `8e25d5d8b06bfd40e0566cae48e2b511459985e1`
- branch de desenvolvimento 18.30: `corporate-portals-v18.30-r1`
- HEAD de desenvolvimento atual: `210ae7c2d7c8e433152849d364984ef4a5899b83`
- instalação PythonAnywhere: `/home/AndreGeraseev/reparossjc_corporate_api_r1`
- WSGI: `/var/www/www_reparossjc_online_wsgi.py`
- env privado: `/home/AndreGeraseev/.rsjc_corporate_env.py` — nunca exibir conteúdo
- banco: `/home/AndreGeraseev/reparossjc_corporate_api_r1/db.sqlite3`
- Support R1 existente foi preservado na integração.
- `main` não foi alterada.

## Quatro portais ativos

1. Cris Teste
   - organização: `cris-teste`
   - canal: `teste`
   - usuário: `portal_cris_teste`
   - URL: `https://www.reparossjc.online/corporativo/p/cris-teste/teste/`

2. Amil Jurídico
   - organização: `amil`
   - canal: `juridico`
   - usuário: `portal_amil_juridico`
   - URL: `https://www.reparossjc.online/corporativo/p/amil/juridico/`

3. Amil Manutenção
   - organização: `amil`
   - canal: `manutencao`
   - usuário: `portal_amil_manutencao`
   - URL: `https://www.reparossjc.online/corporativo/p/amil/manutencao/`

4. Amil Distrato
   - organização: `amil`
   - canal: `distrato`
   - usuário: `portal_amil_distrato`
   - URL: `https://www.reparossjc.online/corporativo/p/amil/distrato/`

Login compartilhado: `https://www.reparossjc.online/corporativo/login/`.

Senhas existem apenas no ambiente/DB com hash. Nunca escrever, imprimir ou commitar senhas.

## Escopo e isolamento dos portais

- `PortalChannelMembership` limita cada usuário ao canal autorizado.
- `PortalPerson` mantém cadastro de pessoas separado por portal.
- chamadas, anexos, aprovação e agendamento são canal-scoped.
- imagens são privadas e entregues apenas por endpoint autenticado.
- Central de Suporte recebe somente agregados técnicos; não recebe nomes, telefones, endereços, descrições, fotos ou outros dados comerciais/PII.
- feed staff-only: `/suporte/monitoramento/portal-ops.json`.

## Hotfix 1 — sessão/logout

Sintoma observado: após login, a tela mostrava `Usuário sem empresa vinculada` mesmo com vínculos corretos.

Diagnóstico:
- banco, WSGI e dispatcher 18.30 estavam corretos;
- o template legado usava logout por GET;
- a sessão anterior podia permanecer ativa e impedir a troca real de usuário.

Correção:
- PR #4 `Fix: corporate logout session flow`;
- merge na branch de deploy: `8bf1bc1830df4b2919a359b75281b7b224b87f4e`;
- logout por POST/CSRF na tela sem acesso;
- compatibilidade para links antigos;
- testes de regressão adicionados;
- CI completo e GitGuardian passaram.

## Hotfix 2 — Server 500 após receber orçamento

Sintoma observado: o portal Cris Teste passava a responder 500 imediatamente após o app enviar um orçamento.

Payload real do item de orçamento observado:
- quote é `dict`;
- possui `discount`, `execution`, `id`, `items`, `payment`, `status`, `total`, `validity`, `warranty`;
- `items` é lista;
- item real tinha chaves `name`, `qty`, `total` e não tinha `price`.

Causa exata confirmada por traceback:
- template usava `{{ qi.total|default:qi.price|floatformat:2 }}`;
- Django resolve o argumento `qi.price` mesmo quando `qi.total` existe;
- ausência de `price` gerava `VariableDoesNotExist` e derrubava a página com 500.

Correção:
- `corporate/quote_compat.py` normaliza itens futuros para garantir a chave `price` como fallback de compatibilidade quando só `total` existe;
- migration `corporate.0005_quote_item_price_compat` corrige orçamentos já gravados sem alterar o `total` original;
- `corporate/test_quote_compat_v1830.py` reproduz o formato real `name/qty/total`;
- PR #5 `Fix: portal quote rendering compatibility`;
- merge na branch de deploy: `8e25d5d8b06bfd40e0566cae48e2b511459985e1`;
- CI completo passou: compile, `check`, `makemigrations --check`, testes Corporate+Support, migrate, bootstrap dos quatro portais e gate de privacidade/compatibilidade;
- GitGuardian passou sem secrets.

O usuário executou backup antes da migration, aplicou `corporate.0005_quote_item_price_compat` e informou que os testes com o orçamento real deram certo. No próximo chat, faça um smoke externo no navegador antes de qualquer novo desenvolvimento se ainda não estiver claramente confirmado que o Reload/publicação final foi concluído.

## Validações já confirmadas nesta sessão

- `portal_cris_teste` existe e está ativo.
- PartnerMembership Cris Teste: manager, ativo, organização ativa.
- PortalChannelMembership Cris Teste/teste: manager, ativo, canal ativo.
- dispatcher 18.30 retorna True.
- `_organization_for` encontra `cris-teste`.
- Django Client com host real retornou 200 para `/corporativo/` e `/corporativo/p/cris-teste/teste/` antes do orçamento.
- WSGI aponta para `/home/AndreGeraseev/reparossjc_corporate_api_r1`.
- banco do shell é o mesmo `db.sqlite3` da instalação de produção.
- SQLite integrity havia retornado `ok` no deploy original.
- bootstrap dos quatro usuários/escopos passou no deploy original.

## Próximo passo recomendado

Não começar uma nova grande feature antes de fechar a regressão real dos portais.

1. Confirmar no navegador que Cris Teste abre com o orçamento já existente e sem 500.
2. Confirmar botão Sair → login de outro portal → isolamento correto da sessão.
3. Testar nos quatro portais: login, criação de chamado, seleção/cadastro de pessoa, upload de imagem, visualização privada, recebimento de orçamento, aprovação e agendamento.
4. Confirmar que Jurídico não enxerga Manutenção/Distrato e que Cris Teste permanece isolado da Amil.
5. Conferir `/suporte/monitoramento/portal-ops.json` como staff e validar que só há agregados técnicos.
6. Só depois decidir o próximo incremento funcional do portal/app.

## Regras permanentes

- não desinstalar o app nem limpar dados/filas;
- não fazer `git reset --hard` ou `git clean` em produção;
- não apagar backups do SQLite;
- não exibir o env privado nem secrets;
- não pedir senha GitHub no terminal;
- não promover automaticamente para `main`;
- não reestruturar app/backend nem criar motores paralelos;
- não marcar validação física como concluída apenas por CI/emulador;
- preservar Support R1 e o fluxo Corporate existente;
- qualquer nova migration: backup primeiro, check/testes, migrate, smoke e Reload controlado.
