"""Deja la base con los datos de demostración del equipo (todos ven lo mismo).
Cerrá el backend antes de correrlo:   python restaurar_demo.py"""
from database.base_demo import restaurar_demo

if __name__ == "__main__":
    restaurar_demo()
