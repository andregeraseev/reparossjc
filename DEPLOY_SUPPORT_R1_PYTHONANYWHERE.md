# Deploy concluído — Central de Suporte R1 no PythonAnywhere

> Implantação controlada concluída e validada em 28/08/2026. **Não repetir automaticamente.** A produção Corporate API R1 permaneceu funcional durante todo o processo.

## Estado implantado
- instalação: `/home/AndreGeraseev/reparossjc_corporate_api_r1`;
- branch local: `deploy-support-r1-20260828`;
- commit implantado: `4a4ca987484b4480c92ad56f91ef413902e98284`;
- backup pré-Support: `db.sqlite3.backup-pre-support-20260828-132054`;
- SHA-256 do banco e backup na cópia: `3629e5de6709b690f7f8ac681bc92141eaa0e1c7228171e0ec4906f405ec2640`;
- migration: `support_center.0001_initial` aplicada;
- ingestão: `RSJC_SUPPORT_INGEST_ENABLED=True` após validação inicial com o kill switch desligado;
- integridade SQLite final: `ok`.

## Pré-condições
- backend branch `support-r1` com CI verde;
- APK `v18.27-support-r1` com gate Android 16 verde;
- backup real de `db.sqlite3` criado antes de migrations;
- confirmar que a instalação ativa continua `/home/AndreGeraseev/reparossjc_corporate_api_r1`;
- preservar `/home/AndreGeraseev/reparossjc` e o WSGI de rollback;
- nunca exibir o conteúdo de `~/.rsjc_corporate_env.py`.

## Estratégia executada
A Central Support R1 entrou na instalação isolada já usada pela Corporate API, sem criar segundo site ou segundo banco de produção.

Sequência concluída:
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

## Smoke tests aprovados antes de habilitar ingestão
- `/api/corporate/v1/health` continua 200;
- portal Corporate continua acessível;
- site `/` e `/seguranca` continuam 200;
- `/api/support/v1/health` retorna `ok=true` e `ingestEnabled=false`;
- `/api/support/v1/bootstrap` retorna 503 enquanto ingestão estiver desligada;
- `/suporte/` redireciona não autenticados para login de staff;
- usuário comum sem `is_staff` não acessa a Central.

## Validação aprovada após habilitar ingestão
Piloto: Samsung SM-S911B, Android 16, app 18.27/1827.
- app obteve e preservou o código `RSJC-MGHL-U85Q`;
- token bruto não aparece no banco/admin/logs;
- Central encontra conta pelo código;
- snapshot mostra somente métricas permitidas;
- fotos/dados integrais de clientes não aparecem;
- `Enviar diagnóstico agora` continua funcional;
- export/import offline funcionou com a API indisponível;
- compartilhamento contínuo foi habilitado com consentimento e permaneceu ativo;
- 42 eventos e 3 snapshots foram observados após o piloto.

Ainda não tratar como encerrados:
- teste real do PDF Review5;
- teste real da IA Review5 com anotação curta + fotos;
- regressão Corporate completa;
- investigação dos 24 itens pendentes na fila local.

## Rollback
Se houver regressão:
- manter o backup SQLite;
- desligar imediatamente `RSJC_SUPPORT_INGEST_ENABLED` e Reload;
- se necessário voltar código/WSGI para o estado anterior sem apagar banco/pastas;
- investigar fora de produção.

Como a ingestão tem kill switch independente, a primeira resposta a problemas de Support deve ser **desabilitar ingestão**, não derrubar a Corporate API.
