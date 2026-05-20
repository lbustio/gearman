# Gearman Demo

Proyecto para demostrar Gearman con Python usando una arquitectura separada por
responsabilidades: dominio, adaptadores Gearman, casos de uso, API HTTP, CLI y
consola web.

Incluye:

- Worker pool dinámico: un worker por CPU detectada, con tope configurable de 64.
- Asignación de tareas por worker.
- API FastAPI y consola web.
- Pipeline fan-out/fan-in sobre Gearman.
- Cuadro de mando con telemetría de workers.
- Resultados por worker y resultado final agregado.
- Logs independientes por worker.

## Tareas

Tareas registradas en Gearman:

- `demo.analyze`: analiza texto, tokens, frecuencia de palabras y sentimiento básico.
- `demo.shard`: particiona texto en chunks para simular distribución de trabajo.
- `demo.bg_log`: recibe telemetría/log en background.

Caso de uso expuesto por API:

- `POST /api/pipeline`: ejecuta `demo.shard` y luego `demo.analyze` por cada shard.

## Estructura

```text
src/gearman_demo/
  domain/
    text_tasks.py        # lógica pura: tokenización, análisis y sharding
    task_catalog.py      # contrato de tareas publicadas por workers
  gearman/
    client.py            # envío de jobs a Gearman
    codec.py             # JSON para payloads/resultados Gearman
    compat.py            # parches de compatibilidad gearman3/Python 3.12+
    telemetry.py         # eventos compartidos y logs por worker
    worker_assignment.py # asignación de tareas por worker/CPU
    worker.py            # worker Gearman instrumentado
  application/
    service.py           # casos de uso, historial, reportes y pipeline
  interfaces/
    cli/
      client_demo.py     # demo por terminal
    http/
      api.py             # FastAPI
      schemas.py         # contratos Pydantic
    web/
      index.html         # consola web
```

Regla de dependencias:

- `domain` no depende de Gearman, FastAPI ni CLI.
- `gearman` adapta el protocolo Gearman y la telemetría.
- `application` orquesta casos de uso y estado local.
- `interfaces` expone HTTP, web y CLI.

Ver también [docs/architecture.md](docs/architecture.md).

## Requisitos

- Python 3.10+
- `gearmand` instalado para ejecutar jobs reales.

Instalar `gearmand` en Ubuntu/Debian:

```bash
sudo apt install gearman-job-server
```

En macOS con Homebrew:

```bash
brew install gearman
```

El paquete Python usado es `gearman3`, que se importa como `gearman`.

## Instalación

```bash
cd /home/lbustio/Code/python/gearman
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Ejecutar Todo

```bash
cd /home/lbustio/Code/python/gearman
python main.py
```

`main.py` hace lo siguiente:

- usa automáticamente `.venv/bin/python` si existe;
- inicia `gearmand` si el puerto `4730` está libre;
- detecta CPUs con `os.cpu_count()`;
- levanta un worker por CPU, con tope de 64;
- arranca la API FastAPI;
- expone la consola web.

Abre:

- Web: `http://127.0.0.1:8000/`
- Swagger: `http://127.0.0.1:8000/docs`

Para detener todo:

```text
Ctrl-C
```

## Worker Pool

Por defecto:

```bash
python main.py
```

Forzar cantidad exacta de workers:

```bash
python main.py --workers 4
```

Usar CPUs detectados, pero limitar el máximo:

```bash
python main.py --max-workers 16
```

Política de asignación:

- Si hay más tareas que workers, un worker registra varias tareas.
- Si hay más workers que tareas, las tareas se repiten round-robin.
- Ejemplo: `cpu-01`, `cpu-02`, ..., `cpu-64`.

## Observabilidad

La consola web muestra:

- **Cuadro de mando Gearman**: workers, PID, tarea actual, estado y duración.
- **Resultados por worker**: resumen de lo que produjo cada worker.
- **Resultado seleccionado**: respuesta final/agregada del job.
- **Logs de ejecución**: eventos de API y workers.
- **Historial local**: jobs enviados desde la API.

Eventos compartidos:

```text
.runtime/events.jsonl
```

Logs humanos por worker:

```text
.runtime/workers/cpu-01.log
.runtime/workers/cpu-02.log
...
```

Ver logs en terminal:

```bash
tail -f .runtime/workers/cpu-01.log
```

Cada log de worker documenta:

- arranque del worker;
- tareas registradas;
- job recibido;
- inicio de procesamiento;
- resultado;
- errores;
- duración.

## Endpoints

- `GET /api/health`: estado del API y servidor Gearman configurado.
- `GET /api/tasks`: catálogo de tareas disponibles.
- `POST /api/analyze`: ejecuta `demo.analyze`.
- `POST /api/shard`: ejecuta `demo.shard`.
- `POST /api/background-log`: envía `demo.bg_log`.
- `POST /api/pipeline`: orquesta `demo.shard` y `demo.analyze`.
- `GET /api/jobs`: historial local de jobs.
- `GET /api/jobs/{local_job_id}`: detalle de un job.
- `GET /api/events`: últimos eventos de ejecución.
- `GET /api/jobs/{local_job_id}/events`: eventos de un job específico.
- `GET /api/report`: reporte agregado.

## Demo Recomendada

1. Ejecuta `python main.py`.
2. Abre `http://127.0.0.1:8000/`.
3. Ejecuta `Pipeline`.
4. Mira `Cuadro de mando Gearman`.
5. Mira `Resultados por worker`.
6. Mira `Resultado seleccionado`.
7. Selecciona el job en el historial para filtrar sus eventos.
8. Abre un log de worker con `tail -f .runtime/workers/cpu-01.log`.

## Ejecución Manual

Usa estos comandos separados para depurar.

Gearman server:

```bash
gearmand --listen=127.0.0.1 --port=4730 --verbose INFO
```

Worker:

```bash
source .venv/bin/activate
python scripts/run_worker.py --host 127.0.0.1 --port 4730 --worker-index 0 --worker-count 1 --worker-id cpu-01
```

API + web:

```bash
source .venv/bin/activate
python scripts/run_api.py --host 127.0.0.1 --port 4730 --api-host 127.0.0.1 --api-port 8000
```

Cliente CLI:

```bash
source .venv/bin/activate
python scripts/run_demo.py "Gearman es excelente, rápido y productivo, aunque a veces da error"
```

## Pruebas

```bash
cd /home/lbustio/Code/python/gearman
source .venv/bin/activate
python -m unittest discover -s tests -v
```

## Compatibilidad

`gearman3` requiere parches para Python moderno:

- `array.fromstring` fue reemplazado por `array.frombytes`.
- Algunos nombres de tarea llegan desde Gearman como `bytes` y se normalizan a `str`.
- Los eventos y respuestas se sanitizan para ser JSON serializable.

Estos parches viven en `src/gearman_demo/gearman/compat.py` y están cubiertos por tests.

## Limitaciones Actuales

- Historial y eventos de API viven en memoria del proceso API.
- Telemetría multiproceso se guarda en archivos locales bajo `.runtime/`.
- El pipeline ejecuta los análisis de shards de forma secuencial desde la API.
- Una versión más avanzada podría usar batch submit, persistencia externa y métricas Prometheus.
