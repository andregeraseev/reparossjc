# Corporate Provider Routing R1

**Branch:** `corporate-provider-routing-r1`  
**Base:** `support-r1` Review4, com Corporate Hardening1 preservado  
**Status:** implementação isolada; não implantar em produção antes do gate e revisão controlada

## Objetivo

Permitir que várias lojas/organizações usem o portal Corporate e escolham um único prestador autorizado ao criar cada chamado. A seleção define qual workspace/app recebe o chamado sem expor a agenda privada de nenhum prestador.

## Modelo

- `ServiceProvider`: identidade do prestador, nome público, workspace exclusivo e hash do token da API;
- `OrganizationProvider`: lista explícita de prestadores autorizados por loja, com um padrão opcional;
- `ServiceRequest.provider`: destinatário gravado no chamado;
- `ServiceRequest.workspace_id`: preservado para compatibilidade com o contrato Android atual e preenchido a partir do prestador escolhido.

Chamados existentes são associados ao prestador correspondente ao workspace durante a migration. A organização Amil continua autorizada para a Reparos SJC e mantém seu fluxo anterior.

## Segurança

- cada loja vê apenas prestadores ativos presentes em sua lista autorizada;
- POST forjado com prestador não autorizado é rejeitado;
- cada novo prestador usa token próprio; o servidor persiste somente SHA-256;
- o token global legado permanece aceito somente no workspace canônico existente;
- o workspace autenticado é autoritativo: parâmetros de URL não ampliam o acesso;
- um prestador não consulta nem atualiza chamados atribuídos a outro;
- contratos expõem nome/ID público do prestador, nunca token ou hash;
- agenda interna continua fora da API; apenas janelas públicas são compartilhadas.

## Operação inicial

O cadastro de prestadores e os vínculos com lojas é feito no Django Admin. O token individual é lido de variável de ambiente privada pelo comando:

```text
python manage.py set_corporate_provider_token <slug> --token-env RSJC_PROVIDER_TOKEN
```

O valor bruto não deve ser passado na linha de comando, Git, logs ou chat.

## Gate obrigatório

- `manage.py check`;
- `makemigrations --check --dry-run`;
- migration em banco temporário;
- regressão completa de `corporate` e `support_center`;
- loja vê somente prestadores autorizados;
- seleção roteia ao workspace correto;
- token/workspace de outro prestador não acessa o chamado;
- fluxo Amil atual permanece funcional;
- Support continua com ingestão desligada até ativação controlada.

## Não fazer

- não implantar junto com a primeira ativação da Central Support;
- não reutilizar um token entre prestadores novos;
- não permitir seleção global de qualquer prestador;
- não remover `workspace_id` do contrato Android nesta revisão;
- não publicar agenda privada;
- não promover automaticamente para `corporate-api-r1` ou `main`.
