# R48 · API de backup privada

A R48 usa uma API de versões imutáveis de Config_App.json. O Android envia com HTTPS e token. O servidor verifica SHA-256, estrutura e tamanho, guarda cada versão com criptografia Fernet e confirma o ID, a integridade e o tamanho. Repetir o mesmo arquivo na mesma conta devolve o ID existente. A API de leitura é isolada por conta.

## Homologação

Use um serviço ou virtual host de QA, com HTTPS e banco separado do site. Instale `requirements-r48.txt` e configure `DJANGO_SETTINGS_MODULE=config.r48_settings` antes de carregar `config.wsgi:application`.

| Variável | Valor |
|---|---|
| `RSJC_BACKUP_DJANGO_SECRET` | Chave Django aleatória do ambiente |
| `RSJC_BACKUP_HOSTS` | Host de QA, sem esquema ou caminho |
| `RSJC_BACKUP_DB` | Caminho absoluto, gravável pelo serviço, fora da pasta pública |
| `RSJC_BACKUP_ENCRYPTION_KEY` | Uma chave Fernet exclusiva, armazenada fora do código |
| `RSJC_BACKUP_TRUST_HTTPS_PROXY` | 1 somente se o proxy confiável remove ou sobrescreve `X-Forwarded-Proto` |

Guarde a chave de criptografia junto com o plano de recuperação do banco. A perda dela torna ilegíveis as versões armazenadas. Configure o proxy para encaminhar `Authorization` e aceitar requisições de até 8 MiB. O armazenamento fica no banco da API e depende da retenção e cópia de segurança desse banco.

```sh
python manage.py migrate --settings=config.r48_settings
python manage.py rsjc_backup_token conta-qa --settings=config.r48_settings
```

O segundo comando mostra o token uma vez e substitui o anterior da conta. Use **Ajustes → Backup → Configurar acesso** no Android. Informe o endereço HTTPS de QA e o token. Habilite o automático somente depois do teste manual. Cada conta tem histórico próprio. Use dados fictícios no ambiente de teste.

A integração no site existente está condicionada a `RSJC_ENABLE_CLOUD_BACKUP=1`. O módulo de homologação é a opção para testar antes de qualquer alteração no site de produção.

## Contrato v1

- `GET /api/rsjc-backup/v1/versions/` lista as versões em ordem de recebimento, com paginação `?before=ID`.
- `POST /api/rsjc-backup/v1/versions/` recebe o JSON schema 44 e `X-Backup-SHA256`. Exige tamanho conhecido e resposta 201 para versão nova ou 200 para repetição.
- `GET /api/rsjc-backup/v1/versions/ID/` entrega os bytes verificados e o checksum no cabeçalho `X-Backup-SHA256`.

Todos exigem `Authorization: Bearer TOKEN` e HTTPS. A API rejeita arquivos incompletos, checksums divergentes e tentativas de gravar cópia totalmente vazia quando já existe histórico.

## QA

```sh
RSJC_ENABLE_CLOUD_BACKUP=1 python manage.py test cloud_backup
RSJC_ENABLE_CLOUD_BACKUP=1 python manage.py makemigrations --check --dry-run
```
