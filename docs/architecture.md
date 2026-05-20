# Arquitectura

Este proyecto usa una separación por responsabilidades, no por frameworks.

## Capas

```text
interfaces -> application -> gearman -> domain
```

La regla práctica es que el dominio no importa nada de las capas externas.

## Responsabilidades

- `domain`: reglas puras de procesamiento de texto y catálogo lógico de tareas.
- `gearman`: adaptación al protocolo Gearman, codec JSON y worker.
- `application`: casos de uso, historial local, eventos de ejecución, reportes
  y pipeline.
- `interfaces`: entradas para usuarios y sistemas externos: HTTP, CLI y web.

## Flujo principal

1. La webapp llama un endpoint de FastAPI.
2. `interfaces/http/api.py` valida el request con schemas Pydantic.
3. `application/service.py` ejecuta el caso de uso.
4. `gearman/client.py` envía jobs a `gearmand`.
5. `gearman/worker.py` recibe jobs y llama funciones puras de `domain`.
6. `application/service.py` registra eventos para que la webapp muestre logs.

## Decisiones

- El worker registra tareas desde `domain/task_catalog.py` para evitar strings
  dispersos.
- `gearman/worker_assignment.py` define la asignación de tareas por worker:
  si hay más tareas que workers, un worker registra varias tareas; si hay más
  workers que tareas, las tareas se repiten round-robin.
- El JSON de Gearman vive en `gearman/codec.py`, no en el dominio.
- La consola web es estática para mantener bajo el costo de demo.
- Los eventos de ejecución se mantienen en memoria y se exponen por
  `/api/events` y `/api/jobs/{local_job_id}/events`.
- Los workers escriben telemetría multiproceso en `.runtime/events.jsonl`; la
  API la combina con eventos propios para alimentar el cuadro de mando.
- Cada worker mantiene un log independiente en `.runtime/workers/{worker_id}.log`
  con una narrativa humana de sus acciones.
- Cada evento `completed` del worker incluye `result_summary`; la webapp usa
  esos resúmenes para mostrar resultados por worker junto al resultado final
  agregado del job.
- `demo.pipeline` vive en aplicación porque es orquestación, no una tarea
  Gearman registrada directamente.

## Límites actuales

- El historial es local en memoria del proceso API.
- Los background jobs solo guardan el handle retornado por Gearman.
- La agregación del pipeline es secuencial; una versión más real debería usar
  batch submit o workers paralelos y consultar estado de handles.
