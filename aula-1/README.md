# Aula 01 · Fundamentos de observabilidade

Laboratório da Aula 01: a API da Loja instrumentada com **OpenTelemetry**, com métricas coletadas pelo **Prometheus**, visualizadas no **Grafana** e com uma status page no **Uptime Kuma**.

> **Ambiente:** o laboratório rodou localmente com Docker Desktop (Windows), e não no Codespaces, porque a cota gratuita do Codespaces tinha acabado. A stack é a mesma do enunciado. Muda só o acesso, que é por `http://localhost:<porta>` em vez da aba Ports.

## Como subir

```bash
cd aula-1
docker compose up -d --build
docker compose ps
```

| Serviço | Porta | Função |
|---|---|---|
| `app` | 8000 / 9464 | API da Loja (FastAPI) e endpoint `/metrics` |
| `carga` | n/a | Gerador de tráfego (navegação, produtos inexistentes, checkouts) |
| `prometheus` | 9090 | Coleta (scrape) a cada 5 s |
| `grafana` | 3000 | Dashboard provisionado `Loja API · 4 Golden Signals` |
| `status` | 3001 | Uptime Kuma, com a status page em `/status/loja` |

## Estrutura

```
aula-1/
├── compose.yaml
├── app/
│   ├── main.py            # API + OpenTelemetry (auto-instrumentação + métrica de negócio loja.pedidos)
│   ├── carga.py           # gerador de carga
│   ├── requirements.txt
│   └── Dockerfile
├── prometheus/prometheus.yml
└── grafana/
    ├── provisioning/      # data source Prometheus + provider de dashboards
    └── dashboards/golden-signals.json
```

---

## Exercício 1.1: Stack do laboratório
Os 5 containers sobem com um único `docker compose up`. O Prometheus mostra os alvos `loja-api` e `prometheus` como **UP**.

## Exercício 1.2: Métricas expostas pela aplicação
- `http_server_request_duration_seconds_count` aparece com os labels `http_route`, `http_request_method` e `http_response_status_code`.
- `loja_pedidos_total` aparece separado por `pagamento` (pix: 186, cartão: 148 no momento da leitura).
- Buckets de `/checkout` (status 200): 0 requisições abaixo de `le=0.1`, 101 abaixo de `0.25`, 271 abaixo de `0.5` e todas (334) abaixo de `0.75`.

**Aprendizado:** o nome OpenTelemetry `loja.pedidos` vira `loja_pedidos_total` no Prometheus. Os pontos viram sublinhado e o sufixo indica o tipo e a unidade. Cada combinação de labels é uma série temporal.

## Exercício 1.3: Status page com Uptime Kuma
Monitores HTTP(s) com heartbeat de 20 s:

| Monitor | URL | Observação |
|---|---|---|
| Site | `http://app:8000/health` | Caixa-preta mais simples |
| Catálogo | `http://app:8000/produtos` | Jornada de navegação |
| Checkout | `http://app:8000/checkout` | `POST`, timeout de 2 s |

A status page **Loja** (`/status/loja`) tem o grupo **Serviços** com os 3 monitores.

Na simulação de Black Friday (`/chaos?latencia=2.5&erro=0.3`):
- **Site** ficou sempre UP (o `/health` não passa pela lógica afetada).
- **Catálogo** oscilou entre UP e DOWN.
- **Checkout** ficou DOWN (timeout de 2 s).
- O incidente **"Lentidão no checkout"** (estilo *warning*) foi publicado no topo da página.

**Aprendizado:** um `/health` verde não garante que a jornada do cliente funciona. É preciso monitorar as jornadas que importam.

## Exercício 1.4: Os 4 golden signals em PromQL

| Sinal | Consulta | Resultado |
|---|---|---|
| Latência p95 (geral) | `histogram_quantile(0.95, sum by (le) (rate(http_server_request_duration_seconds_bucket[1m])))` | 0,41 s |
| Latência p95 `/checkout` | idem, `by (le, http_route)` | 0,64 s (produtos abaixo de 0,1 s) |
| Tráfego | `sum(rate(http_server_request_duration_seconds_count[1m]))` | 3,9 req/s |
| Erros 5xx | `sum(rate(...{http_response_status_code=~"5.."}[5m])) / sum(rate(...[5m]))` | 0,17% |
| Saturação, CPU | `rate(process_cpu_seconds_total{job="loja-api"}[1m])` | 0,009 núcleo |
| Saturação, fila | `sum(http_server_active_requests{job="loja-api"})` | 0 |
| Negócio | `sum by (pagamento) (rate(loja_pedidos_total[1m])) * 60` | ~16 pedidos/min por meio de pagamento |

**Desafio (SLO de 99,5%):**
```promql
# SLI de disponibilidade na última hora
1 - sum(rate(http_server_request_duration_seconds_count{http_response_status_code=~"5.."}[1h]))
  / sum(rate(http_server_request_duration_seconds_count[1h]))
# Fração do error budget consumida
(sum(rate(http_server_request_duration_seconds_count{http_response_status_code=~"5.."}[1h]))
  / sum(rate(http_server_request_duration_seconds_count[1h]))) / 0.005
```
Resultado: SLI de **99,87%** e **25%** do error budget consumido na última hora.

## Exercício 1.5: Dashboard dos golden signals
O `golden-signals.json` é provisionado na pasta **Observability** do Grafana. Ele tem 4 números no topo (latência p95, tráfego, taxa de 5xx e CPU) e uma linha por sinal. A variável `$rota` filtra todos os painéis.

## Exercício 1.6: Game day

| Horário | Rodada | p95 | Tráfego | 5xx | CPU | Em andamento |
|---|---|---|---|---|---|---|
| 22:08 | Normal | 0,45 s | 3,9 req/s | 0% | 0,008 | 0 |
| 22:09 | **1.** +1 s de latência | **2,4 s** | **0,8 req/s** | 2% | 0,004 | 1 |
| 22:10 | **2.** 30% de erros | 0,48 s | 3,7 req/s | **32,7%** | 0,009 | 0 |
| 22:11 | **3.** 150 `/relatorio` (durante) | 0,46 s | 3,2 req/s | n/a | 0,07 | **29** |
| 22:11 | **3.** 150 `/relatorio` (fim) | **10 s** | 4,8 req/s | n/a | **0,46** | 1 |
| 22:13 | **4.** Recuperação | 0,42 s | 4,0 req/s | 0% | 0,01 | 0 |

**Conclusões:**
- Cada falha tem uma assinatura própria. Latência alta derruba o tráfego, porque os clientes esperam mais. Erros não alteram a latência.
- A saturação aparece **primeiro como fila** (requisições em andamento) e **depois como latência**.
- Sem os quatro sinais juntos, é fácil confundir causa e efeito.

---

## Evidências

Os prints ficam em `aula-1/prints/`:

- [ ] `docker compose ps` com os 5 serviços
- [ ] Prometheus → Status → Target health (`loja-api` UP)
- [ ] Grafana → dashboard *Loja API · 4 Golden Signals* durante o game day
- [ ] Status page `/status/loja` com o Checkout vermelho e o incidente publicado
