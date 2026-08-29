# Reparos SJC v18.30 — Regressão automatizada dos quatro portais R1

Data: 2026-08-29

## Objetivo

Fechar o máximo possível da regressão de Portal Operations v18.30 sem depender de interação no aparelho, credenciais reais ou alteração em produção.

Esta bateria roda exclusivamente com banco/arquivos temporários de teste e credenciais geradas em tempo de execução. Não acessa o SQLite de produção, não usa senhas reais, não faz deploy e não promove `main`.

## Base

- branch de origem: `deploy-portals-v18.30-20260829`
- HEAD de origem: `f135db7b369dc957060aa2da3454105c1f6f3362`
- branch isolada limpa de QA: `qa-v18.30-portals-regression-r2-clean`
- produção permanece sem alterações.

## Cenários novos

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

## Gate existente preservado

A bateria nova roda junto de todos os testes `corporate` + `support_center`, `manage.py check`, `makemigrations --check`, migrations em banco descartável, bootstrap idempotente dos quatro portais e gate estático de privacidade/compatibilidade da v18.30.

Também há smoke externo somente leitura para login, health, os quatro caminhos de portal, raiz Corporate e feed da Central. Ele não autentica, não envia POST e não altera produção.

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
