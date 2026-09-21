# Carpeta `data/eval`

Esta carpeta está orientada a **evaluación y validación**: datasets de evaluación, “golden sets”, resultados de experimentos, métricas, y artefactos usados para medir calidad de modelos, RAG, agentes o pipelines.

- **Propósito principal**: centralizar los insumos y salidas de evaluación para asegurar mejoras medibles a lo largo de los hitos del proyecto.
- **Recomendación**: documenta cada set de evaluación (qué mide, cómo se construyó, criterios de éxito) y evita incluir datos sensibles; si es necesario, usa datos sintéticos o anonimizados.

## Artefactos del pronóstico de ventas

`sales_forecast_actual_vs_predicted.png`, `sales_forecast_metrics.md` y `sales_forecast_metrics.json` miden el chequeo histórico de 2024-2025. La banda sombreada es un rango residual empírico, no un intervalo de confianza formal.
