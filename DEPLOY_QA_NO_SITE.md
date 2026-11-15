# Painel de QA no site Reparos SJC

O painel web usa `/qa/`. O APK R49.1 envia diagnósticos para `/api/rsjc-qa/v1/sessions/` no mesmo host HTTPS. No diálogo do APK, informe `https://www.reparossjc.online` como endereço base. A rota reaproveita a aplicação web existente no PythonAnywhere.

## Publicação

1. Na aba **Web**, confira o domínio ativo, o diretório do código, o ambiente virtual e o módulo Django do WSGI. A proposta parte da referência `deploy-portals-v18.30-20260829`. Se a instalação tiver mudanças posteriores, aplique apenas o patch de QA ao código ativo.
2. No ambiente virtual usado pela aplicação, confirme que o site atual responde em HTTPS, anote a revisão e faça uma cópia privada da configuração WSGI. Preserve o banco operacional. Prepare o código atualizado no checkout de publicação habitual.
3. Crie um diretório privado fora da árvore pública do site e dos mapeamentos de arquivos estáticos. Defina `RSJC_QA_DB_PATH` no ambiente privado do WSGI com o caminho absoluto de um SQLite próprio. Exemplo de caminho `/home/AndreGeraseev/.rsjc_qa/diagnostics.sqlite3`. Use permissão 700 no diretório. O ambiente do comando a seguir deve carregar a configuração privada real do site juntamente com `RSJC_QA_DB_PATH`.
4. Ainda antes do reload, faça as verificações e migre somente o banco de QA.

   ```bash
   umask 077
   python manage.py check
   python manage.py migrate qa_monitor --database=rsjc_qa --noinput
   python manage.py rsjc_qa_staff qa-equipe
   python manage.py rsjc_qa_token qa-01
   ```

   Os dois últimos comandos retornam credenciais diferentes. Entregue a senha de equipe exclusivamente à equipe e o token de envio ao testador correspondente. A emissão de token para um código existente substitui o token anterior.

5. Recarregue a aplicação no PythonAnywhere. Confira a página inicial e as rotas corporativas usuais. Confira o redirecionamento de `/qa/` para o login, faça uma sessão fictícia de ponta a ponta e verifique o recibo e a linha do tempo. O envio requer HTTPS com certificado válido.
6. Agende `python manage.py rsjc_qa_prune` diariamente com o ambiente de produção do site e o banco exclusivo de QA. O comando remove diagnósticos após 30 dias por padrão, ajustáveis por `RSJC_QA_RETENTION_DAYS`, além de acessos e contadores de login vencidos. As sessões anteriores da janela temporária conservam o próprio fluxo de arquivamento.

## Reversão

Remova `RSJC_QA_DB_PATH` da configuração WSGI privada e recarregue a aplicação. O QA deixa de ser carregado. O arquivo SQLite permanece disponível para uma reativação ou análise autorizada. Confira a página inicial após o reload.

## Verificação de isolamento

A suíte verifica a página pública, a ativação da rota por configuração, a separação dos bancos e das autenticações, o envio da versão 18.47, a validade do cookie, CSRF, limites, reenvio idempotente e retenção. A integração continua a usar o contrato de dados fictícios do monitor da R49.1.
