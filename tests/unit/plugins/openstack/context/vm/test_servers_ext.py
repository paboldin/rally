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


import ddt
import mock

from rally.plugins.openstack.context.vm import servers_ext
from tests.unit import test


@ddt.ddt
class ServerGeneratorExtTestCase(test.ContextTestCase):

    def test__get_servers_per_tenant(self):
        context = {
            "task": mock.Mock(),
            "config": {
                "servers_ext": {
                    "servers_per_tenant": 42
                }
            }
        }
        server_generator = servers_ext.ServerGeneratorExt(context)
        retval = server_generator._get_servers_per_tenant()

        self.assertEqual(42, retval)

    def test__get_servers_per_tenant_hypervisors(self):
        context = {
            "task": mock.Mock(),
            "admin": {
                "endpoint": "admin_endpoint"
            },
            "config": {
                "servers_ext": {
                    "servers_per_tenant": "hypervisors"
                }
            }
        }

        mock_list = self.admin_clients("nova").hypervisors.list
        mock_list.return_value.__len__.return_value = 42

        server_generator = servers_ext.ServerGeneratorExt(context)
        retval = server_generator._get_servers_per_tenant()

        self.assertEqual(42, retval)
        mock_list.return_value.__len__.assert_called_once_with()

    def test__get_servers_per_tenant_incorrect(self):
        context = {
            "task": mock.Mock(),
            "config": {
                "servers_ext": {
                    "servers_per_tenant": "foobar"
                }
            }
        }
        server_generator = servers_ext.ServerGeneratorExt(context)

        self.assertRaises(ValueError, server_generator._get_servers_per_tenant)

    def test__get_server_group_none(self):
        context = {
            "task": mock.Mock(),
            "config": {
                "servers_ext": {
                    "placement_policy": None,
                }
            }
        }

        server_generator = servers_ext.ServerGeneratorExt(context)
        retval = server_generator._get_server_group(None)

        self.assertIsNone(retval)

    @mock.patch("rally.common.utils.generate_random_name")
    def test__get_server_group(self, mock_generate_random_name):
        context = {
            "task": mock.Mock(),
            "config": {
                "servers_ext": {
                    "placement_policy": "foobar",
                }
            }
        }
        mock_clients = mock.Mock(
            **{
                "nova.return_value.server_groups.create.return_value.id": "42"
            })
        mock_generate_random_name.return_value = "fooname"

        server_generator = servers_ext.ServerGeneratorExt(context)
        retval = server_generator._get_server_group(mock_clients)

        mock_generate_random_name.assert_called_once_with(
            prefix="rally_server_group_")

        mock_create = mock_clients.nova.return_value.server_groups.create
        mock_create.assert_called_once_with(
            name="fooname", policies=["foobar"])
        self.assertEqual("42", retval)

    def _get_context(self, servers_with_ips, config_override={}):
        context = {
            "task": mock.Mock(),
            "config": {
                "servers_ext": {
                    "placement_policy": "foobar",
                    "floating_ips": "once",
                    "image": "image",
                    "flavor": "flavor",
                    "floating_network": "floating_network",
                    "internal_network": "internal_network",
                    "userdata": "{servers_with_ips[0][1]}.{server_num}.foo"
                }
            }
        }
        if config_override:
            context["config"]["servers_ext"].update(config_override)

        server_generator = servers_ext.ServerGeneratorExt(context)
        server_generator._get_server_group = mock.Mock(
            return_value="server_group")
        server_generator._get_servers_per_tenant = mock.Mock(
            return_value=len(servers_with_ips))

        server_generator._boot_one_server_with_ips = mock.Mock(
            side_effect=servers_with_ips
        )

        return server_generator

    def test__boot_tenant_servers(self):
        user = {
            "endpoint": "user_endpoint"
        }
        tenant = {}

        servers_with_ips = [("foo", 10), ("bar", 20)]

        server_generator = self._get_context(servers_with_ips)

        server_generator._boot_tenant_servers(user, tenant)

        self.assertEqual(
            {
                "group": "server_group",
                "servers_with_ips": servers_with_ips
            },
            tenant)

        common_kwargs = dict(
            flavor="flavor", image="image",
            floating_network="floating_network",
            internal_network="internal_network",
            scheduler_hints={
                "group": "server_group"
            },
            user=user
        )

        self.assertEqual(
            [
                mock.call(
                    use_floating_ip=True,
                    userdata=None,
                    **common_kwargs
                ),
                mock.call(
                    use_floating_ip=False,
                    userdata="10.1.foo",
                    **common_kwargs
                ),
            ],
            server_generator._boot_one_server_with_ips.mock_calls)

    def test__boot_tenant_servers_floating_ips_none(self):
        user = {
            "endpoint": "user_endpoint"
        }
        tenant = {}

        servers_with_ips = [("foo", 10), ("bar", 20)]

        server_generator = self._get_context(
            servers_with_ips, {"floating_ips": "none"})
        server_generator._get_server_group.return_value = None

        server_generator._boot_tenant_servers(user, tenant)

        self.assertEqual(
            {
                "servers_with_ips": servers_with_ips
            },
            tenant)

        common_kwargs = dict(
            flavor="flavor", image="image",
            floating_network="floating_network",
            internal_network="internal_network",
            user=user
        )

        self.assertEqual(
            [
                mock.call(
                    use_floating_ip=False,
                    userdata=None,
                    **common_kwargs
                ),
                mock.call(
                    use_floating_ip=False,
                    userdata="10.1.foo",
                    **common_kwargs
                ),
            ],
            server_generator._boot_one_server_with_ips.mock_calls)

    def test__boot_tenant_servers_floating_ips_each(self):
        user = {
            "endpoint": "user_endpoint"
        }
        tenant = {}

        servers_with_ips = [("foo", 10), ("bar", 20), ("buzz", 42)]

        server_generator = self._get_context(
            servers_with_ips, {"floating_ips": "each"})
        server_generator._get_server_group.return_value = None

        server_generator._boot_tenant_servers(user, tenant)

        self.assertEqual(
            {
                "servers_with_ips": servers_with_ips
            },
            tenant)

        common_kwargs = dict(
            flavor="flavor", image="image",
            floating_network="floating_network",
            internal_network="internal_network",
            user=user
        )

        self.assertEqual(
            [
                mock.call(
                    use_floating_ip=True,
                    userdata=None,
                    **common_kwargs
                ),
                mock.call(
                    use_floating_ip=True,
                    userdata="10.1.foo",
                    **common_kwargs
                ),
                mock.call(
                    use_floating_ip=True,
                    userdata="10.2.foo",
                    **common_kwargs
                ),
            ],
            server_generator._boot_one_server_with_ips.mock_calls)

    @ddt.unpack
    @ddt.data(
        (
            [
                [{
                    "OS-EXT-IPS:type": "floating",
                }],
                [{
                    "OS-EXT-IPS:type": "fixed",
                    "addr": "foo_addr"
                }],
            ],
            {"is_floating": True},
            ({"is_floating": True}, "foo_addr")
        ),
        (
            [],
            {"is_floating": False, "ip": "bar_addr"},
            (None, "bar_addr")
        )
    )
    def test__boot_one_server_with_ips(self, addresses, fip, expected):
        context = {
            "task": mock.Mock(),
        }

        server_generator = servers_ext.ServerGeneratorExt(context)
        mock_server = mock.Mock(
            **{
                "addresses.values.return_value": addresses,
                "id": "foo_server"
            })

        server_generator._boot_server_for_user = mock.Mock(
            return_value=(mock.Mock(), mock_server, fip)
        )

        retval = server_generator._boot_one_server_with_ips(
            foo_arg="foo_value")

        server_generator._boot_server_for_user.assert_called_once_with(
            foo_arg="foo_value"
        )

        self.assertEqual("foo_server", retval[0])
        self.assertEqual(expected, retval[1:])

    def test_setup(self):
        context = {
            "task": mock.MagicMock(uuid="foo"),
            "users": [
                {"tenant_id": "tenant_id0"},
                {"tenant_id": "tenant_id1"},
                {"tenant_id": "tenant_id2"}
            ],
            "tenants": {
                "tenant_id0": {"foo": 0},
                "tenant_id1": {"foo": 1},
                "tenant_id2": {"foo": 2}
            }
        }

        server_generator = servers_ext.ServerGeneratorExt(context)
        server_generator._boot_tenant_servers = mock.Mock()
        server_generator.setup()

        self.assertEqual(
            [
                mock.call({"tenant_id": "tenant_id0"}, {"foo": 0}),
                mock.call({"tenant_id": "tenant_id1"}, {"foo": 1}),
                mock.call({"tenant_id": "tenant_id2"}, {"foo": 2}),
            ],
            server_generator._boot_tenant_servers.mock_calls)

    def test__cleanup_one_tenant(self):
        user = {
            "endpoint": "user_endpoint"
        }
        tenant = {
            "group": "foobar",
            "servers_with_ips": [
                ("server_id_1", "fip", "fixed_ip_1"),
                ("server_id_2", None, "fixed_ip_2")
            ]
        }

        mock_servers_get = self.clients("nova").servers.get
        mock_servers_get.side_effect = ["server_1", "server_2"]

        server_generator = servers_ext.ServerGeneratorExt(
            {"task": mock.Mock()})
        server_generator._delete_server = mock.Mock()
        server_generator._delete_server_with_fip = mock.Mock()

        server_generator._cleanup_one_tenant(user, tenant)

        server_generator._delete_server_with_fip.assert_called_once_with(
            "server_1", "fip")
        server_generator._delete_server.assert_called_once_with("server_2")

        self.assertEqual(
            [
                mock.call("server_id_1"),
                mock.call("server_id_2"),
            ],
            mock_servers_get.mock_calls)

        self.clients("nova").server_groups.delete.assert_called_once_with(
            "foobar")

    def test_cleanup(self):
        context = {
            "task": mock.MagicMock(uuid="foo"),
            "users": [
                {"tenant_id": "tenant_id0"},
                {"tenant_id": "tenant_id1"},
                {"tenant_id": "tenant_id2"}
            ],
            "tenants": {
                "tenant_id0": {"foo": 0},
                "tenant_id1": {"foo": 1},
                "tenant_id2": {"foo": 2}
            }
        }

        server_generator = servers_ext.ServerGeneratorExt(context)
        server_generator._cleanup_one_tenant = mock.Mock()

        server_generator.cleanup()

        self.assertEqual(
            [
                mock.call({"tenant_id": "tenant_id0"}, {"foo": 0}),
                mock.call({"tenant_id": "tenant_id1"}, {"foo": 1}),
                mock.call({"tenant_id": "tenant_id2"}, {"foo": 2}),
            ],
            server_generator._cleanup_one_tenant.mock_calls)
