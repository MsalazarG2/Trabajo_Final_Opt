"""Modelo lineal de flujo multicomunicación para DataNet Analytics."""

from math import isclose, isfinite

import pulp


NODOS = tuple(range(1, 9))

# Cada enlace se describe con (costo por Gbps, capacidad en Gbps).
ENLACES_BASE = {
    (1, 2): (4, 12),
    (1, 3): (6, 10),
    (2, 3): (2, 8),
    (2, 4): (5, 10),
    (2, 5): (7, 8),
    (3, 4): (3, 12),
    (3, 6): (5, 10),
    (4, 5): (2, 10),
    (4, 7): (6, 12),
    (5, 6): (3, 8),
    (5, 8): (5, 10),
    (6, 7): (2, 10),
    (6, 8): (4, 12),
    (7, 8): (3, 14),
}

# Cada comunicación se describe con (origen, destino, demanda en Gbps).
COMUNICACIONES_BASE = {
    "F1": (1, 8, 6),
    "F2": (2, 7, 5),
    "F3": (3, 8, 4),
}

TOLERANCIA = 1e-6


def resolver(enlaces, comunicaciones, desactivados=()):
    """Resuelve con CBC. Devuelve flujos y costo solo si son óptimos y válidos."""
    if enlaces.keys() != ENLACES_BASE.keys():
        raise ValueError("Se requieren los 14 enlaces de la red DataNet.")
    desactivados = set(desactivados)
    if not desactivados.issubset(enlaces):
        raise ValueError("Los enlaces desactivados deben pertenecer a la red.")
    for costo, capacidad in enlaces.values():
        if not all(isfinite(valor) and valor >= 0 for valor in (costo, capacidad)):
            raise ValueError("Los costos y capacidades deben ser finitos y no negativos.")
    for origen, destino, demanda in comunicaciones.values():
        if origen not in NODOS or destino not in NODOS or origen == destino:
            raise ValueError("Cada comunicación necesita dos nodos distintos de la red.")
        if not isfinite(demanda) or demanda < 0:
            raise ValueError("Las demandas deben ser finitas y no negativas.")



    modelo += x[k, [5,8]] =< 4

    modelo = pulp.LpProblem("DataNet", pulp.LpMinimize)
    # x[k, i, j] representa el flujo de k por i → j.
    x = {
        (k, i, j): pulp.LpVariable(f"x_{k}_{i}_{j}", lowBound=0)
        for k in comunicaciones
        for i, j in enlaces
    }
    capacidad_efectiva = {
        enlace: 0 if enlace in desactivados else capacidad
        for enlace, (_, capacidad) in enlaces.items()
    }

    # Función objetivo.
    modelo += pulp.lpSum(
        enlaces[i, j][0] * variable for (k, i, j), variable in x.items()
    ), "Costo_total"

    # Balance de flujo por comunicación y nodo.
    for k, (origen, destino, demanda) in comunicaciones.items():
        for nodo in NODOS:
            salidas = pulp.lpSum(x[k, i, j] for i, j in enlaces if i == nodo)
            entradas = pulp.lpSum(x[k, i, j] for i, j in enlaces if j == nodo)
            balance = demanda * (int(nodo == origen) - int(nodo == destino))
            modelo += salidas - entradas == balance, f"Balance_{k}_{nodo}"

    # Capacidad compartida por las tres comunicaciones.
    for i, j in enlaces:
        carga = pulp.lpSum(x[k, i, j] for k in comunicaciones)
        modelo += carga <= capacidad_efectiva[i, j], f"Capacidad_{i}_{j}"

    modelo.solve(pulp.PULP_CBC_CMD(msg=False))
    estado = pulp.LpStatus[modelo.status]
    if modelo.status != pulp.LpStatusOptimal:
        return {"estado": estado}

    flujos = {clave: variable.value() for clave, variable in x.items()}
    costo = sum(enlaces[i, j][0] * flujo for (_, i, j), flujo in flujos.items())
    # PuLP usa una variable auxiliar sin valor si todo costo unitario es cero.
    objetivo = pulp.value(modelo.objective)
    validar(enlaces, comunicaciones, capacidad_efectiva, flujos, costo, objetivo)
    return {
        "estado": estado,
        "costo": costo,
        "flujos": flujos,
        "capacidad_efectiva": capacidad_efectiva,
    }


def validar(enlaces, comunicaciones, capacidades, flujos, costo, objetivo):
    """Recalcula las restricciones con los valores devueltos por el solver."""
    for flujo in flujos.values():
        if not isfinite(flujo) or flujo < -TOLERANCIA:
            raise RuntimeError("El resultado contiene un flujo inválido.")

    for k, (origen, destino, demanda) in comunicaciones.items():
        for nodo in NODOS:
            salidas = sum(flujos[k, i, j] for i, j in enlaces if i == nodo)
            entradas = sum(flujos[k, i, j] for i, j in enlaces if j == nodo)
            esperado = demanda * (int(nodo == origen) - int(nodo == destino))
            if not isclose(salidas - entradas, esperado, abs_tol=TOLERANCIA):
                raise RuntimeError(f"Balance incorrecto para {k} en nodo {nodo}.")

    for (i, j), capacidad in capacidades.items():
        carga = sum(flujos[k, i, j] for k in comunicaciones)
        if carga > capacidad + TOLERANCIA:
            raise RuntimeError(f"Capacidad excedida en {i} → {j}.")

    if objetivo is None and all(precio == 0 for precio, _ in enlaces.values()):
        objetivo = 0
    if objetivo is None or not isclose(costo, objetivo, abs_tol=TOLERANCIA):
        raise RuntimeError("El costo recalculado difiere del objetivo de PuLP.")


if __name__ == "__main__":
    resultado = resolver(ENLACES_BASE, COMUNICACIONES_BASE)
    print(f"Estado del caso base: {resultado['estado']}")
    if resultado["estado"] == "Optimal":
        print(f"Costo total: {resultado['costo']:g} unidades monetarias")
        print("Flujos positivos (Gbps)")
        for (k, i, j), flujo in resultado["flujos"].items():
            if flujo > TOLERANCIA:
                print(f"{k} | {i} → {j} | {flujo:g}")
        print("Verificación de balances, capacidades y costo superada.")
