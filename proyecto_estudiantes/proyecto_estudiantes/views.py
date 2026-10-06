"""CONTROLADOR: reglas del negocio para Estudiantes.

Reglas de esta capa:
  - Cero print() y cero input(): no habla con el usuario.
  - Devuelve tuplas (exito, mensaje) o datos; la Vista decide cómo mostrarlos.
  - Valida ANTES de tocar el archivo.
"""
from models import Estudiante, CAMPOS_ESTUDIANTE
from shared.json_manager import GestorJSON
from shared.herramientas import es_email_valido

gestor = GestorJSON("data/estudiantes.json")

# TUPLAS de configuración: fijas, nadie las modifica en tiempo de ejecución
CAMPOS_OBLIGATORIOS = ("nombre", "apellido", "email", "carnet")
CAMPOS_BUSCABLES = ("nombre", "apellido", "email", "carnet")
NOTA_MIN, NOTA_MAX = 0, 20


# ===================== AYUDAS INTERNAS =====================

def carnets_registrados(excepto_id=None):
    """CONJUNTO con los carnets ya usados: detectar duplicados es instantáneo."""
    return {
        registro["carnet"].strip().upper()
        for registro in gestor.leer()
        if registro["id"] != excepto_id
    }


def emails_registrados(excepto_id=None):
    """CONJUNTO con los emails ya usados."""
    return {
        registro["email"].strip().lower()
        for registro in gestor.leer()
        if registro["id"] != excepto_id
    }


def siguiente_id():
    ids = [registro["id"] for registro in gestor.leer()]
    return max(ids) + 1 if ids else 1      # caso explícito para lista vacía


# ===================== C · CREATE =====================

def crear_estudiante(datos):
    """datos: diccionario con las claves de CAMPOS_ESTUDIANTE. Devuelve (exito, mensaje)."""
    try:
        # 1) Normalizo: un diccionario con todos los campos, sin espacios sobrantes
        valores = {campo: str(datos.get(campo, "")).strip() for campo in CAMPOS_ESTUDIANTE}

        # 2) Obligatorios (recorro la TUPLA)
        faltantes = [campo for campo in CAMPOS_OBLIGATORIOS if not valores[campo]]
        if faltantes:
            return False, f"Faltan campos obligatorios: {', '.join(faltantes)}"

        # 3) Formato del email
        if not es_email_valido(valores["email"]):
            return False, f"El email '{valores['email']}' no tiene un formato válido"

        # 4) Carnet duplicado: pertenencia instantánea en un CONJUNTO
        if valores["carnet"].upper() in carnets_registrados():
            return False, f"El carnet {valores['carnet']} ya está registrado"

        # 5) Email duplicado
        if valores["email"].lower() in emails_registrados():
            return False, "Ese email ya está registrado"

        # 6) Creo el objeto del Modelo. ** convierte el diccionario en argumentos
        estudiante = Estudiante(siguiente_id(), **valores)

        # 7) Agrego a la LISTA y guardo
        registros = gestor.leer()
        registros.append(estudiante.a_diccionario())
        if not gestor.guardar(registros):
            return False, "No se pudo escribir el archivo"

        return True, f"Estudiante {estudiante.obtener_nombre_completo()} creado con id {estudiante.id}"

    except Exception as error:
        return False, f"Error inesperado: {error}"


# ===================== R · READ =====================

def obtener_todos():
    """LISTA de objetos Estudiante."""
    return [Estudiante.desde_diccionario(registro) for registro in gestor.leer()]


def obtener_por_id(id_estudiante):
    for estudiante in obtener_todos():
        if estudiante.id == id_estudiante:
            return estudiante
    return None


# ===================== S · SEARCH =====================

def buscar_estudiantes(termino):
    """Búsqueda lineal por los campos de CAMPOS_BUSCABLES (y por materia inscrita)."""
    termino = termino.strip().lower()
    if not termino:
        return []

    encontrados = []
    for registro in gestor.leer():
        coincide = any(
            termino in str(registro.get(campo, "")).lower()
            for campo in CAMPOS_BUSCABLES
        )
        if not coincide:
            coincide = any(termino in materia.lower() for materia in registro.get("materias", []))
        if coincide:
            encontrados.append(Estudiante.desde_diccionario(registro))
    return encontrados


# ===================== U · UPDATE =====================

