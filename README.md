# Trabajo_Final_Opt

## DataNet Analytics

Simulador de flujo multicomunicación. Minimiza el costo de transmitir F1, F2 y F3
en una red de 8 servidores y 14 enlaces con capacidades compartidas.

### Ejecutar localmente

```bash
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

En el simulador, selecciona un escenario y pulsa **Resolver modelo**. Puedes
editar demandas, costos, capacidades y disponibilidad de enlaces. En la pestaña
**Comparación de escenarios** se ejecutan los escenarios predefinidos con datos
independientes de las ediciones del simulador.

El modelo de PuLP está en `modelo.py`. Para ejecutar el caso base en consola,
usa `python modelo.py`. Debe devolver un costo óptimo de 176 unidades monetarias.

Para desplegar en Streamlit Community Cloud, elige la rama `main` y
`streamlit_app.py` como archivo principal.
