# Copyright 2015: Mirantis Inc.
# All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

from rally import osclients
from rally.plugins.openstack.scenarios.vm import utils as vm_utils
from rally.task import types


class BootOneServerMixin(object):

    # TODO(pboldin): should I move this to vm_scenario?
    def _boot_server_for_user(self, user, image, flavor, prefix, **kwargs):

        clients = osclients.Clients(user["endpoint"])

        image_id = types.ImageResourceType.transform(
            clients=clients, resource_config=image)
        flavor_id = types.FlavorResourceType.transform(
            clients=clients, resource_config=flavor)

        if user.get("keypair"):
            kwargs.setdefault("key_name", user["keypair"]["name"])
        if user.get("secgroup"):
            kwargs.setdefault("security_groups", [user["secgroup"]["name"]])

        vm_scenario_cls = kwargs.pop("vm_scenario_cls", vm_utils.VMScenario)
        # TODO(pboldin): Would it be better to pass vm_scenario to this method?
        vm_scenario = vm_scenario_cls(self.context, clients=clients)

        if kwargs.get("name") is None:
            kwargs["name"] = vm_scenario._generate_random_name(prefix)

        server, fip = vm_scenario._boot_server_with_fip(
            image=image_id, flavor=flavor_id, **kwargs)

        return vm_scenario, server, fip
