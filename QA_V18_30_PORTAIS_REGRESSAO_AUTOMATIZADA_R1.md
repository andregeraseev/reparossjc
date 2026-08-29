# Reparos SJC v18.30 — Regressão automatizada dos quatro portais R1

Data: 2026-08-29

## Objetivo

Fechar o máximo possível da regressão de Portal Operations v18.30 sem depender de interação no aparelho, credenciais reais ou alteração em produção.

Esta bateria roda exclusivamente com banco/arquivos temporários de teste e credenciais geradas em tempo de execução. Não acessa o SQLite de produção, não usa senhas reais, não faz deploy e não promove `main`.

## Base

- branch de origem: `deploy-portals-v18.30-20260829`
- HEAD de origem: `f135db7b369dc957060aa2da3454105c1f6f3362`
- branch isolada limpa de QA: `qa-v18.30-portals-regression-r2-clean`
- HEAD QA validado antes desta atualização documental: `4c7178a7c554ecb5a78a61a3499c779eeff64b47`
- PR draft: `#7`
- produção permanece sem alterações.

## Cenários cobertos

### 1. Sessão e logout

- login no perfil equivalente ao Cris Teste;
- GET de logout mostra confirmação sem encerrar silenciosamente;
- POST de logout remove `_auth_user_id` da sessão;
- login subsequente em Amil Jurídico troca efetivamente a identidade;
- a nova sessão não abre Cris Teste nem outro canal Amil não autorizado.

### 2. Isolamento dos quatro portais

Perfis sintéticos equivalentes a:

- Cris Teste;
- Amil Jurídico;
- Amil Manutenção;
- Amil Distrato.

Para cada perfil são verificados:

- página contendo somente chamado/pessoa do próprio canal;
- API de portal contendo somente IDs autorizados;
- canal Amil vizinho retorna 404;
- organização externa retorna 403;
- conteúdo de chamados e pessoas dos outros portais não aparece no HTML.

### 3. Imagens privadas

Para cada um dos quatro portais:

- criação de chamado com PNG real mínimo em armazenamento temporário;
- leitura autenticada pelo próprio canal retorna 200;
- `Content-Type` esperado;
- `Cache-Control: private, no-store`;
- usuário de outro portal recebe 404 para o mesmo anexo.

### 4. Orçamento real, aprovação e agendamento

Para cada um dos quatro portais:

- operador sintético envia orçamento no formato observado no incidente real: item com `name`, `qty`, `total`, sem `price`;
- compatibilidade adiciona `price` sem alterar `total`;
- página do portal precisa renderizar HTTP 200 e mostrar o item;
- portal autorizado aprova orçamento;
- disponibilidade pública sintética é publicada no banco de teste;
- operador oferece subconjunto explícito;
- portal escolhe a janela;
- chamado chega a `schedule_requested` com `schedule_selected`;
- portal vizinho não consegue mutar o chamado.

### 5. Central de Suporte / Portal Ops

- `sanitize_snapshot_v1830` aceita apenas a allow-list numérica de `portalOps`;
- valores negativos são limitados a zero e valores excessivos ao teto seguro;
- nomes, telefone, endereço, descrição, IDs de chamado, URL de imagem e rótulos livres são descartados;
- feed staff-only re-sanitiza até snapshot deliberadamente sujo gravado no banco de teste;
- `sync` expõe apenas os quatro campos técnicos autorizados;
- usuário não-staff não acessa o feed;
- resposta permanece `aggregate-technical-only` e sem cache.

### 6. Hardening de bordas adicionado após a regressão principal

Dois comportamentos foram primeiro reproduzidos como falha e depois corrigidos somente nesta branch de QA:

1. **ID externo longo**: a checagem de duplicidade passou a usar o mesmo valor normalizado/limitado a 120 caracteres que será persistido. Isso evita colisão de `UNIQUE`/500 quando dois IDs longos diferentes compartilham os primeiros 120 caracteres.
2. **Filtro explícito de portal fora do escopo**: `portal_channel_id` não autorizado agora retorna 403 em vez de continuar silenciosamente com outro escopo permitido.

Também ficaram travadas as não-regressões:

- espaços antes/depois do ID externo são normalizados antes da duplicidade;
- filtro explícito para um canal efetivamente autorizado continua funcionando normalmente.

## Gate final sem interação

Run `33277783531`: **success**.

- **77 testes** Corporate + Support, todos OK;
- `manage.py check`: sem problemas;
- `makemigrations --check --dry-run`: sem mudanças;
- migrations em banco descartável: OK;
- bootstrap idempotente dos quatro portais: OK;
- gate estático de privacidade/compatibilidade/escopo: OK;
- smoke externo anônimo de produção: OK;
- GitGuardian no mesmo HEAD: **No secrets detected**.

O smoke externo é somente leitura para login, health, os quatro caminhos de portal, raiz Corporate e feed da Central. Ele não autentica, não envia POST e não altera produção.

## Fora desta bateria

Continuam dependendo de validação humana/produção e não devem ser marcados como concluídos por CI:

- aparência e usabilidade real no navegador/celular;
- login com as credenciais reais dos quatro portais;
- upload de foto real pela interface pública de produção;
- sincronização real com o app instalado no Samsung;
- aprovação/agendamento reais no ambiente público;
- observação da Central de Suporte com telemetria real do aparelho;
- qualquer deploy, reload ou migration de produção.

## Regra de promoção

Resultado verde nesta branch significa somente **regressão automatizada aprovada**. Não autoriza merge, deploy ou mudança em `main` sem etapa explícita posterior.
