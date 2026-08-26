# Corporate API R1

Gate da primeira integração real entre Portal Corporativo e aplicativo Reparos SJC.

Branch: `corporate-api-r1`

Validações esperadas:
- Django check;
- migrations sem drift;
- testes de autenticação do operador;
- criação de chamado no portal;
- idempotência por organização + externalRequestId;
- aprovação de orçamento;
- escolha de horário;
- contrato sem exposição da agenda privada.
