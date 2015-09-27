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

import mock

from rally.plugins.openstack.context.vm import utils
from tests.unit import test

BASE = "rally.plugins.openstack.context.vm.utils"


class BootOneServerMixinTestCase(test.TestCase):
    @mock.patch("%s.vm_utils.VMScenario" % BASE)
    @mock.patch("%s.osclients.Clients" % BASE)
    @mock.patch("%s.types.ImageResourceType.transform" % BASE,
                return_value="image")
    @mock.patch("%s.types.FlavorResourceType.transform" % BASE,
                return_value="flavor")
    def test__boot_server_for_user(
            self, mock_flavor_resource_type_transform,
            mock_image_resource_type_transform, mock_clients,
            mock_vm_scenario):

        mock_vm_scenario_inst = mock_vm_scenario.return_value = mock.MagicMock(
            _boot_server_with_fip=mock.MagicMock(
                return_value=("fake_server", "ip")),
            _generate_random_name=mock.MagicMock(return_value="foo_name"),
        )

        user = {
            "endpoint": "endpoint",
            "keypair": {"name": "keypair_name"},
            "secgroup": {"name": "secgroup_name"}
        }

        mixin = utils.BootOneServerMixin()
        mixin.context = {}
        retval = mixin._boot_server_for_user(
            user=user,
            image={"name": "image"},
            flavor={"name": "flavor"},
            prefix="prefix_foo",
            foo_arg="foo_value",
        )

        self.assertEqual(
            (mock_vm_scenario_inst, "fake_server", "ip"),
            retval)

        mock_flavor_resource_type_transform.assert_called_once_with(
            clients=mock_clients.return_value,
            resource_config={"name": "flavor"})
        mock_image_resource_type_transform.assert_called_once_with(
            clients=mock_clients.return_value,
            resource_config={"name": "image"})
        mock_vm_scenario.assert_called_once_with(
            mixin.context, clients=mock_clients.return_value)

        mock_vm_scenario_inst._boot_server_with_fip.assert_called_once_with(
            image="image", flavor="flavor",
            name="foo_name", key_name="keypair_name",
            security_groups=["secgroup_name"], foo_arg="foo_value")

    @mock.patch("%s.osclients.Clients" % BASE)
    @mock.patch("%s.types.ImageResourceType.transform" % BASE,
                return_value="image")
    @mock.patch("%s.types.FlavorResourceType.transform" % BASE,
                return_value="flavor")
    def test__boot_server_for_user_kwargs(
            self, mock_flavor_resource_type_transform,
            mock_image_resource_type_transform, mock_clients):

        mock_vm_tasks = mock.Mock()
        mock_vm_tasks_inst = mock_vm_tasks.return_value = mock.MagicMock(
            _boot_server_with_fip=mock.MagicMock(
                return_value=("fake_server", "ip")),
            _generate_random_name=mock.MagicMock(return_value="foo_name"),
        )

        user = {
            "endpoint": "endpoint",
            "keypair": {"name": "keypair_name"},
            "secgroup": {"name": "secgroup_name"}
        }

        mixin = utils.BootOneServerMixin()
        mixin.context = {}
        retval = mixin._boot_server_for_user(
            user=user,
            image={"name": "image"},
            flavor={"name": "flavor"},
            prefix="prefix_foo",
            vm_scenario_cls=mock_vm_tasks,
            key_name="foo_key",
            security_groups=["foo_groups"],
            foo_arg="foo_value",
        )

        self.assertEqual(
            (mock_vm_tasks_inst, "fake_server", "ip"),
            retval)

        mock_flavor_resource_type_transform.assert_called_once_with(
            clients=mock_clients.return_value,
            resource_config={"name": "flavor"})
        mock_image_resource_type_transform.assert_called_once_with(
            clients=mock_clients.return_value,
            resource_config={"name": "image"})
        mock_vm_tasks.assert_called_once_with(
            mixin.context, clients=mock_clients.return_value)

        mock_vm_tasks_inst._boot_server_with_fip.assert_called_once_with(
            image="image", flavor="flavor",
            name="foo_name", key_name="foo_key",
            security_groups=["foo_groups"], foo_arg="foo_value")
