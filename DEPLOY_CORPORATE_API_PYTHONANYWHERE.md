# Corporate API R1 — deploy no PythonAnywhere

Branch: `corporate-api-r1`.

## Status atual
**Deploy realizado com sucesso em 26/08/2026.**

Produção atual:
- pasta antiga preservada: `/home/AndreGeraseev/reparossjc`;
- pasta nova em uso: `/home/AndreGeraseev/reparossjc_corporate_api_r1`;
- WSGI: `/var/www/www_reparossjc_online_wsgi.py`;
- secrets: `/home/AndreGeraseev/.rsjc_corporate_env.py` (permissão 600);
- health público confirmado em `https://www.reparossjc.online/api/corporate/v1/health` com `ok: true`.

Leia `00_CONTINUIDADE_CORPORATE_API_R1.md` antes de qualquer novo deploy ou manutenção.

## Procedimento usado no deploy
### 1. Preparação isolada
Em vez de trocar a branch diretamente dentro da pasta que atendia o site, foi criada uma cópia isolada:

```bash
git clone --branch corporate-api-r1 \
  https://github.com/andregeraseev/reparossjc.git \
  ~/reparossjc_corporate_api_r1
```

O clone usado no deploy partiu do commit funcional `dd1ed7116ac18e1602cfd8b6a96f0cfcb1100c55`.

### 2. Variáveis de ambiente
Os valores privados ficam em arquivo Python fora do repositório, carregado pelo WSGI antes de importar o Django:

- `DJANGO_SECRET_KEY`;
- `DJANGO_DEBUG=0`;
- `DJANGO_ALLOWED_HOSTS`;
- `DJANGO_CSRF_TRUSTED_ORIGINS`;
- `DJANGO_SECURE_SSL_REDIRECT=1`;
- `DJANGO_HSTS_SECONDS=31536000`;
- `RSJC_WORKSPACE_ID=ws_reparos_sjc`;
- `RSJC_CORPORATE_OPERATOR_TOKEN`;
- `RSJC_AMIL_USERNAME`;
- `RSJC_AMIL_PASSWORD`.

Nunca grave nem compartilhe os valores reais no GitHub/chat.

### 3. Banco e testes
Na instalação nova foram executados:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py test corporate -v 1
python manage.py bootstrap_corporate_demo
```

Os 8 testes Corporate passaram.

**Importante:** os testes locais precisam de `DJANGO_SECURE_SSL_REDIRECT=0` e `DJANGO_HSTS_SECONDS=0` somente no processo de teste, porque o Django Test Client usa HTTP. Produção continua com HTTPS/HSTS obrigatórios.

### 4. Preservação do site existente
A instalação antiga tinha alterações locais não commitadas de home, views, rota `/seguranca`, estáticos, favicon e settings. Elas foram copiadas/mescladas para a nova instalação antes da virada.

A CSP antiga foi convertida para formato `django-csp` 4.x:

```python
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        # diretivas preservadas do site
    }
}
```

Após a conversão, `python manage.py check` passou.

Esses arquivos locais devem ser comparados com o GitHub antes de qualquer `reset --hard`, `clean` ou reclone destrutivo. Veja `00_CONTINUIDADE_CORPORATE_API_R1.md`.

### 5. WSGI
Antes da virada foi criado backup do WSGI. O arquivo atual carrega primeiro o ambiente privado e depois usa a nova pasta:

```python
exec(open('/home/AndreGeraseev/.rsjc_corporate_env.py').read())
project_home = '/home/AndreGeraseev/reparossjc_corporate_api_r1'
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
```

Depois foi feito **Reload** na aba Web do PythonAnywhere.

### 6. Smoke test público
Confirmado após Reload:

- `https://www.reparossjc.online/api/corporate/v1/health` → `ok: true`.

Também devem permanecer disponíveis:
- `https://www.reparossjc.online/`;
- `https://www.reparossjc.online/seguranca`;
- `https://www.reparossjc.online/corporativo/login/`.

## App Android
App correspondente:
- repo `andregeraseev/reparossjc-wear-`;
- branch `v18.27-corporate-api-r1`;
- artifact técnico aprovado `9625535347`;
- API `https://www.reparossjc.online/api/corporate/v1`.

O token do operador é o mesmo `RSJC_CORPORATE_OPERATOR_TOKEN`, mas deve ser obtido apenas no terminal do PythonAnywhere e colado diretamente no aparelho. Não compartilhar no chat.

## Rollback
Se um deploy futuro quebrar o site:
1. restaurar o backup do WSGI ou apontar `project_home` de volta para `/home/AndreGeraseev/reparossjc`;
2. Reload na aba Web;
3. investigar antes de nova tentativa.

Não apagar a pasta nova nem a antiga durante o rollback.
