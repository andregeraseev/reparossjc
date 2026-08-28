# 00 — Continuidade Support R1

**Criado em:** 27/08/2026  
**Backend:** `andregeraseev/reparossjc`, branch `support-r1`  
**App:** `andregeraseev/reparossjc-wear-`, branch `v18.27-support-r1`

> Esta frente é isolada da Corporate API R1 em produção. Não fazer deploy automático nem mesclar para `corporate-api-r1`/`main` antes do gate técnico e físico. O objetivo é uma Central de Suporte interna, inicialmente somente leitura do aparelho.

## Objetivo
Permitir que um usuário informe um código `RSJC-XXXX-XXXX` e o suporte interno encontre:
- conta/workspace;
- aparelhos registrados;
- versão do app/Android;
- último contato e último backup;
- estado da sincronização;
- Live Update/notificações;
- contagens técnicas de registros;
- linha do tempo sanitizada de ações/erros;
- diagnóstico automático por regras;
- chamados internos de suporte.

## Privacidade e segurança
- token do dispositivo de suporte é secreto e fica apenas no SharedPreferences privado `rsjc_private_secrets` do Android;
- token não entra em backup, Git, logs ou código de suporte;
- o código `RSJC-XXXX-XXXX` é identificador de busca, não credencial de acesso;
- `/suporte/` é restrito a usuário Django `is_staff`;
- API ingere somente campos sanitizados e possui uma segunda sanitização server-side;
- não enviar nome/telefone/endereço de clientes atendidos, fotos, senhas, OpenAI API key, Corporate token, keystore ou conteúdo integral do banco;
- sem shell, JavaScript remoto ou alteração remota de dados na R1.

## Backend preparado
Novo app Django `support_center`:
- `SupportAccount` — workspace + código de suporte;
- `SupportDevice` — instalação/aparelho + hash do token;
- `SupportEvent` — eventos técnicos sanitizados;
- `SupportSnapshot` — snapshots de saúde (máx. 50 por aparelho);
- `SupportCase` — chamado interno criado pelo operador.

Rotas planejadas:
- `GET /api/support/v1/health`;
- `POST /api/support/v1/bootstrap`;
- `POST /api/support/v1/events`;
- `POST /api/support/v1/snapshot`;
- `GET /suporte/`;
- `GET /suporte/<support_code>/`.

`RSJC_SUPPORT_INGEST_ENABLED` controla a ingestão. Em produção o default é **desligado**; portanto simplesmente ter o código no branch não começa a receber telemetria.

## App planejado
Support R1 é aplicado por patch determinístico sobre o artifact Hardening1, preservando 18.27/1827, assinatura, banco, backup, Wear, Live Update e Corporate API.

Comportamento:
1. gera `installationId` local não incluído no backup;
2. bootstrap mínimo obtém `supportCode` e token do aparelho;
3. token é salvo no cofre Android privado;
4. auditoria madura é espelhada em uma fila **sanitizada** local de suporte;
5. `window.error` e `unhandledrejection` entram na mesma fila sanitizada;
6. detalhes ficam locais por padrão;
7. usuário pode `Enviar diagnóstico agora` para enviar snapshot + últimos eventos;
8. opção de compartilhamento contínuo pode ser ativada explicitamente;
9. Ferramentas ganha entrada `Suporte`.

## Não fazer
- não implantar ainda no PythonAnywhere sem revisão explícita;
- não habilitar ingestão em produção sem definir política/consentimento;
- não usar código de suporte como senha;
- não mandar objetos comerciais completos para a API de suporte;
- não adicionar comandos remotos destrutivos nesta fase.
