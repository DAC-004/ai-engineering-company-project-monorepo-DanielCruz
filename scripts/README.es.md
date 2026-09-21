# Carpeta `scripts`

Esta carpeta contiene **scripts auxiliares** del monorepo: automatizaciones de desarrollo, utilidades de mantenimiento, tareas repetitivas (setup, lint, migraciones, generación de datos, etc.) y tooling interno.

- **Propósito principal**: agrupar herramientas de soporte que no pertenecen a una app/agente/pipeline específico, pero facilitan el trabajo del equipo.
- **Recomendación**: documenta cada script (qué hace, parámetros, requisitos, ejemplos de uso) y procura que sean reproducibles (y seguros) en distintos entornos.

## Pronóstico de ventas (HealthCore)

```bash
uv run python scripts/train_sales_forecast.py
uv run pytest tests/pipelines -q
```

- `train_sales_forecast.py` valida `data/raw/healthcore_sales.csv`, entrena Random Forest y escribe métricas y la gráfica
- La evaluación es histórica de un paso hacia adelante (2024-2025), no un pronóstico único a 24 meses desde finales de 2023
- PSI compara `visits_count` de entrenamiento frente a prueba (volumen consolidado, no mezcla US/UK)
- K2 es el estadístico de normalidad D'Agostino-Pearson sobre residuos de prueba; no es una métrica de exactitud del pronóstico

La versión detallada está en [README.md](./README.md).
