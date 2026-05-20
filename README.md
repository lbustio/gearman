
# Gearman Demo

Demostración de Gearman en Python con arquitectura limpia, API FastAPI, consola web y worker pool dinámico.

## Estructura del proyecto

```
src/gearman_demo/
  domain/           # lógica pura: tokenización, análisis, sharding
  gearman/          # adaptadores Gearman, telemetría, workers
  application/      # casos de uso, historial, reportes, pipeline
  interfaces/
    cli/            # demo por terminal
    http/           # API FastAPI y contratos Pydantic
    web/            # consola web (index.html)
scripts/            # runners para worker, API, demo
main.py             # orquestador: levanta gearmand, workers y API
install_all.sh      # instala TODO: sistema, entorno, dependencias
```

## Requisitos

- Python 3.10+
- gearmand (servidor Gearman)

## Instalación rápida (recomendada)

```bash
cd /home/lbustio/Code/python/gearman
bash install_all.sh
source .venv/bin/activate
```

Esto instala:
- gearmand y dependencias de sistema (si es Linux/apt o yum)
- entorno virtual Python y dependencias del proyecto
- el paquete en modo editable

Si tu sistema no es compatible, instala gearmand y libgearman-dev manualmente.

## Ejecución unificada

```bash
python main.py
```

Esto levanta automáticamente:
- gearmand (o usa uno ya corriendo)
- un worker por CPU
- la API FastAPI y la consola web

Accede a la web en: http://127.0.0.1:8000/
Swagger: http://127.0.0.1:8000/docs

## Tareas y API

Tareas registradas en Gearman:
- `demo.analyze`: análisis de texto, tokens, sentimiento
- `demo.shard`: particionado de texto
- `demo.bg_log`: telemetría/log en background

Caso de uso expuesto por API:
- `POST /api/pipeline`: ejecuta `demo.shard` y luego `demo.analyze` por cada shard

## Personalización y ayuda

`python main.py --help` muestra todas las opciones (puertos, workers, etc).

---

Ver también [docs/architecture.md](docs/architecture.md) para detalles de diseño.

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
