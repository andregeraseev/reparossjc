# Relatos de bugs R49.3 no site Reparos SJC

O painel autenticado em `/qa/` passa a oferecer **Relatos de bugs**. Cada entrada guarda no banco já reservado ao QA a descrição autorizada, a tela, a versão, a captura JPEG opcional e até 30 ações da sessão quando disponíveis. Capturas ficam nas tabelas privadas e são entregues somente com uma sessão de equipe válida.

## Atualizar o painel de QA

1. Preserve o WSGI ativo e a configuração privada que define `RSJC_QA_DB_PATH`. Use uma cópia consistente do banco SQLite de QA, via API de backup do SQLite, antes da migração.
2. No ambiente virtual ativo, instale a dependência indicada em `requirements-qa-feedback.txt`.
3. Aplique as mudanças de `qa_monitor/` à mesma instalação do painel privado. O teste de isolamento verifica que o banco operacional continua byte a byte igual durante a migração.
4. Com o mesmo ambiente do WSGI, execute:

   ```bash
   python manage.py check
   python manage.py migrate qa_monitor --database=rsjc_qa --noinput
   ```

5. Recarregue o site em PythonAnywhere. Confira a página pública e o acesso autenticado a `/qa/bugs/`. Rode um teste fictício com o APK R49.3 e confira descrição, imagem e sessão associada. O aplicativo usa o mesmo token de testador que já autorizava diagnósticos.
6. Mantenha a tarefa diária `python manage.py rsjc_qa_prune`. Ela inclui os relatos e suas capturas no mesmo prazo de retenção das sessões.

Para reverter a publicação, retome o código anterior do painel e recarregue o site. A nova tabela é aditiva e pode permanecer no banco privado para preservar relatos recebidos. Os envios antigos de sessões com protocolo 1 continuam aceitos pelo painel atualizado.
