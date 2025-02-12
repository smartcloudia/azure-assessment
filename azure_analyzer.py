import os
import json
import logging
from azure.identity import AzureCliCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.containerservice import ContainerServiceClient
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.sql import SqlManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.network import NetworkManagementClient

SUBSCRIPTION_ID = "ID"

def get_resource_group_from_id(resource_id):
    """
    Extrae el nombre del grupo de recursos desde el ID completo del recurso.
    """
    try:
        parts = resource_id.split('/')
        rg_index = parts.index('resourceGroups')
        return parts[rg_index + 1]
    except (ValueError, IndexError):
        return None

def main():
    # Configurar el logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID") or SUBSCRIPTION_ID
    if not subscription_id:
        raise ValueError("Debes establecer la variable de entorno AZURE_SUBSCRIPTION_ID con el ID de la suscripción.")

    credential = AzureCliCredential()

    # Creación de clientes
    resource_client = ResourceManagementClient(credential, subscription_id)
    compute_client = ComputeManagementClient(credential, subscription_id)
    container_client = ContainerServiceClient(credential, subscription_id)
    web_client = WebSiteManagementClient(credential, subscription_id)
    sql_client = SqlManagementClient(credential, subscription_id)
    storage_client = StorageManagementClient(credential, subscription_id)
    network_client = NetworkManagementClient(credential, subscription_id)

    infra_info = {}
    resource_groups = list(resource_client.resource_groups.list())

    for rg in resource_groups:
        rg_name = rg.name
        logging.info(f"Procesando grupo de recursos: {rg_name}")
        infra_info[rg_name] = {
            "virtual_machines": [],
            "aks_clusters": [],
            "web_apps": [],
            "sql_servers": [],
            "storage_accounts": [],
            "other_resources": []
        }

        # --- VIRTUAL MACHINES ---
        try:
            vms = list(compute_client.virtual_machines.list(rg_name))
            for vm in vms:
                logging.info(f"Procesando VM: {vm.name} en el grupo de recursos: {rg_name}")
                try:
                    vm_detail = compute_client.virtual_machines.get(rg_name, vm.name, expand='instanceView')
                    
                    # Información básica de la VM
                    vm_info = {
                        "name": vm_detail.name,
                        "id": vm_detail.id,
                        "location": vm_detail.location,
                        "type": vm_detail.type,
                        "vm_size": vm_detail.hardware_profile.vm_size if vm_detail.hardware_profile else None,
                        "os_type": (vm_detail.storage_profile.os_disk.os_type
                                    if vm_detail.storage_profile and vm_detail.storage_profile.os_disk else None),
                        "os_disk": {
                            "name": vm_detail.storage_profile.os_disk.name if vm_detail.storage_profile and vm_detail.storage_profile.os_disk else None,
                            "size_gb": vm_detail.storage_profile.os_disk.disk_size_gb if vm_detail.storage_profile and vm_detail.storage_profile.os_disk else None
                        },
                        "data_disks": [
                            {
                                "name": d.name,
                                "lun": d.lun,
                                "size_gb": d.disk_size_gb
                            } for d in (vm_detail.storage_profile.data_disks if vm_detail.storage_profile.data_disks else [])
                        ],
                        "statuses": [s.display_status for s in vm_detail.instance_view.statuses] if (vm_detail.instance_view and vm_detail.instance_view.statuses) else [],
                        "tags": vm_detail.tags if vm_detail.tags else {},
                        "availability_set": vm_detail.availability_set.id if vm_detail.availability_set else None,
                        "zones": vm_detail.zones if hasattr(vm_detail, 'zones') and vm_detail.zones else []
                    }

                    # --- Extensiones de la VM ---
                    try:
                        extensions = list(compute_client.virtual_machine_extensions.list(rg_name, vm_detail.name))
                        vm_info["extensions"] = []
                        for ext in extensions:
                            vm_info["extensions"].append({
                                "name": ext.name,
                                "publisher": ext.publisher,
                                "extension_type": ext.type_properties_type,
                                "type_handler_version": ext.type_handler_version,
                                "provisioning_state": ext.provisioning_state
                            })
                    except Exception as ext_e:
                        logging.error(f"Error al procesar extensiones de la VM {vm_detail.name} en el grupo {rg_name}: {ext_e}")
                        vm_info["extensions"] = []

                    # --- Información de red asociada a la VM ---
                    vm_info["network_interfaces"] = []
                    if vm_detail.network_profile and vm_detail.network_profile.network_interfaces:
                        for nic_ref in vm_detail.network_profile.network_interfaces:
                            nic_name = nic_ref.id.split('/')[-1]
                            nic = network_client.network_interfaces.get(rg_name, nic_name)

                            nic_info = {
                                "name": nic.name,
                                "id": nic.id,
                                "mac_address": nic.mac_address,
                                "dns_settings": {
                                    "dns_servers": nic.dns_settings.dns_servers if nic.dns_settings else [],
                                    "internal_dns_name_label": nic.dns_settings.internal_dns_name_label if nic.dns_settings else None
                                },
                                "ip_configurations": [],
                                "nsg": None
                            }

                            # Obtener NSG asociado a la NIC
                            if nic.network_security_group:
                                nsg_id = nic.network_security_group.id
                                nsg_rg = nsg_id.split("/")[4]
                                nsg_name = nsg_id.split("/")[-1]
                                try:
                                    nsg = network_client.network_security_groups.get(nsg_rg, nsg_name)
                                    nsg_info = {
                                        "name": nsg.name,
                                        "id": nsg.id,
                                        "security_rules": []
                                    }
                                    for rule in nsg.security_rules:
                                        nsg_info["security_rules"].append({
                                            "name": rule.name,
                                            "protocol": rule.protocol,
                                            "source_port_range": rule.source_port_range,
                                            "destination_port_range": rule.destination_port_range,
                                            "source_address_prefix": rule.source_address_prefix,
                                            "destination_address_prefix": rule.destination_address_prefix,
                                            "access": rule.access,
                                            "priority": rule.priority,
                                            "direction": rule.direction
                                        })
                                    nic_info["nsg"] = nsg_info
                                except Exception as nsg_e:
                                    logging.error(f"Error al obtener NSG {nsg_name} para NIC {nic.name}: {nsg_e}")

                            # IP Configs (para IP privada, IP pública)
                            for ip_conf in nic.ip_configurations:
                                ip_conf_info = {
                                    "name": ip_conf.name,
                                    "private_ip_address": ip_conf.private_ip_address,
                                    "private_ip_allocation_method": ip_conf.private_ip_allocation_method,
                                }

                                # Si hay IP pública asociada
                                if ip_conf.public_ip_address:
                                    pub_ip_id = ip_conf.public_ip_address.id
                                    pub_ip_name = pub_ip_id.split('/')[-1]
                                    pub_ip_rg = pub_ip_id.split('/')[4]
                                    try:
                                        pub_ip = network_client.public_ip_addresses.get(pub_ip_rg, pub_ip_name)
                                        ip_conf_info["public_ip_address"] = {
                                            "name": pub_ip.name,
                                            "ip_address": pub_ip.ip_address,
                                            "allocation_method": pub_ip.public_ip_allocation_method,
                                            "dns_settings": {
                                                "domain_name_label": pub_ip.dns_settings.domain_name_label if pub_ip.dns_settings else None,
                                                "fqdn": pub_ip.dns_settings.fqdn if pub_ip.dns_settings else None,
                                                "reverse_fqdn": pub_ip.dns_settings.reverse_fqdn if pub_ip.dns_settings else None
                                            }
                                        }
                                    except Exception as pub_ip_e:
                                        logging.error(f"Error al obtener Public IP {pub_ip_name} para NIC {nic.name}: {pub_ip_e}")
                                nic_info["ip_configurations"].append(ip_conf_info)

                            vm_info["network_interfaces"].append(nic_info)

                    # --- Discos administrados (Managed Disks) adicionales ---
                    disk_info_list = []
                    if vm_detail.storage_profile and vm_detail.storage_profile.os_disk and vm_detail.storage_profile.os_disk.managed_disk:
                        os_disk_id = vm_detail.storage_profile.os_disk.managed_disk.id
                        os_disk_name = os_disk_id.split('/')[-1]
                        os_disk_rg = os_disk_id.split('/')[4]
                        try:
                            os_disk_obj = compute_client.disks.get(os_disk_rg, os_disk_name)
                            disk_info_list.append({
                                "role": "os_disk",
                                "name": os_disk_obj.name,
                                "id": os_disk_obj.id,
                                "location": os_disk_obj.location,
                                "disk_size_gb": os_disk_obj.disk_size_gb,
                                "disk_state": os_disk_obj.disk_state,
                                "os_type": os_disk_obj.os_type,
                                "disk_sku": os_disk_obj.sku.name if os_disk_obj.sku else None
                            })
                        except Exception as os_disk_e:
                            logging.error(f"Error al obtener OS Disk {os_disk_name} para VM {vm_detail.name}: {os_disk_e}")

                    if vm_detail.storage_profile and vm_detail.storage_profile.data_disks:
                        for d in vm_detail.storage_profile.data_disks:
                            if d.managed_disk:
                                data_disk_id = d.managed_disk.id
                                data_disk_name = data_disk_id.split('/')[-1]
                                data_disk_rg = data_disk_id.split('/')[4]
                                try:
                                    data_disk_obj = compute_client.disks.get(data_disk_rg, data_disk_name)
                                    disk_info_list.append({
                                        "role": "data_disk",
                                        "name": data_disk_obj.name,
                                        "id": data_disk_obj.id,
                                        "location": data_disk_obj.location,
                                        "disk_size_gb": data_disk_obj.disk_size_gb,
                                        "disk_state": data_disk_obj.disk_state,
                                        "os_type": data_disk_obj.os_type,
                                        "disk_sku": data_disk_obj.sku.name if data_disk_obj.sku else None
                                    })
                                except Exception as data_disk_e:
                                    logging.error(f"Error al obtener Data Disk {data_disk_name} para VM {vm_detail.name}: {data_disk_e}")

                    vm_info["managed_disks_details"] = disk_info_list

                    # Agregar la VM al informe incluso si hubo errores en extensiones
                    infra_info[rg_name]["virtual_machines"].append(vm_info)
                except Exception as vm_e:
                    logging.error(f"Error al obtener detalles de la VM {vm.name} en el grupo {rg_name}: {vm_e}")
                    continue
        except Exception as vms_e:
            logging.error(f"Error al listar VMs en el grupo {rg_name}: {vms_e}")

        # --- AKS CLUSTERS ---
        try:
            aks_clusters = list(container_client.managed_clusters.list_by_resource_group(rg_name))
            for cluster in aks_clusters:
                logging.info(f"Procesando AKS Cluster: {cluster.name} en el grupo de recursos: {rg_name}")
                try:
                    aks_info = {
                        "name": cluster.name,
                        "id": cluster.id,
                        "location": cluster.location,
                        "kubernetes_version": cluster.kubernetes_version,
                        "dns_prefix": cluster.dns_prefix,
                        "node_resource_group": cluster.node_resource_group,
                        "tags": cluster.tags,
                        "agent_pools": []
                    }

                    agent_pools = list(container_client.agent_pools.list(rg_name, cluster.name))
                    for pool in agent_pools:
                        pool_info = {
                            "name": pool.name,
                            "count": pool.count,
                            "vm_size": pool.vm_size,
                            "os_type": pool.os_type,
                            "orchestrator_version": pool.orchestrator_version
                        }
                        aks_info["agent_pools"].append(pool_info)

                    infra_info[rg_name]["aks_clusters"].append(aks_info)
                except Exception as aks_e:
                    logging.error(f"Error al procesar AKS Cluster {cluster.name} en el grupo {rg_name}: {aks_e}")
                    continue
        except Exception as aks_list_e:
            logging.error(f"Error al listar AKS Clusters en el grupo {rg_name}: {aks_list_e}")

        # --- WEB APPS (App Services y Static Sites) ---
        try:
            # Listar todos los recursos en el grupo de recursos
            all_resources = list(resource_client.resources.list_by_resource_group(rg_name))
            logging.info(f"Listando todos los recursos en el grupo de recursos: {rg_name}")

            web_app_types = ['microsoft.web/sites', 'microsoft.web/staticsites']
            web_app_resources = [res for res in all_resources if res.type.lower() in web_app_types]

            logging.info(f"Encontrados {len(web_app_resources)} recursos de tipo Web App o Static Site en el grupo de recursos: {rg_name}")

            for res in web_app_resources:
                logging.debug(f"Procesando recurso Web: {res.name} de tipo: {res.type}")
                try:
                    if res.type.lower() == 'microsoft.web/sites':
                        # Procesar como Web App
                        app = web_client.web_apps.get(rg_name, res.name)
                        last_modified = app.last_modified_time_utc.isoformat() if app.last_modified_time_utc else None

                        app_info = {
                            "name": app.name,
                            "id": app.id,
                            "location": app.location,
                            "kind": app.kind,
                            "state": app.state,
                            "default_host_name": app.default_host_name,
                            "last_modified_time_utc": last_modified
                        }

                        # --- Configuración general ---
                        try:
                            config = web_client.web_apps.get_configuration(rg_name, app.name)
                            app_info.update({
                                "net_framework_version": config.net_framework_version,
                                "php_version": config.php_version,
                                "python_version": config.python_version,
                                "node_version": config.node_version,
                                "linux_fx_version": config.linux_fx_version,
                                "always_on": config.always_on,
                                "auto_heal_enabled": config.auto_heal_enabled,
                                "web_sockets_enabled": config.web_sockets_enabled,
                                "default_documents": config.default_documents,
                                "use_32_bit_worker_process": config.use32_bit_worker_process,
                                "ftps_state": config.ftps_state,
                                "http20_enabled": config.http20_enabled,
                                "min_tls_version": config.min_tls_version,
                                "health_check_path": config.health_check_path
                            })
                        except Exception as config_e:
                            logging.error(f"Error al obtener la configuración de la Web App {app.name}: {config_e}")

                        # --- Configuración de autenticación (Auth Settings) ---
                        try:
                            auth_settings = web_client.web_apps.get_auth_settings(rg_name, app.name)
                            app_info["auth_settings"] = auth_settings.as_dict()
                        except Exception as auth_e:
                            logging.error(f"Error al obtener los auth settings para la Web App {app.name}: {auth_e}")
                            app_info["auth_settings"] = {}

                        # --- Identidad asignada (Managed Identity) ---
                        try:
                            identity = web_client.web_apps.get(rg_name, app.name).identity
                            app_info["identity"] = identity.as_dict() if identity else None
                        except Exception as identity_e:
                            logging.error(f"Error al obtener la identidad de la Web App {app.name}: {identity_e}")
                            app_info["identity"] = None

                        # --- Configuración de diagnósticos y logging ---
                        try:
                            diagnostic_logs = web_client.web_apps.get_diagnostic_logs_configuration(rg_name, app.name)
                            logging.debug(f"Detalles de diagnostic_logs para {app.name}: {diagnostic_logs}")
                            app_info.update({
                                "application_logs": diagnostic_logs.application_logs.as_dict() if diagnostic_logs.application_logs else None,
                                "http_logs": diagnostic_logs.http_logs.as_dict() if diagnostic_logs.http_logs else None,
                                "detailed_error_logging_enabled": getattr(diagnostic_logs, 'detailed_error_logging_enabled', None),  # Usar getattr para evitar errores
                                "failed_request_tracing_enabled": getattr(diagnostic_logs, 'failed_request_tracing_enabled', None)  # Usar getattr para evitar errores
                            })
                        except Exception as diag_e:
                            logging.error(f"Error al obtener la configuración de logging para la Web App {app.name}: {diag_e}")
                            app_info.update({
                                "application_logs": None,
                                "http_logs": None,
                                "detailed_error_logging_enabled": None,
                                "failed_request_tracing_enabled": None
                            })

                        # --- App Settings (Variables de entorno) ---
                        try:
                            app_settings = web_client.web_apps.list_application_settings(rg_name, app.name)
                            app_info["app_settings"] = app_settings.properties if app_settings.properties else {}
                        except Exception as app_settings_e:
                            logging.error(f"Error al obtener los app settings de la Web App {app.name}: {app_settings_e}")
                            app_info["app_settings"] = {}

                        # --- Connection Strings ---
                        try:
                            connection_strings = web_client.web_apps.list_connection_strings(rg_name, app.name)
                            app_info["connection_strings"] = connection_strings.properties if connection_strings.properties else {}
                        except Exception as conn_e:
                            logging.error(f"Error al obtener las connection strings de la Web App {app.name}: {conn_e}")
                            app_info["connection_strings"] = {}

                        # Agregar la información completa de la Web App
                        infra_info[rg_name]["web_apps"].append(app_info)
                        logging.info(f"Información de la Web App {app.name} recopilada y agregada al informe.")

                    elif res.type.lower() == 'microsoft.web/staticsites':
                        # Procesar como Static Site
                        static_sites = web_client.static_sites.list_by_resource_group(rg_name)
                        for static_site in static_sites:
                            if static_site.name.lower() == res.name.lower():
                                last_modified = static_site.last_modified_time.isoformat() if hasattr(static_site, 'last_modified_time') and static_site.last_modified_time else None

                                site_info = {
                                    "name": static_site.name,
                                    "id": static_site.id,
                                    "location": static_site.location,
                                    "kind": static_site.kind,
                                    "state": static_site.state if hasattr(static_site, 'state') else None,
                                    "default_host_name": static_site.default_hostname if hasattr(static_site, 'default_hostname') else None,
                                    "last_modified_time_utc": last_modified,
                                    "sku": static_site.sku.name if hasattr(static_site, 'sku') and static_site.sku else None,
                                    "branch": static_site.branch if hasattr(static_site, 'branch') else None,
                                    "repository_url": static_site.repository_url if hasattr(static_site, 'repository_url') else None,
                                    "build_properties": {
                                        "app_location": static_site.build_properties.app_location if hasattr(static_site, 'build_properties') and static_site.build_properties else None,
                                        "api_location": static_site.build_properties.api_location if hasattr(static_site, 'build_properties') and static_site.build_properties else None,
                                        "output_location": static_site.build_properties.output_location if hasattr(static_site, 'build_properties') and static_site.build_properties else None,
                                    },
                                    "tags": static_site.tags if static_site.tags else {}
                                    # Puedes agregar otros campos según sea necesario
                                }

                                # Agregar la información completa del Static Site a web_apps
                                infra_info[rg_name]["web_apps"].append(site_info)
                                logging.info(f"Información del Static Site {static_site.name} recopilada y agregada al informe.")
                except Exception as app_e:
                    logging.error(f"Error al procesar recurso Web en el grupo {rg_name}: {app_e}")
                    continue

        except Exception as web_list_e:
            logging.error(f"Error al listar recursos Web en el grupo {rg_name}: {web_list_e}")

        # --- SQL SERVERS & DATABASES ---
        try:
            # Obtener todos los SQL Servers listados en la suscripción
            all_sql_servers = list(sql_client.servers.list())
            logging.debug(f"SQL Servers encontrados en la suscripción: {[s.name for s in all_sql_servers]}")

            # Filtrar los SQL Servers que pertenecen al grupo de recursos actual
            rg_sql_servers = [s for s in all_sql_servers if get_resource_group_from_id(s.id).lower() == rg_name.lower()]
            logging.info(f"Encontrados {len(rg_sql_servers)} SQL Servers en el grupo de recursos: {rg_name}")

            for server in rg_sql_servers:
                logging.info(f"Procesando SQL Server: {server.name} en el grupo de recursos: {rg_name}")
                try:
                    server_info = {
                        "name": server.name,
                        "id": server.id,
                        "location": server.location,
                        "version": server.version,
                        "fully_qualified_domain_name": server.fully_qualified_domain_name,
                        "databases": []
                    }

                    databases = list(sql_client.databases.list_by_server(rg_name, server.name))
                    for db in databases:
                        db_info = {
                            "name": db.name,
                            "id": db.id,
                            "status": getattr(db, 'status', None),
                            "edition": getattr(db, 'edition', None),
                            "max_size_bytes": getattr(db, 'max_size_bytes', None),
                            "collation": getattr(db, 'collation', None)
                        }
                        server_info["databases"].append(db_info)

                    infra_info[rg_name]["sql_servers"].append(server_info)
                except Exception as sql_e:
                    logging.error(f"Error al procesar SQL Server {server.name} en el grupo {rg_name}: {sql_e}")
                    continue
        except Exception as sql_list_e:
            logging.error(f"Error al listar SQL Servers en el grupo {rg_name}: {sql_list_e}")

        # --- STORAGE ACCOUNTS ---
        try:
            # Obtener todos los Storage Accounts listados en la suscripción
            all_storage_accounts = list(storage_client.storage_accounts.list())
            rg_storage_accounts = [sa for sa in all_storage_accounts if get_resource_group_from_id(sa.id).lower() == rg_name.lower()]
            logging.info(f"Encontrados {len(rg_storage_accounts)} Storage Accounts en el grupo de recursos: {rg_name}")

            for sa in rg_storage_accounts:
                logging.info(f"Procesando Storage Account: {sa.name} en el grupo de recursos: {rg_name}")
                try:
                    sa_keys = storage_client.storage_accounts.list_keys(rg_name, sa.name)
                    sa_info = {
                        "name": sa.name,
                        "id": sa.id,
                        "location": sa.location,
                        "type": sa.type,
                        "sku": sa.sku.name if sa.sku else None,
                        "kind": sa.kind,
                        "access_tier": sa.access_tier if hasattr(sa, 'access_tier') else None,
                        "keys": [key.value for key in sa_keys.keys] if sa_keys else []
                    }
                    infra_info[rg_name]["storage_accounts"].append(sa_info)
                except Exception as sa_e:
                    logging.error(f"Error al procesar Storage Account {sa.name} en el grupo {rg_name}: {sa_e}")
                    continue
        except Exception as storage_list_e:
            logging.error(f"Error al listar Storage Accounts en el grupo {rg_name}: {storage_list_e}")

        # --- OTHER RESOURCES ---
        try:
            # Obtener todos los recursos específicos para excluirlos de 'other_resources'
            processed_ids = set(
                [vm.id for vm in compute_client.virtual_machines.list(rg_name)] +
                [aks.id for aks in container_client.managed_clusters.list_by_resource_group(rg_name)] +
                [app.id for app in web_client.web_apps.list_by_resource_group(rg_name)] +
                [s.id for s in rg_sql_servers] +
                [sa.id for sa in rg_storage_accounts]
            )
            logging.debug(f"IDs procesados en el grupo {rg_name}: {processed_ids}")

            # Listar todos los recursos en el grupo de recursos
            all_resources = list(resource_client.resources.list_by_resource_group(rg_name))

            for res in all_resources:
                if res.id not in processed_ids:
                    infra_info[rg_name]["other_resources"].append({
                        "name": res.name,
                        "id": res.id,
                        "type": res.type,
                        "location": res.location,
                        "tags": res.tags
                    })
        except Exception as other_e:
            logging.error(f"Error al procesar otros recursos en el grupo {rg_name}: {other_e}")

    # Guardar el resultado en un archivo JSON
    try:
        with open("infra_report.json", "w") as f:
            json.dump(infra_info, f, indent=4)
        print("Informe generado: infra_report.json")
    except Exception as file_e:
        logging.error(f"Error al guardar el informe JSON: {file_e}")

if __name__ == "__main__":
    main()
