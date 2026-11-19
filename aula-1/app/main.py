"""API da Loja instrumentada com OpenTelemetry. As métricas ficam em :9464/metrics para o Prometheus."""
import asyncio, random
from fastapi import FastAPI, HTTPException
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from prometheus_client import start_http_server

# 1. Provider de métricas: o leitor Prometheus expõe tudo em /metrics (porta 9464)
start_http_server(9464)
metrics.set_meter_provider(MeterProvider(
    resource=Resource.create({"service.name": "loja-api", "service.version": "1.0.0"}),
    metric_readers=[PrometheusMetricReader()]))

# 2. Instrumentação automática: duração e requisições HTTP, CPU e memória do processo
app = FastAPI(title="Loja API")
FastAPIInstrumentor.instrument_app(app)
SystemMetricsInstrumentor(config={"process.cpu.utilization": None, "process.memory.usage": None}).instrument()

# 3. Métrica de negócio criada à mão
meter = metrics.get_meter("loja.api")
pedidos = meter.create_counter("loja.pedidos", unit="{pedido}", description="Pedidos finalizados")

# Chaos: latência extra e taxa de erro ajustáveis em tempo de execução
chaos = {"latencia": 0.0, "erro": 0.0}
PRODUTOS = {1: "Camiseta", 2: "Caneca", 3: "Mochila", 4: "Boné"}


async def simular(base):
    await asyncio.sleep(random.uniform(*base) + chaos["latencia"])
    if random.random() < chaos["erro"]:
        raise HTTPException(500, "falha simulada")


@app.get("/produtos")
async def listar():
    await simular((0.01, 0.05))
    return PRODUTOS


@app.get("/produtos/{pid}")
async def detalhar(pid: int):
    await simular((0.01, 0.08))
    if pid not in PRODUTOS:
        raise HTTPException(404, "produto não encontrado")
    return {"id": pid, "nome": PRODUTOS[pid]}


@app.post("/checkout")
async def checkout():
    await simular((0.1, 0.6))
    if random.random() < 0.02:
        raise HTTPException(503, "gateway de pagamento indisponível")
    pedidos.add(1, {"pagamento": random.choice(["pix", "cartao"])})
    return {"status": "aprovado"}


@app.get("/relatorio")
def relatorio():
    # Rota pesada de CPU: usada para provocar saturação
    total = sum(i * i for i in range(2_000_000))
    return {"linhas": total % 1000}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chaos")
async def ajustar_chaos(latencia: float = 0.0, erro: float = 0.0):
    chaos.update(latencia=latencia, erro=erro)
    return chaos
