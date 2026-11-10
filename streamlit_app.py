import graphviz
import pandas as pd
import streamlit as st
from pulp import PulpSolverError

from modelo import COMUNICACIONES_BASE, ENLACES_BASE, NODOS, TOLERANCIA, resolver


ESCENARIOS = {
    "Caso base": "Demandas y capacidades originales.",
    "Falla del enlace 3 → 6": "El enlace 3 → 6 queda desactivado.",
    "Aumento de demanda de F1": "F1 aumenta de 6 a 10 Gbps.",
    "Ampliación del enlace 3 → 6": "Su capacidad aumenta de 10 a 14 Gbps.",
    "Prueba de infactibilidad": "Se desactivan las dos salidas del servidor 1.",
}
ESTADOS = {"Optimal": "Óptimo", "Infeasible": "Infactible", "Unbounded": "No acotado"}
COLORES = {
    "Disponible": "#64748b",
    "En uso": "#007a66",
    "Saturado": "#c2410c",
    "Desactivado": "#a1a1aa",
    "Sin capacidad": "#a1a1aa",
}


def datos_escenario(nombre):
    enlaces = ENLACES_BASE.copy()
    comunicaciones = COMUNICACIONES_BASE.copy()
    desactivados = set()
    if nombre == "Falla del enlace 3 → 6":
        desactivados.add((3, 6))
    elif nombre == "Aumento de demanda de F1":
        comunicaciones["F1"] = (1, 8, 10)
    elif nombre == "Ampliación del enlace 3 → 6":
        enlaces[3, 6] = (enlaces[3, 6][0], 14)
    elif nombre == "Prueba de infactibilidad":
        desactivados.update(((1, 2), (1, 3)))
    return enlaces, comunicaciones, desactivados


def tabla_enlaces(enlaces, desactivados, resultado):
    filas = []
    flujos = resultado.get("flujos")
    for (i, j), (precio, capacidad) in enlaces.items():
        efectivo = 0 if (i, j) in desactivados else capacidad
        cargas = {k: flujos[k, i, j] if flujos is not None else None
                  for k in COMUNICACIONES_BASE}
        total = sum(cargas.values()) if flujos is not None else None
        estado = "Disponible"
        if (i, j) in desactivados:
            estado = "Desactivado"
        elif efectivo == 0:
            estado = "Sin capacidad"
        elif total is not None and total >= efectivo - TOLERANCIA:
            estado = "Saturado"
        elif total is not None and total > TOLERANCIA:
            estado = "En uso"
        filas.append({
            "Enlace": f"{i} → {j}",
            "Estado": estado,
            "Costo por Gbps": precio,
            "Capacidad efectiva (Gbps)": efectivo,
            **cargas,
            "Carga (Gbps)": total,
            "Utilización (%)": 100 * total / efectivo if total is not None and efectivo else None,
        })
    return pd.DataFrame(filas)


def dibujar_red(enlaces, tabla):
    grafico = graphviz.Digraph(graph_attr={"rankdir": "LR", "pad": "0.2"})
    grafico.attr("node", shape="circle", style="filled", fillcolor="#eff6ff",
                 color="#2563eb", fontcolor="#172554")
    for nodo in NODOS:
        grafico.node(str(nodo))
    for (i, j), fila in zip(enlaces, tabla.to_dict("records")):
        estado = fila["Estado"]
        capacidad = fila["Capacidad efectiva (Gbps)"]
        carga = fila["Carga (Gbps)"]
        etiqueta = f"{capacidad:g} Gbps" if pd.isna(carga) else f"{carga:g}/{capacidad:g}"
        grafico.edge(str(i), str(j), label=etiqueta, color=COLORES[estado],
                     fontcolor=COLORES[estado],
                     style="dashed" if estado in {"Desactivado", "Sin capacidad"} else "solid",
                     penwidth="2" if estado in {"En uso", "Saturado"} else "1")
    st.graphviz_chart(grafico, width="stretch")
    st.caption("Etiquetas de enlace en Gbps. Con solución óptima se muestra carga/capacidad. "
               "Gris: disponible, verde: en uso, naranja: saturado, línea discontinua: inactivo o sin capacidad.")


@st.cache_data
def comparar_escenarios():
    filas = []
    for nombre in ESCENARIOS:
        enlaces, comunicaciones, desactivados = datos_escenario(nombre)
        resultado = resolver(enlaces, comunicaciones, desactivados)
        tabla = tabla_enlaces(enlaces, desactivados, resultado)
        optimo = resultado["estado"] == "Optimal"
        enlace_clave = tabla.loc[tabla["Enlace"] == "3 → 6"].iloc[0]
        filas.append({
            "Escenario": nombre,
            "Estado": ESTADOS.get(resultado["estado"], resultado["estado"]),
            "Demanda (Gbps)": sum(demanda for _, _, demanda in comunicaciones.values()),
            "Costo mínimo": resultado.get("costo"),
            "Carga 3 → 6 (Gbps)": enlace_clave["Carga (Gbps)"],
            "Capacidad 3 → 6 (Gbps)": enlace_clave["Capacidad efectiva (Gbps)"],
            "Enlaces saturados": int((tabla["Estado"] == "Saturado").sum()) if optimo else None,
        })
    comparacion = pd.DataFrame(filas)
    comparacion["Cambio de costo vs. base"] = (
        comparacion["Costo mínimo"] - comparacion.loc[0, "Costo mínimo"]
    )
    return comparacion


