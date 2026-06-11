#!/usr/bin/env python3
"""CLI de administración de configuración para R2 Sync."""
import sys
from src.config import load_config, save_config, default_config, config_path


def print_config(config: dict):
    creds = config["credentials"]
    print("\n── Credenciales ──────────────────────────────")
    print(f"  account_id       : {creds.get('account_id', '')}")
    print(f"  access_key_id    : {creds.get('access_key_id', '')}")
    print(f"  secret_access_key: {'*' * 8 if creds.get('secret_access_key') else ''}")
    print("\n── Buckets configurados ──────────────────────")
    for i, b in enumerate(config["buckets"]):
        print(f"  [{i}] {b['name']} -> {b['local_path']}")
    if not config["buckets"]:
        print("  (ninguno)")
    print()


def prompt(label: str, default: str = "") -> str:
    val = input(f"{label} [{default}]: ").strip()
    return val if val else default


def edit_credentials(config: dict):
    c = config["credentials"]
    print("\nDeja en blanco para mantener el valor actual.")
    c["account_id"] = prompt("account_id", c.get("account_id", ""))
    c["access_key_id"] = prompt("access_key_id", c.get("access_key_id", ""))
    secret = input(f"secret_access_key [{'***' if c.get('secret_access_key') else ''}]: ").strip()
    if secret:
        c["secret_access_key"] = secret
    save_config(config)
    print("✓ Credenciales guardadas.")


def add_bucket(config: dict):
    name = prompt("Nombre del bucket R2")
    local = prompt("Ruta local de la carpeta sincronizada")
    if not name or not local:
        print("Operación cancelada.")
        return
    config["buckets"].append({"name": name, "local_path": local})
    save_config(config)
    print(f"✓ Bucket '{name}' agregado.")


def remove_bucket(config: dict):
    if not config["buckets"]:
        print("No hay buckets configurados.")
        return
    print_config(config)
    idx = input("Índice del bucket a eliminar: ").strip()
    try:
        removed = config["buckets"].pop(int(idx))
        save_config(config)
        print(f"✓ Bucket '{removed['name']}' eliminado.")
    except (ValueError, IndexError):
        print("Índice inválido.")


def main():
    if not config_path().exists():
        print("No se encontró configuración. Creando nueva...")
        save_config(default_config())

    while True:
        config = load_config()
        print_config(config)
        print("1) Editar credenciales")
        print("2) Agregar bucket")
        print("3) Eliminar bucket")
        print("4) Salir")
        choice = input("Opción: ").strip()
        if choice == "1":
            edit_credentials(config)
        elif choice == "2":
            add_bucket(config)
        elif choice == "3":
            remove_bucket(config)
        elif choice == "4":
            break
        else:
            print("Opción inválida.")


if __name__ == "__main__":
    main()
