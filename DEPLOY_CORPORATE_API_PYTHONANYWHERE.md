# Corporate API R1 — deploy no PythonAnywhere

Branch de teste: `corporate-api-r1`.

## 1. Atualizar o código
No Bash Console do PythonAnywhere, dentro do repositório do site:

```bash
git fetch origin
git checkout corporate-api-r1
git pull --ff-only origin corporate-api-r1
```

## 2. Variáveis de ambiente
Defina no arquivo WSGI do web app, antes de importar o Django, ou em um arquivo privado fora do repositório carregado pelo WSGI:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG=0`
- `DJANGO_ALLOWED_HOSTS=reparossjc.online,www.reparossjc.online`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://reparossjc.online,https://www.reparossjc.online`
- `RSJC_WORKSPACE_ID=ws_reparos_sjc`
- `RSJC_CORPORATE_OPERATOR_TOKEN=<token longo e aleatório>`
- `RSJC_AMIL_USERNAME=<usuário do portal>`
- `RSJC_AMIL_PASSWORD=<senha forte do portal>`

Nunca grave esses valores no GitHub.

## 3. Banco e usuário Amil
Com o virtualenv do site ativo:

```bash
python manage.py migrate
python manage.py bootstrap_corporate_demo
python manage.py check
```

## 4. Reload
Na aba **Web** do PythonAnywhere, pressione **Reload**.

## 5. Smoke test
Abra:

- `https://www.reparossjc.online/api/corporate/v1/health`
- `https://www.reparossjc.online/corporativo/login/`

O health deve responder JSON com `ok: true`; o portal deve pedir login.

## 6. App Android
No Chamador, configurar uma única vez:

- API: `https://www.reparossjc.online/api/corporate/v1`
- token do operador: o mesmo valor de `RSJC_CORPORATE_OPERATOR_TOKEN`

O token fica no armazenamento privado do aplicativo e não entra no backup.
