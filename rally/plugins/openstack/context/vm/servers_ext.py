# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from rally.common.i18n import _
from rally.common import log as logging
from rally.common import utils as rutils
from rally import consts
from rally import osclients
from rally.plugins.openstack.context.vm import utils as context_vm_utils
from rally.plugins.openstack.scenarios.vm import utils as vm_utils
from rally.task import context


LOG = logging.getLogger(__name__)


@context.configure(name="servers_ext", order=530)
class ServerGeneratorExt(context.Context,
                         context_vm_utils.BootOneServerMixin):
    """Context class for adding temporary servers for benchmarks.

        Servers are added for each tenant.
    """

    CONFIG_SCHEMA = {
        "type": "object",
        "$schema": consts.JSON_SCHEMA,
        "properties": {
            "image": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string"
                    }
                }
            },
            "flavor": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string"
                    }
                }
            },
            "floating_network": {
                "type": "string"
            },
            "internal_network": {
                "type": "string"
            },
            "port": {
                "type": "integer",
                "minimum": 1,
                "maximum": 65535
            },
            "userdata": {
                "type": "string"
            },
            "servers_per_tenant": {
                "oneOf": [
                    {
                        "type": "integer",
                        "minimum": 1
                    },
                    {
                        "type": "string",
                        "enum": ["hypervisors"]
                    }
                ]
            },
            "floating_ips": {
                "type": "string",
                "enum": ["each", "once", "none"]
            },
            "placement_policy": {
                "type": "string",
                "enum": ["affinity", "anti-affinity"]
            },
        },
        "required": ["image", "flavor"],
        "additionalProperties": False
    }

    DEFAULT_CONFIG = {
        "servers_per_tenant": 5
    }

    def _get_servers_per_tenant(self):
        servers_per_tenant = self.config["servers_per_tenant"]
        if isinstance(servers_per_tenant, int):
            return servers_per_tenant

        if servers_per_tenant == "hypervisors":
            admin_clients = osclients.Clients(
                self.context["admin"]["endpoint"])
            return len(admin_clients.nova().hypervisors.list())

        raise ValueError("servers_per_tenant has incorrect value")

    def _get_server_group(self, clients):
        if self.config.get("placement_policy", None) is None:
            return

        name = vm_utils.VMScenario()._generate_random_name(
            prefix="rally_server_group_")
        return clients.nova().server_groups.create(
            name=name,
            policies=[self.config["placement_policy"]]
        ).id

    def _boot_tenant_servers(self, user, tenant):
        server_group = self._get_server_group(
            osclients.Clients(user["endpoint"]))

        kwargs = {}
        if server_group is not None:
            tenant["group"] = server_group
            kwargs["scheduler_hints"] = {"group": server_group}

        servers_per_tenant = self._get_servers_per_tenant()
        userdata_template = self.config.get("userdata", None)

        use_floating_ip = self.config.get("floating_ips") != "none"

        tenant["servers_with_ips"] = servers_with_ips = []
        for i in range(servers_per_tenant):
            try:
                if userdata_template is not None:
                    userdata = userdata_template.format(
                        servers_with_ips=servers_with_ips,
                        server_num=i, **self.config
                    )
            except (IndexError, KeyError) as e:
                LOG.debug(
                    "Tried to make an userdata from template got exception %s"
                    % e)
                userdata = None

            server_with_ips = self.boot_one_server_with_ips(
                user=user,
                image=self.config["image"],
                flavor=self.config["flavor"],
                use_floating_ip=use_floating_ip,
                userdata=userdata,
                floating_network=self.config.get("floating_network"),
                internal_network=self.config.get("internal_network"),
                **kwargs)

            servers_with_ips.append(server_with_ips)

            if self.config.get("floating_ips") == "once":
                use_floating_ip = False

    @rutils.log_task_wrapper(LOG.info, _("Enter context: `ServersExt`"))
    def setup(self):

        for user, tenant_id in rutils.iterate_per_tenants(
                self.context["users"]):
            self._boot_tenant_servers(user, self.context["tenants"][tenant_id])

    def boot_one_server_with_ips(self, **kwargs):
        vm_scenario, server, fip = self._boot_server_for_user(
            prefix="rally_ctx_servers_ext_", **kwargs)

        if fip["is_floating"]:
            fixed_ip = None
            for addresses in server.addresses.values():
                for address in addresses:
                    if address["OS-EXT-IPS:type"] == "fixed":
                        fixed_ip = address["addr"]
                        break
                else:
                    continue
                break
        else:
            fixed_ip = fip["ip"]
            fip = None

        return server.id, fip, fixed_ip

    @rutils.log_task_wrapper(LOG.info, _("Exit context: `ServersExt`"))
    def cleanup(self):
        for user, tenant_id in rutils.iterate_per_tenants(
                self.context["users"]):

            self._cleanup_one_tenant(user, self.context["tenants"][tenant_id])

    def _cleanup_one_tenant(self, user, tenant):
        clients = osclients.Clients(user["endpoint"])

        for server_id, fip, fixed_ip in tenant["servers_with_ips"]:
            server_id = clients.nova().servers.get(server_id)
            if fip:
                self._delete_server_with_fip(server_id, fip)
            else:
                self._delete_server(server_id)
        if "group" in tenant:
            clients.nova().server_groups.delete(tenant["group"])