st.set_page_config(page_title="DataNet Analytics", page_icon="🔗", layout="wide")
st.title("DataNet Analytics")
st.write("Distribuye tres comunicaciones en una red dirigida con el menor costo posible, "
         "respetando la demanda y la capacidad compartida de los enlaces.")

configuracion, comparacion = st.tabs(["Simulador", "Comparación de escenarios"])

with configuracion:
    escenario = st.selectbox("Escenario inicial", list(ESCENARIOS))
    st.caption(ESCENARIOS[escenario])
    enlaces, comunicaciones, desactivados = datos_escenario(escenario)

    with st.expander("Editar datos del escenario"):
        demanda = st.columns(len(comunicaciones))
        for columna, (k, (origen, destino, valor)) in zip(demanda, comunicaciones.items()):
            valor_editado = columna.number_input(
                f"{k} · {origen} → {destino} (Gbps)", min_value=0.0, value=float(valor),
                step=0.5, key=f"{escenario}-{k}",
            )
            comunicaciones[k] = (origen, destino, valor_editado)

        datos = pd.DataFrame([
            {"Enlace": f"{i} → {j}", "Costo por Gbps": float(costo),
             "Capacidad (Gbps)": float(capacidad), "Activo": (i, j) not in desactivados}
            for (i, j), (costo, capacidad) in enlaces.items()
        ])
        cambios = st.data_editor(
            datos, key=f"enlaces-{escenario}", width="stretch", hide_index=True,
            disabled=["Enlace"], column_config={
                "Costo por Gbps": st.column_config.NumberColumn(min_value=0, required=True),
                "Capacidad (Gbps)": st.column_config.NumberColumn(min_value=0, required=True),
                "Activo": st.column_config.CheckboxColumn(required=True),
            },
        )
        desactivados = set()
        for enlace, fila in zip(enlaces, cambios.to_dict("records")):
            enlaces[enlace] = (fila["Costo por Gbps"], fila["Capacidad (Gbps)"])
            if not fila["Activo"]:
                desactivados.add(enlace)

    firma = (escenario, tuple(enlaces.items()), tuple(comunicaciones.items()),
             frozenset(desactivados))
    if st.button("Resolver modelo", type="primary"):
        st.session_state.pop("solucion", None)
        try:
            st.session_state.solucion = (firma, resolver(enlaces, comunicaciones, desactivados))
        except (ValueError, RuntimeError, PulpSolverError) as error:
            st.error(f"Error al resolver: {error}")

    firma_guardada, resultado = st.session_state.get("solucion", (None, {}))
    if firma_guardada != firma:
        resultado = {}
        st.info("Pulsa Resolver modelo para calcular el resultado con los datos actuales.")
    elif resultado["estado"] == "Optimal":
        metricas = st.columns(3)
        metricas[0].metric("Estado", "Óptimo")
        metricas[1].metric("Costo mínimo", f"{resultado['costo']:,.2f}")
        metricas[2].metric("Demanda entregada",
                           f"{sum(d for _, _, d in comunicaciones.values()):g} Gbps")
    elif resultado["estado"] == "Infeasible":
        st.warning("Infactible. La red configurada no puede entregar todas las demandas.")
    else:
        estado = resultado["estado"]
        st.warning(f"Estado del optimizador: {ESTADOS.get(estado, estado)}.")

    detalle = tabla_enlaces(enlaces, desactivados, resultado)
    st.subheader("Red de servidores")
    dibujar_red(enlaces, detalle)
    if "flujos" in resultado:
        st.subheader("Tráfico por enlace")
        st.caption("F1, F2, F3 y carga total se expresan en Gbps.")
        st.dataframe(detalle.round(3), hide_index=True, width="stretch")

with comparacion:
    st.subheader("Caso base, escenarios y prueba adicional")
    st.caption("Cada escenario parte de los datos originales, de forma independiente a los cambios del simulador.")
    if st.button("Comparar escenarios"):
        st.session_state.mostrar_comparacion = True
    if st.session_state.get("mostrar_comparacion"):
        try:
            st.dataframe(comparar_escenarios().round(3), hide_index=True, width="stretch")
        except (ValueError, RuntimeError, PulpSolverError) as error:
            st.error(f"Error al comparar: {error}")
