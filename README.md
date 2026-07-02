# Perfil de Élite — Scouting Dashboard

Dashboard interactivo del sistema de detección de talento cross-liga (1ª RFEF → LaLiga),
desarrollado como parte del TFM *Big Data Aplicado al Scouting en Fútbol* (Sevilla FC / Master).

Metodología: PCA + K-Means (arquetipos sobre LaLiga) → proyección por similitud coseno sobre
1ª RFEF → score final (similitud + sobre-rendimiento contextual + ajuste por edad) →
LightGBM + SHAP para explicabilidad.

## Ejecutar en local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Estructura

- `app.py` — aplicación Streamlit (ranking, ficha de jugador, comparador, validación empírica)
- `data/rfef_final_con_shap.csv` — jugadores de 1ª RFEF proyectados, con score y SHAP
- `data/laliga_arquetipos_fase_a.csv` — arquetipos de referencia construidos sobre LaLiga

## Despliegue

Desplegado en Streamlit Community Cloud conectando este repositorio.
