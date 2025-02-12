# Azure Assessment con n8n

## Descripción
Este proyecto realiza un **Azure Assessment** utilizando **n8n** para analizar y evaluar los recursos en una suscripción de Azure. La automatización permite obtener información detallada sobre la infraestructura, incluyendo máquinas virtuales, bases de datos, redes y costos asociados, generando un informe completo basado en los datos obtenidos.

## Características
- **Automatización con n8n**: Un flujo de trabajo en **n8n** analiza la infraestructura de Azure.
- **Extracción de información**: Se obtiene información detallada de los recursos.
- **Generación de reportes**: Se crean informes en formato estructurado.
- **Evaluación de costos**: Se ejecuta un análisis de costos del entorno Azure.

## Requisitos
- Una cuenta de **Azure** con los permisos adecuados para acceder a los recursos.
- **n8n** instalado y configurado.
- **Azure CLI** instalado y autenticado.
- Dependencias de Python necesarias (para `azure_analyzer.py`).

## Instalación
1. Clonar este repositorio:
   ```sh
   git clone REPO_URL
   cd azure-assessment-n8n
   ```
2. Instalar las dependencias de Python:
   ```sh
   pip install -r requirements.txt
   ```
3. Configurar las credenciales de Azure:
   ```sh
   az login
   ```
4. Importar el flujo en n8n (`Azure_Analyzer_V2_N8N.json`).

## Uso
### 1. Ejecutar el análisis de costos
```sh
chmod +x azure_costs.sh
./azure_costs.sh
```
Este script obtendrá los costos de la suscripción de Azure.

### 2. Ejecutar el análisis de infraestructura
```sh
python azure_analyzer.py
```
Generará un archivo JSON con la información de los recursos de Azure.

### 3. Generar el gráfico de dependencias de Azure
```sh
chmod +x azure_graph.sh
./azure_graph.sh
```
Crea una representación visual de la infraestructura de Azure.

## Archivos
| Archivo | Descripción |
|---------|-------------|
| `README.md` | Documentación del proyecto. |
| `Azure_Analyzer_V2_N8N.json` | Flujo de trabajo de **n8n** para el análisis de Azure. |
| `azure_graph.sh` | Script para generar un gráfico de dependencias. |
| `azure_costs.sh` | Script para obtener costos de la suscripción de Azure. |
| `azure_analyzer.py` | Script en Python para analizar los recursos de Azure. |

## Contribuciones
Las contribuciones son bienvenidas. Para contribuir:
1. Haz un **fork** del proyecto.
2. Crea una nueva rama con la mejora: `git checkout -b feature-nueva`.
3. Realiza tus cambios y haz un **commit**: `git commit -m 'Nueva funcionalidad'`.
4. Sube los cambios a tu **fork** y abre un **pull request**.

## Licencia
Este proyecto está bajo la licencia **MIT**.


