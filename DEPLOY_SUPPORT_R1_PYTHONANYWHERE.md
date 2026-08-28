# Deploy futuro — Central de Suporte R1 no PythonAnywhere

> **NÃO EXECUTAR AUTOMATICAMENTE.** Este documento prepara o caminho; a produção Corporate API R1 deve continuar intocada até aprovação do gate Support R1.

## Pré-condições
- backend branch `support-r1` com CI verde;
- APK `v18.27-support-r1` com gate Android 16 verde;
- backup real de `db.sqlite3` criado antes de migrations;
- confirmar que a instalação ativa continua `/home/AndreGeraseev/reparossjc_corporate_api_r1`;
- preservar `/home/AndreGeraseev/reparossjc` e o WSGI de rollback;
- nunca exibir o conteúdo de `~/.rsjc_corporate_env.py`.

## Estratégia recomendada
A Central Support R1 deve entrar na instalação isolada já usada pela Corporate API, mas somente após revisão controlada. Não criar um segundo site/DB de produção sem necessidade.

Sequência futura:
1. backup do SQLite atual com timestamp;
2. conferir `git status` e preservar deltas locais do site público;
3. integrar **somente** os arquivos Support aprovados na instalação de produção;
4. `python manage.py check`;
5. `python manage.py makemigrations --check --dry-run`;
6. `python manage.py migrate --noinput`;
7. smoke local com ingestão ainda desligada;
8. criar/confirmar um usuário Django `is_staff` para `/suporte/` sem registrar senha em Git/chat;
9. Reload do site;
10. confirmar `/api/support/v1/health` e `/suporte/` protegido;
11. somente depois definir `RSJC_SUPPORT_INGEST_ENABLED=1` no arquivo privado de ambiente e Reload;
12. instalar APK Support R1 em um aparelho de teste e validar bootstrap/código/diagnóstico;
13. só então considerar disponibilidade para usuários reais.

## Smoke tests esperados antes de habilitar ingestão
- `/api/corporate/v1/health` continua 200;
- portal Corporate continua acessível;
- site `/` e `/seguranca` continuam 200;
- `/api/support/v1/health` retorna `ok=true` e `ingestEnabled=false`;
- `/api/support/v1/bootstrap` retorna 503 enquanto ingestão estiver desligada;
- `/suporte/` redireciona não autenticados para login de staff;
- usuário comum sem `is_staff` não acessa a Central.

## Smoke tests após habilitar ingestão
Usar somente um aparelho de teste:
- app obtém código `RSJC-XXXX-XXXX`;
- token bruto não aparece no banco/admin/logs;
- Central encontra conta pelo código;
- snapshot mostra somente métricas permitidas;
- evento contendo email/telefone/token fictício chega redigido;
- fotos/dados integrais de clientes não aparecem;
- desligar compartilhamento contínuo impede novos uploads automáticos;
- `Enviar diagnóstico agora` continua funcional;
- export offline funciona mesmo com API Support indisponível.

## Rollback
Se houver regressão:
- manter o backup SQLite;
- desligar imediatamente `RSJC_SUPPORT_INGEST_ENABLED` e Reload;
- se necessário voltar código/WSGI para o estado anterior sem apagar banco/pastas;
- investigar fora de produção.

Como a ingestão tem kill switch independente, a primeira resposta a problemas de Support deve ser **desabilitar ingestão**, não derrubar a Corporate API.
