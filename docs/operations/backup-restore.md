# Backup e restauração

Implementa o [ADR-009](../decisions/ADR-009-backup.md). Os comandos exatos entram no setup da infraestrutura.

## Política

| Item | Valor |
| --- | --- |
| Ferramenta | `pg_dump` no formato custom (`-Fc`) |
| Frequência | *A definir no setup* — é ela que define o RPO |
| RPO declarado | Igual à frequência do dump |
| Destino | Bucket do Object Storage da Oracle, fora da VM |
| Retenção | *A definir* (exemplo: últimos 7 diários) |
| Teste de restauração | Antes da primeira apresentação e depois de cada mudança na rotina de backup |

## Backup

Executado pelo agendador do **Servidor (VM Oracle, Linux)**:

1. Gerar o dump do banco a partir do container `postgres`, com data e hora no nome do arquivo.
2. Enviar o arquivo para o bucket.
3. Apagar a cópia local depois do envio confirmado.
4. Registrar sucesso ou falha num log que a equipe consiga consultar.

## Restauração

Executada no **Servidor (VM Oracle, Linux)** ou num **PC (Linux)** de teste:

1. Baixar o dump desejado do bucket.
2. Subir um PostgreSQL limpo, na mesma versão da produção.
3. Restaurar com `pg_restore`.
4. Conferir:
   - a contagem de registros das tabelas principais (`paciente`, `solicitacao`, `agendamento`, `vaga`);
   - a versão das migrações do Alembic;
   - um login e um fluxo do paciente.
5. Registrar a data do teste e o tempo gasto (é o RTO observado).

## Registro de testes de restauração

| Data | Dump usado | Resultado | Tempo | Quem |
| --- | --- | --- | --- | --- |
| | | | | |
