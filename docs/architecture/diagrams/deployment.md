# Diagrama de implantação

Onde cada componente executa no MVP. Portas e nomes de serviço são a proposta para o `docker-compose.yml`; o procedimento está em [implantação](../../operations/deployment.md).

```mermaid
flowchart TB
  subgraph cliente["Dispositivo do usuário"]
    browser["Navegador<br/>(celular ou computador)"]
  end

  subgraph oci["Oracle Cloud — nível gratuito"]
    subgraph vm["VM Linux · 2 OCPU · 12 GB RAM · 200 GB"]
      subgraph compose["Docker Compose"]
        subgraph publica["rede: borda"]
          nginx["nginx<br/>:80 → redireciona<br/>:443 TLS"]
        end
        subgraph interna["rede: interna (sem acesso externo)"]
          api["api<br/>Uvicorn :8000"]
          worker["worker"]
          db[("postgres :5432")]
          vol[("volume pgdata")]
        end
      end
      cron["agendador do host<br/>pg_dump"]
    end
    obj[["Object Storage<br/>bucket de backups"]]
  end

  smtp[["Provedor SMTP"]]

  browser -- "HTTPS 443" --> nginx
  nginx -- "/api/v1 → :8000" --> api
  api --> db
  worker --> db
  db --- vol
  worker -- "SMTP TLS" --> smtp
  cron -- "dump" --> db
  cron -- "upload" --> obj
```

O GitHub Actions roda lint e testes em cada pull request; no MVP ele não publica na VM (implantação manual, ver [implantação](../../operations/deployment.md)).

- Só as portas 80 e 443 ficam abertas na lista de segurança da VM; o SSH é restrito às chaves da equipe.
- `api`, `worker` e `postgres` não publicam portas no host.
- O frontend, depois de compilado, é servido pelo próprio Nginx como arquivos estáticos.
