# Copyright 2014: Mirantis Inc.
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

import mock

from rally import exceptions
from rally.plugins.openstack.context.keystone import roles
from tests.unit import fakes
from tests.unit import test

CTX = "rally.plugins.openstack.context.keystone.roles"

class NamedMock(mock.Mock):
    def __getattr__(self, value):
        if value == "name":
            return getattr(self, "name_")
        return super(mock.Mock, self).__getattr__(value)

class RoleGeneratorTestCase(test.ContextTestCase):

    def setUp(self):
        super(RoleGeneratorTestCase, self).setUp()
        self.client = self.clients("keystone")
        self.client.version = "v2.0"

        self.client.roles.add_user_role = mock.MagicMock()
        self.client.roles.remove_user_role = mock.MagicMock()
        self.client.roles.list.return_value = [
            NamedMock(id="r1", name_="test_role1"),
            NamedMock(id="r2", name_="test_role2"),
        ]

    def get_test_context(self):
        return {
            "config": {
                "roles": [
                    "test_role1",
                    "test_role2"
                ]
            },
            "admin": {"endpoint": mock.MagicMock()},
            "task": mock.MagicMock()
        }

    def test_add_role(self):
        ctx = roles.RoleGenerator(self.context)
        ctx.context["users"] = [{"id": "u1", "tenant_id": "t1"},
                                {"id": "u2", "tenant_id": "t2"}]
        result = ctx._add_role(mock.MagicMock(),
                               self.context["config"]["roles"][0])

        expected = {"id": "r1", "name": "test_role1"}
        self.assertEqual(expected, result)

    def test_add_role_which_does_not_exist(self):
        ctx = roles.RoleGenerator(self.context)
        ctx.context["users"] = [{"id": "u1", "tenant_id": "t1"},
                                {"id": "u2", "tenant_id": "t2"}]
        ex = self.assertRaises(exceptions.NoSuchRole, ctx._add_role,
                               mock.MagicMock(), "unknown_role")

        expected = "There is no role with name `unknown_role`."
        self.assertEqual(expected, str(ex))

    def test_remove_role(self):
        role = mock.MagicMock()

        ctx = roles.RoleGenerator(self.context)
        ctx.context["users"] = [{"id": "u1", "tenant_id": "t1"},
                                {"id": "u2", "tenant_id": "t2"}]
        ctx._remove_role(mock.MagicMock(), role)
        self.assertEqual(
            [
                mock.call("u1", role["id"], tenant="t1"),
                mock.call("u2", role["id"], tenant="t2"),
            ],
            self.client.roles.remove_user_role.mock_calls)

    def test_setup_and_cleanup(self):
        with roles.RoleGenerator(self.context) as ctx:
            ctx.context["users"] = [{"id": "u1", "tenant_id": "t1"},
                                    {"id": "u2", "tenant_id": "t2"}]

            ctx.setup()
            calls = [
                mock.call("u1", "r1", tenant="t1"),
                mock.call("u2", "r1", tenant="t2"),
                mock.call("u1", "r2", tenant="t1"),
                mock.call("u2", "r2", tenant="t2")
            ]
            self.client.roles.add_user_role.assert_has_calls(calls)
            self.assertEqual(
                4, self.client.roles.add_user_role.call_count)
            self.assertEqual(
                0, self.client.roles.remove_user_role.call_count)
            self.assertEqual(2, len(ctx.context["roles"]))
            self.assertEqual(2, len(self.client.roles.list()))

        # Cleanup (called by content manager)
        self.assertEqual(2, len(self.client.roles.list()))
        self.assertEqual(4, self.client.roles.add_user_role.call_count)
        self.assertEqual(4, self.client.roles.remove_user_role.call_count)
        self.assertEqual(
            [
                mock.call("u1", "r1", tenant="t1"),
                mock.call("u2", "r1", tenant="t2"),
                mock.call("u1", "r2", tenant="t1"),
                mock.call("u2", "r2", tenant="t2")
            ],
            self.client.roles.remove_user_role.mock_calls)
