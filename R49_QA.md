# R49 · Diagnósticos de testes

A edição Android de testes tem o pacote `br.com.reparossjc.field.qa`. Ela abre com o armazenamento vazio e pode carregar o cenário fictício pelo painel de testes. O painel oferece autorização, encerramento, envio manual e exclusão da sessão local.

Os diagnósticos contêm somente versão, SDK Android, classe de aparelho, identificador aleatório da instalação de QA, identificador e duração da sessão e eventos enumerados. A conferência de gravação indica a leitura imediata do valor persistido no armazenamento local. A sessão permanece no aparelho após falha de envio e a repetição do envio é idempotente.

## Instalação isolada

Configure um ambiente HTTPS com o módulo `config.r49_settings`. Aponte `RSJC_QA_DATABASE` para um arquivo SQLite absoluto e exclusivo, `RSJC_QA_SECRET` para uma chave aleatória e `RSJC_QA_HOSTS` para os nomes HTTPS permitidos, separados por espaços. Configure `RSJC_QA_TRUST_HTTPS_PROXY=1` somente se o proxy confiável sobrescrever o cabeçalho de protocolo. O projeto WSGI existente respeita `DJANGO_SETTINGS_MODULE`.

```bash
python -m pip install -r requirements-r48.txt
export DJANGO_SETTINGS_MODULE=config.r49_settings
python manage.py migrate --noinput
python manage.py createsuperuser
python manage.py rsjc_qa_token qa-01
python manage.py test qa_monitor
```

O painel fica em `/qa/` e exige login da equipe. O comando de token imprime uma credencial de envio, sem conceder acesso ao painel. Use um código fictício por testador e entregue a credencial pelo canal privado de QA. Repetir o comando substitui a credencial anterior daquele código.

No app, abra **Ajustes → Backup → Sessão de teste**. Carregue o exemplo, inicie e autorize a coleta, use as telas e encerre a sessão. Selecione **Enviar diagnóstico** e informe a URL HTTPS do ambiente e o token do testador. A sessão local pode ser descartada quando o envio for confirmado no painel.

A API de diagnósticos é `POST /api/rsjc-qa/v1/sessions/`. Ela verifica o token, o tamanho e a lista fechada de campos e valores. O mesmo identificador com conteúdo idêntico é aceito novamente. Um identificador existente com conteúdo ou conta diferente é recusado. A publicação é independente do site e do servidor de backups da R48.
