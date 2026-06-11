# R2 Sync Service

Sincroniza carpetas locales con buckets de Cloudflare R2.

## Requisitos

- Python 3.11+
- Credenciales R2 con permisos de lectura/escritura/eliminación

## Instalación

```bash
pip install -r requirements.txt
```

## Configuración

```bash
python cli.py
```

El archivo de configuración cifrado se guarda en `~/.r2sync_config.enc`.  
La base de datos de estados se guarda en `~/.r2sync_state.db`.

### Estructura del config (interno, cifrado)

```json
{
  "credentials": {
    "account_id": "tu-account-id",
    "access_key_id": "tu-access-key",
    "secret_access_key": "tu-secret-key"
  },
  "buckets": [
    { "name": "mi-bucket", "local_path": "/ruta/local" }
  ]
}
```

## Instalar como servicio

**Windows** (ejecutar como Administrador):

Requiere [NSSM](https://nssm.cc/download) — descarga `nssm.exe` y colócalo en la raíz del proyecto.

```bash
python install_service.py install
python install_service.py uninstall
```

**Linux** (ejecutar como root):
```bash
sudo python install_service.py install
sudo python install_service.py uninstall
```

## Ejecutar manualmente

```bash
python src/service.py
```

## Comportamiento

| Evento local | Acción en R2 |
|---|---|
| Crear archivo | Upload |
| Modificar archivo | Upload (sobreescribe) |
| Eliminar archivo/carpeta | Delete |
| Mover/Renombrar | Delete origen + Upload destino |

Cada 30 segundos se compara el contenido del bucket con la carpeta local:
- Archivos nuevos en R2 → se descargan localmente
- Archivos eliminados de R2 con estado `SYNCED` → se eliminan localmente
