# Copyright 2015: Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Tests for the VM workload context utilities."""

import ddt
import mock

from rally.plugins.openstack.context.vm import utils
from tests.unit import test

BASE = "rally.plugins.openstack.context.vm.utils"


@ddt.ddt
class BootOneServerMixinTestCase(test.TestCase):
    @ddt.unpack
    @ddt.data(
        {
            "call_kwargs": {
                "foo_arg": "foo_value"
            },
            "call_expected": {
                "key_name": "keypair_name",
                "security_groups": ["secgroup_name"],
                "foo_arg": "foo_value"
            },
        },
        {
            "call_kwargs": {
                "foo_arg": "foo_value",
                "vm_scenario_cls": True,
            },
            "call_expected": {
                "key_name": "keypair_name",
                "security_groups": ["secgroup_name"],
                "foo_arg": "foo_value"
            },
        }
    )
    @mock.patch("%s.vm_utils.VMScenario" % BASE)
    @mock.patch("%s.osclients.Clients" % BASE)
    @mock.patch("%s.types.ImageResourceType.transform" % BASE,
                return_value="image")
    @mock.patch("%s.types.FlavorResourceType.transform" % BASE,
                return_value="flavor")
    def test__boot_server_for_user(
            self, mock_flavor_resource_type_transform,
            mock_image_resource_type_transform, mock_clients,
            mock_vm_scenario, call_kwargs, call_expected):

        vm_scenario_cls = mock_vm_scenario
        if call_kwargs.pop("vm_scenario_cls", False):
            vm_scenario_cls = mock.Mock()
            call_kwargs["vm_scenario_cls"] = vm_scenario_cls

        vm_scenario_inst = vm_scenario_cls.return_value = mock.MagicMock(
            _boot_server_with_fip=mock.MagicMock(
                return_value=("fake_server", "ip")),
        )

        user = {
            "endpoint": "endpoint",
            "keypair": {"name": "keypair_name"},
            "secgroup": {"name": "secgroup_name"}
        }

        mixin = utils.BootOneServerMixin()
        mixin.context = {}
        mixin.generate_random_name = mock.MagicMock(return_value="foo_name")

        retval = mixin._boot_server_for_user(
            user=user,
            image={"name": "image"},
            flavor={"name": "flavor"},
            **call_kwargs
        )

        self.assertEqual(
            (vm_scenario_inst, "fake_server", "ip"),
            retval)

        mock_flavor_resource_type_transform.assert_called_once_with(
            clients=mock_clients.return_value,
            resource_config={"name": "flavor"})
        mock_image_resource_type_transform.assert_called_once_with(
            clients=mock_clients.return_value,
            resource_config={"name": "image"})
        vm_scenario_cls.assert_called_once_with(
            mixin.context, clients=mock_clients.return_value)

        vm_scenario_inst._boot_server_with_fip.assert_called_once_with(
            image="image", flavor="flavor", name="foo_name",
            **call_expected)