def actualizar_estudiante(id_estudiante, cambios):
    """cambios: diccionario solo con los campos que se quieren modificar."""
    try:
        # DIFERENCIA DE CONJUNTOS: ¿mandaron algún campo que no existe?
        desconocidos = set(cambios) - set(CAMPOS_ESTUDIANTE)
        if desconocidos:
            return False, f"Campos no válidos: {', '.join(sorted(desconocidos))}"

        if not cambios:
            return False, "No se indicó ningún cambio"

        if "email" in cambios:
            if not es_email_valido(cambios["email"]):
                return False, "El email no tiene un formato válido"
            if cambios["email"].strip().lower() in emails_registrados(excepto_id=id_estudiante):
                return False, "Ese email ya lo usa otro estudiante"

        if "carnet" in cambios:
            if not cambios["carnet"].strip():
                return False, "El carnet no puede quedar vacío"
            if cambios["carnet"].strip().upper() in carnets_registrados(excepto_id=id_estudiante):
                return False, "Ese carnet ya lo usa otro estudiante"

        registros = gestor.leer()
        posicion = None
        for indice, registro in enumerate(registros):    # enumerate: índice y valor
            if registro["id"] == id_estudiante:
                posicion = indice
                break

        if posicion is None:
            return False, f"No existe un estudiante con id {id_estudiante}"

        registros[posicion].update({k: str(v).strip() for k, v in cambios.items()})
        if not gestor.guardar(registros):
            return False, "No se pudo escribir el archivo"
        return True, f"Estudiante {id_estudiante} actualizado ({len(cambios)} campo/s)"

    except Exception as error:
        return False, f"Error inesperado: {error}"


# ===================== D · DELETE =====================

def eliminar_estudiante(id_estudiante):
    registros = gestor.leer()
    # Construyo una LISTA NUEVA sin ese registro: nunca borro mientras recorro
    quedan = [registro for registro in registros if registro["id"] != id_estudiante]

    if len(quedan) == len(registros):
        return False, f"No existe un estudiante con id {id_estudiante}"

    if not gestor.guardar(quedan):
        return False, "No se pudo escribir el archivo"
    return True, f"Estudiante {id_estudiante} eliminado"


# ===================== NOTAS, PROMEDIO Y CONJUNTOS =====================

def agregar_nota(id_estudiante, materia, nota):
    """Agrega una nota (0 a 20) a una materia. Devuelve (exito, mensaje)."""
    try:
        materia = str(materia).strip()
        if not materia:
            return False, "La materia es obligatoria"

        # La nota puede llegar como texto desde la Vista: la convierto aquí
        try:
            valor = float(str(nota).replace(",", "."))
        except ValueError:
            return False, "La nota debe ser un número"

        if not (NOTA_MIN <= valor <= NOTA_MAX):
            return False, f"La nota debe estar entre {NOTA_MIN} y {NOTA_MAX}"
        if valor.is_integer():
            valor = int(valor)

        registros = gestor.leer()
        for indice, registro in enumerate(registros):
            if registro["id"] == id_estudiante:
                estudiante = Estudiante.desde_diccionario(registro)
                estudiante.agregar_nota(materia, valor)       # dict de listas + set
                registros[indice] = estudiante.a_diccionario()
                if not gestor.guardar(registros):
                    return False, "No se pudo escribir el archivo"
                return True, f"Nota {valor} agregada en {materia}"

        return False, f"No existe un estudiante con id {id_estudiante}"

    except Exception as error:
        return False, f"Error inesperado: {error}"


def obtener_promedio(id_estudiante):
    """Devuelve (exito, promedio_o_mensaje)."""
    estudiante = obtener_por_id(id_estudiante)
    if estudiante is None:
        return False, f"No existe un estudiante con id {id_estudiante}"
    return True, estudiante.obtener_promedio()


def materias_ofertadas():
    """CONJUNTO con todas las materias inscritas por todos los estudiantes, sin repetir."""
    todas = set()
    for estudiante in obtener_todos():
        todas |= estudiante.materias          # UNIÓN de conjuntos
    return todas


def estudiantes_en_comun(id_a, id_b):
    """Materias que comparten dos estudiantes (INTERSECCIÓN de conjuntos).

    Devuelve (True, lista_ordenada) o (False, mensaje_de_error).
    """
    if id_a == id_b:
        return False, "Debe elegir dos estudiantes distintos"

    estudiante_a = obtener_por_id(id_a)
    estudiante_b = obtener_por_id(id_b)
    if estudiante_a is None:
        return False, f"No existe un estudiante con id {id_a}"
    if estudiante_b is None:
        return False, f"No existe un estudiante con id {id_b}"

    return True, sorted(estudiante_a.materias_en_comun(estudiante_b))
