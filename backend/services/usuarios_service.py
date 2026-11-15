import os
import sqlite3
from datetime import datetime

from werkzeug.security import generate_password_hash

from dao.usuario_dao import UsuarioDAO
from database.conexion import BaseDeDatos
from services.excepciones import (
    AccesoDenegadoError,
    NoEncontradoError,
    ReglaNegocioError,
)
from services.seguridad import (
    generar_password_temporal,
    normalizar_email,
    validar_rol,
)

NOMBRE_ARCHIVO_CREDENCIALES = "credenciales_iniciales.txt"


class UsuariosService:
    """Administración de usuarios de los locales:
      - crea automáticamente el administrador de cada local nuevo,
      - permite al administrador aprobar o rechazar empleados,
      - da de alta perfiles con rol elegido y contraseña temporal,
      - arma el panel con todo lo que pasa en el local."""

    def __init__(self):
        self.db = BaseDeDatos()
        self.dao = UsuarioDAO(self.db)

    # ---------- administrador automático del local ----------
    def crear_administrador_local(self, sucursal_id, email=None, cx=None):
        """Crea el administrador de un local con contraseña temporal.
        Se llama DENTRO de la transacción que crea el local (parámetro cx):
        si algo falla acá, tampoco se crea el local."""
        email = normalizar_email(email) if email else f"admin.local{sucursal_id}@cdlocales.local"
        if self.dao.email_existe(email, cx=cx):
            raise ReglaNegocioError(f"Ya existe una cuenta con el correo {email}")
        password_temporal = generar_password_temporal()
        try:
            self.dao.crear(
                email, generate_password_hash(password_temporal), sucursal_id,
                rol="ADMINISTRADOR", estado="APROBADO", debe_cambiar_password=True, cx=cx)
        except sqlite3.IntegrityError as error:
            raise ReglaNegocioError(f"Ya existe una cuenta con el correo {email}") from error
        return {"email": email, "password_temporal": password_temporal}

    def asegurar_administradores(self):
        """Al iniciar el backend: todo local activo sin administrador recibe uno.
        Cubre los locales que existían antes de esta funcionalidad (por ejemplo los
        de datos_iniciales). Las credenciales se muestran en consola y se guardan en
        un archivo local que NO se sube al repositorio (.gitignore)."""
        creadas = []
        for local in self.dao.locales_sin_administrador():
            with self.db.transaccion() as cx:
                credenciales = self.crear_administrador_local(local["id"], cx=cx)
            creadas.append({"local": local["nombre"], **credenciales})
        if creadas:
            self._guardar_credenciales(creadas)
        return creadas

    def _guardar_credenciales(self, creadas):
        carpeta = os.path.dirname(os.path.abspath(self.db._ruta))
        ruta = os.path.join(carpeta, NOMBRE_ARCHIVO_CREDENCIALES)
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(ruta, "a", encoding="utf-8") as archivo:
            for c in creadas:
                linea = (f"{fecha} | {c['local']} | {c['email']} | "
                         f"contraseña temporal: {c['password_temporal']}")
                archivo.write(linea + "\n")
                print(f"[Administrador creado] {linea}")
        print(f"Credenciales guardadas en {ruta} (se piden cambiar en el primer ingreso).")

    # ---------- gestión del equipo (solo administrador del local) ----------
    def equipo(self, admin):
        return self.dao.listar_por_sucursal(admin["sucursal_id"])

    def aprobar(self, admin, usuario_id, rol=None):
        """Aprueba una cuenta pendiente y le genera una contraseña temporal.
        El administrador puede confirmar el rol pedido o cambiarlo."""
        usuario = self._del_mismo_local(admin, usuario_id)
        rol = validar_rol(rol) if rol is not None else usuario["rol"]
        password_temporal = generar_password_temporal()
        cambiadas = self.dao.resolver_pendiente(
            usuario_id, "APROBADO", rol, admin["id"],
            password_hash=generate_password_hash(password_temporal))
        if not cambiadas:
            raise ReglaNegocioError("Esta cuenta ya fue resuelta por otro administrador")
        return {"usuario": self.dao.obtener(usuario_id),
                "password_temporal": password_temporal}

    def rechazar(self, admin, usuario_id, motivo=None):
        usuario = self._del_mismo_local(admin, usuario_id)
        motivo = motivo.strip() if isinstance(motivo, str) and motivo.strip() else None
        cambiadas = self.dao.resolver_pendiente(
            usuario_id, "RECHAZADO", usuario["rol"], admin["id"], motivo=motivo)
        if not cambiadas:
            raise ReglaNegocioError("Esta cuenta ya fue resuelta por otro administrador")
        return self.dao.obtener(usuario_id)

    def alta_directa(self, admin, email, rol):
        """El administrador crea un perfil (eligiendo el rol) ya aprobado,
        con contraseña temporal que el usuario debe cambiar al entrar."""
        email = normalizar_email(email)
        validar_rol(rol)
        if self.dao.email_existe(email):
            raise ReglaNegocioError("Ya existe una cuenta con ese correo")
        password_temporal = generar_password_temporal()
        try:
            usuario_id = self.dao.crear(
                email, generate_password_hash(password_temporal), admin["sucursal_id"],
                rol=rol, estado="APROBADO", debe_cambiar_password=True,
                aprobado_por_usuario_id=admin["id"])
        except sqlite3.IntegrityError as error:
            raise ReglaNegocioError("Ya existe una cuenta con ese correo") from error
        return {"usuario": self.dao.obtener(usuario_id),
                "password_temporal": password_temporal}

    def panel(self, admin):
        return self.dao.panel_local(admin["sucursal_id"])

    def _del_mismo_local(self, admin, usuario_id):
        usuario = self.dao.obtener(usuario_id)
        if usuario is None:
            raise NoEncontradoError(f"No existe el usuario {usuario_id}")
        if usuario["sucursal_id"] != admin["sucursal_id"]:
            raise AccesoDenegadoError("Solo podés gestionar las cuentas de tu local")
        if usuario["estado"] != "PENDIENTE":
            raise ReglaNegocioError("Solo se pueden aprobar o rechazar cuentas pendientes")
        return usuario
