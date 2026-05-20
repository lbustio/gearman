# Gearman Demo

Demostración de Gearman en Python con arquitectura por responsabilidades, API FastAPI, consola web, worker pool dinámico y observabilidad por worker.

## Estructura

```text
src/gearman_demo/
  domain/           # lógica pura: análisis de texto, sharding, catálogo de tareas
  gearman/          # cliente, worker, codec, compatibilidad y telemetría Gearman
  application/      # casos de uso, historial, reportes y pipeline
  interfaces/
    cli/            # demo por terminal
    http/           # API FastAPI y contratos Pydantic
    web/            # consola web
scripts/            # runners para API, worker y demo CLI
main.py             # orquestador: gearmand + API + workers
install_all.sh      # instalación de sistema, venv y dependencias
docs/               # notas de arquitectura
```

## Requisitos

- Python 3.10+
- `gearmand` disponible en el sistema

Instalación rápida:

```bash
bash install_all.sh
source .venv/bin/activate
```

Si `gearmand` no está instalado, en Linux/apt normalmente basta con:

```bash
sudo apt install gearman-job-server
```

## Ejecución

```bash
python main.py
```

Esto hace lo siguiente:

- usa `.venv/bin/python` si existe;
- inicia `gearmand` si no hay uno escuchando;
- detecta CPUs con `os.cpu_count()`;
- levanta un worker por CPU, con tope de 64;
- asigna tareas a los workers con round-robin;
- arranca la API antes de los workers para recibir sus reportes de estado;
- expone la consola web.

URLs:

- Web: `http://127.0.0.1:8000/`
- Swagger: `http://127.0.0.1:8000/docs`

Para detener todo:

```text
Ctrl-C
```

## Worker Pool

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
- Si hay más workers que tareas, varias CPUs pueden ejecutar la misma tarea.
- Los workers se nombran con padding estable: `cpu-01`, `cpu-02`, ..., `cpu-64`.

## Tareas

Tareas Gearman registradas:

- `demo.analyze`: analiza texto, tokens y sentimiento.
- `demo.shard`: divide texto en fragmentos.
- `demo.bg_log`: ejecuta una acción background y deja telemetría.

Caso de uso compuesto:

- `POST /api/pipeline`: ejecuta `demo.shard` y luego `demo.analyze` por cada shard.

## Observabilidad

La consola web muestra:

- estado reportado por cada worker por HTTP: ocupado/libre, PID, jobs en curso, jobs procesados, jobs fallidos, tarea actual, última tarea y duración;
- resultados por worker;
- resultado final/agregado del job;
- logs de ejecución de API y workers;
- historial local de jobs enviados desde la API.

Los workers usan `WorkerStatusReporter` para enviar su estado a la API con:

```text
POST /api/worker-status
```

La web consulta el estado agregado con:

```text
GET /api/workers-status
```

Telemetría compartida:

```text
.runtime/events.jsonl
```

Logs humanos por worker:

```text
.runtime/workers/cpu-01.log
.runtime/workers/cpu-02.log
...
```

Ver un worker específico:

```bash
tail -f .runtime/workers/cpu-01.log
```

Cada log de worker documenta arranque, tareas registradas, jobs recibidos, inicio, fin, duración, resultados y errores.

## Endpoints

- `GET /api/health`: estado de API y servidor Gearman configurado.
- `GET /api/tasks`: catálogo de tareas.
- `POST /api/analyze`: ejecuta `demo.analyze`.
- `POST /api/shard`: ejecuta `demo.shard`.
- `POST /api/background-log`: envía `demo.bg_log`.
- `POST /api/pipeline`: orquesta `demo.shard` y `demo.analyze`.
- `POST /api/worker-status`: recibe reportes de estado de workers.
- `GET /api/workers-status`: lista el último estado reportado por cada worker.
- `GET /api/jobs`: historial local de jobs.
- `GET /api/jobs/{local_job_id}`: detalle de un job.
- `GET /api/events`: últimos eventos de ejecución.
- `GET /api/jobs/{local_job_id}/events`: eventos de un job específico.
- `GET /api/report`: reporte agregado.

## Demo Recomendada

1. Ejecuta `python main.py`.
2. Abre `http://127.0.0.1:8000/`.
3. Ejecuta `Pipeline`.
4. Mira el `Cuadro de mando Gearman`.
5. Revisa `Resultados por worker`.
6. Revisa `Resultado seleccionado`.
7. Selecciona un job del historial para filtrar sus eventos.
8. Mira el archivo de un worker con `tail -f .runtime/workers/cpu-01.log`.

## Ejecución Manual

Gearman server:

```bash
gearmand --listen=127.0.0.1 --port=4730 --verbose INFO
```

API + web:

```bash
source .venv/bin/activate
python scripts/run_api.py --host 127.0.0.1 --port 4730 --api-host 127.0.0.1 --api-port 8000
```

Worker:

```bash
source .venv/bin/activate
python scripts/run_worker.py --host 127.0.0.1 --port 4730 --worker-index 0 --worker-count 1 --worker-id cpu-01 --api-url http://127.0.0.1:8000
```

Cliente CLI:

```bash
source .venv/bin/activate
python scripts/run_demo.py "Gearman es excelente, rápido y productivo, aunque a veces da error"
```

## Pruebas

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

## Compatibilidad

`gearman3` requiere parches para Python moderno:

- `array.fromstring` fue reemplazado por `array.frombytes`.
- Algunos nombres de tarea llegan desde Gearman como `bytes` y se normalizan a `str`.
- Los eventos y respuestas se sanitizan para ser JSON serializable.

Estos parches viven en `src/gearman_demo/gearman/compat.py` y están cubiertos por tests.

## Limitaciones

- Historial y estado agregado de workers viven en memoria del proceso API.
- Telemetría multiproceso se guarda en archivos locales bajo `.runtime/`.
- El pipeline ejecuta los análisis de shards de forma secuencial desde la API.
- Una versión más avanzada podría usar batch submit, persistencia externa y métricas Prometheus.

Ver también [docs/architecture.md](docs/architecture.md).
