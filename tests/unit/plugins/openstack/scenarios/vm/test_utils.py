# Copyright 2013: Mirantis Inc.
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


import subprocess

import mock
import netaddr
from oslo_config import cfg

from rally.plugins.openstack.scenarios.vm import utils
from tests.unit import test

VMTASKS_UTILS = "rally.plugins.openstack.scenarios.vm.utils"
CONF = cfg.CONF


class VMScenarioTestCase(test.ScenarioTestCase):

    @mock.patch("%s.open" % VMTASKS_UTILS,
                side_effect=mock.mock_open(), create=True)
    def test__run_command_over_ssh_script_file(self, mock_open):
        mock_ssh = mock.MagicMock()
        vm_scenario = utils.VMScenario(self.context)
        vm_scenario._run_command_over_ssh(
            mock_ssh,
            {
                "script_file": "foobar",
                "interpreter": ["interpreter", "interpreter_arg"],
                "command_args": ["arg1", "arg2"]
            }
        )
        mock_ssh.execute.assert_called_once_with(
            ["interpreter", "interpreter_arg", "arg1", "arg2"],
            stdin=mock_open.side_effect())
        mock_open.assert_called_once_with("foobar", "rb")

    @mock.patch("%s.six.moves.StringIO" % VMTASKS_UTILS)
    def test__run_command_over_ssh_script_inline(self, mock_string_io):
        mock_ssh = mock.MagicMock()
        vm_scenario = utils.VMScenario(self.context)
        vm_scenario._run_command_over_ssh(
            mock_ssh,
            {
                "script_inline": "foobar",
                "interpreter": ["interpreter", "interpreter_arg"],
                "command_args": ["arg1", "arg2"]
            }
        )
        mock_ssh.execute.assert_called_once_with(
            ["interpreter", "interpreter_arg", "arg1", "arg2"],
            stdin=mock_string_io.return_value)
        mock_string_io.assert_called_once_with("foobar")

    def test__run_command_over_ssh_remote_path(self):
        mock_ssh = mock.MagicMock()
        vm_scenario = utils.VMScenario(self.context)
        vm_scenario._run_command_over_ssh(
            mock_ssh,
            {
                "remote_path": ["foo", "bar"],
                "command_args": ["arg1", "arg2"]
            }
        )
        mock_ssh.execute.assert_called_once_with(
            ["foo", "bar", "arg1", "arg2"],
            stdin=None)

    def test__run_command_over_ssh_remote_path_copy(self):
        mock_ssh = mock.MagicMock()
        vm_scenario = utils.VMScenario(self.context)
        vm_scenario._run_command_over_ssh(
            mock_ssh,
            {
                "remote_path": ["foo", "bar"],
                "local_path": "/bin/false",
                "command_args": ["arg1", "arg2"]
            }
        )
        mock_ssh.put_file.assert_called_once_with(
            "/bin/false", "bar", mode=0o755
        )
        mock_ssh.execute.assert_called_once_with(
            ["foo", "bar", "arg1", "arg2"],
            stdin=None)

    def test__run_command_over_ssh_fails(self):
        vm_scenario = utils.VMScenario(self.context)
        self.assertRaises(ValueError,
                          vm_scenario._run_command_over_ssh,
                          None, command={})

    def test__wait_for_ssh(self):
        ssh = mock.MagicMock()
        vm_scenario = utils.VMScenario(self.context)
        vm_scenario._wait_for_ssh(ssh)
        ssh.wait.assert_called_once_with()

    def test__wait_for_ping(self):
        vm_scenario = utils.VMScenario(self.context)
        vm_scenario._ping_ip_address = mock.Mock(return_value=True)
        vm_scenario._wait_for_ping(netaddr.IPAddress("1.2.3.4"))
        self.mock_wait_for.mock.assert_called_once_with(
            netaddr.IPAddress("1.2.3.4"),
            is_ready=self.mock_resource_is.mock.return_value,
            timeout=CONF.benchmark.vm_ping_timeout,
            check_interval=CONF.benchmark.vm_ping_poll_interval)
        self.mock_resource_is.mock.assert_called_once_with(
            "ICMP UP", vm_scenario._ping_ip_address)

    @mock.patch(VMTASKS_UTILS + ".VMScenario._run_command_over_ssh")
    @mock.patch("rally.common.sshutils.SSH")
    def test__run_command(self, mock_sshutils_ssh,
                          mock_vm_scenario__run_command_over_ssh):
        vm_scenario = utils.VMScenario(self.context)
        vm_scenario.context = {"user": {"keypair": {"private": "ssh"}}}
        vm_scenario._run_command("1.2.3.4", 22, "username", "password",
                                 command={"script_file": "foo",
                                          "interpreter": "bar"})

        mock_sshutils_ssh.assert_called_once_with(
            "username", "1.2.3.4", port=22, pkey="ssh", password="password")
        mock_sshutils_ssh.return_value.wait.assert_called_once_with()
        mock_vm_scenario__run_command_over_ssh.assert_called_once_with(
            mock_sshutils_ssh.return_value,
            {"script_file": "foo", "interpreter": "bar"})

    @mock.patch(VMTASKS_UTILS + ".sys")
    @mock.patch("subprocess.Popen")
    def test__ping_ip_address_linux(self, mock_popen, mock_sys):
        mock_popen.return_value.returncode = 0
        mock_sys.platform = "linux2"

        vm_scenario = utils.VMScenario(self.context)
        host_ip = netaddr.IPAddress("1.2.3.4")
        self.assertTrue(vm_scenario._ping_ip_address(host_ip))

        mock_popen.assert_called_once_with(
            ["ping", "-c1", "-w1", str(host_ip)],
            stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        mock_popen.return_value.wait.assert_called_once_with()

    @mock.patch(VMTASKS_UTILS + ".sys")
    @mock.patch("subprocess.Popen")
    def test__ping_ip_address_linux_ipv6(self, mock_popen, mock_sys):
        mock_popen.return_value.returncode = 0
        mock_sys.platform = "linux2"

        vm_scenario = utils.VMScenario(self.context)
        host_ip = netaddr.IPAddress("1ce:c01d:bee2:15:a5:900d:a5:11fe")
        self.assertTrue(vm_scenario._ping_ip_address(host_ip))

        mock_popen.assert_called_once_with(
            ["ping6", "-c1", "-w1", str(host_ip)],
            stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        mock_popen.return_value.wait.assert_called_once_with()

    @mock.patch(VMTASKS_UTILS + ".sys")
    @mock.patch("subprocess.Popen")
    def test__ping_ip_address_other_os(self, mock_popen, mock_sys):
        mock_popen.return_value.returncode = 0
        mock_sys.platform = "freebsd10"

        vm_scenario = utils.VMScenario(self.context)
        host_ip = netaddr.IPAddress("1.2.3.4")
        self.assertTrue(vm_scenario._ping_ip_address(host_ip))

        mock_popen.assert_called_once_with(
            ["ping", "-c1", str(host_ip)],
            stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        mock_popen.return_value.wait.assert_called_once_with()

    @mock.patch(VMTASKS_UTILS + ".sys")
    @mock.patch("subprocess.Popen")
    def test__ping_ip_address_other_os_ipv6(self, mock_popen, mock_sys):
        mock_popen.return_value.returncode = 0
        mock_sys.platform = "freebsd10"

        vm_scenario = utils.VMScenario(self.context)
        host_ip = netaddr.IPAddress("1ce:c01d:bee2:15:a5:900d:a5:11fe")
        self.assertTrue(vm_scenario._ping_ip_address(host_ip))

        mock_popen.assert_called_once_with(
            ["ping6", "-c1", str(host_ip)],
            stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        mock_popen.return_value.wait.assert_called_once_with()

    def get_scenario(self):
        server = mock.Mock(
            networks={"foo_net": "foo_data"},
            addresses={"foo_net": [{"addr": "foo_ip"}]},
            tenant_id="foo_tenant"
        )
        scenario = utils.VMScenario(self.context)

        scenario._boot_server = mock.Mock(return_value=server)
        scenario._delete_server = mock.Mock()
        scenario._associate_floating_ip = mock.Mock()
        scenario._wait_for_ping = mock.Mock()

        return scenario, server

    def test__boot_server_with_fip_without_networks(self):
        scenario, server = self.get_scenario()
        server.networks = {}
        self.assertRaises(RuntimeError,
                          scenario._boot_server_with_fip,
                          "foo_image", "foo_flavor", foo_arg="foo_value")
        scenario._boot_server.assert_called_once_with(
            "foo_image", "foo_flavor",
            foo_arg="foo_value", auto_assign_nic=True)

    def test__boot_server_with_fixed_ip(self):
        scenario, server = self.get_scenario()
        scenario._attach_floating_ip = mock.Mock()
        server, ip = scenario._boot_server_with_fip(
            "foo_image", "foo_flavor", floating_network="ext_network",
            use_floating_ip=False, foo_arg="foo_value")

        self.assertEqual(ip, {"ip": "foo_ip", "id": None,
                              "is_floating": False})
        scenario._boot_server.assert_called_once_with(
            "foo_image", "foo_flavor",
            auto_assign_nic=True, foo_arg="foo_value")
        self.assertEqual(scenario._attach_floating_ip.mock_calls, [])

    def test__boot_server_with_fip(self):
        scenario, server = self.get_scenario()
        scenario._attach_floating_ip = mock.Mock(
            return_value={"id": "foo_id", "ip": "foo_ip"})
        server, ip = scenario._boot_server_with_fip(
            "foo_image", "foo_flavor", floating_network="ext_network",
            use_floating_ip=True, foo_arg="foo_value")
        self.assertEqual(ip, {"ip": "foo_ip", "id": "foo_id",
                              "is_floating": True})

        scenario._boot_server.assert_called_once_with(
            "foo_image", "foo_flavor",
            auto_assign_nic=True, foo_arg="foo_value")
        scenario._attach_floating_ip.assert_called_once_with(
            server, "ext_network")

    def test__delete_server_with_fixed_ip(self):
        ip = {"ip": "foo_ip", "id": None, "is_floating": False}
        scenario, server = self.get_scenario()
        scenario._delete_floating_ip = mock.Mock()
        scenario._delete_server_with_fip(server, ip, force_delete=True)

        self.assertEqual(scenario._delete_floating_ip.mock_calls, [])
        scenario._delete_server.assert_called_once_with(server, force=True)

    def test__delete_server_with_fip(self):
        fip = {"ip": "foo_ip", "id": "foo_id", "is_floating": True}
        scenario, server = self.get_scenario()
        scenario._delete_floating_ip = mock.Mock()
        scenario._delete_server_with_fip(server, fip, force_delete=True)

        scenario._delete_floating_ip.assert_called_once_with(server, fip)
        scenario._delete_server.assert_called_once_with(server, force=True)

    @mock.patch(VMTASKS_UTILS + ".network_wrapper.wrap")
    def test__attach_floating_ip(self, mock_wrap):
        scenario, server = self.get_scenario()

        netwrap = mock_wrap.return_value
        netwrap.create_floating_ip.return_value = {
            "id": "foo_id", "ip": "foo_ip"}

        scenario._attach_floating_ip(
            server, floating_network="bar_network")

        mock_wrap.assert_called_once_with(scenario.clients,
                                          self.context["task"])
        netwrap.create_floating_ip.assert_called_once_with(
            ext_network="bar_network",
            tenant_id="foo_tenant", fixed_ip="foo_ip")

        scenario._associate_floating_ip.assert_called_once_with(
            server, "foo_ip", fixed_address="foo_ip")

    @mock.patch(VMTASKS_UTILS + ".network_wrapper.wrap")
    def test__delete_floating_ip(self, mock_wrap):
        scenario, server = self.get_scenario()

        _check_addr = mock.Mock(return_value=True)
        scenario.check_ip_address = mock.Mock(return_value=_check_addr)
        scenario._dissociate_floating_ip = mock.Mock()

        scenario._delete_floating_ip(
            server, fip={"id": "foo_id", "ip": "foo_ip"})

        scenario.check_ip_address.assert_called_once_with(
            "foo_ip")
        _check_addr.assert_called_once_with(server)
        scenario._dissociate_floating_ip.assert_called_once_with(
            server, "foo_ip")
        mock_wrap.assert_called_once_with(scenario.clients,
                                          self.context["task"])
        mock_wrap.return_value.delete_floating_ip.assert_called_once_with(
            "foo_id", wait=True)

    @mock.patch(VMTASKS_UTILS + ".subprocess.Popen")
    @mock.patch(VMTASKS_UTILS + ".json")
    def test__process_agent_commands_output(
            self, mock_json, mock_subprocess_popen):
        scenario = utils.VMScenario(self.context)

        mock_subprocess_popen.return_value.communicate.return_value = (
            "stdout", "stderr")

        retval = scenario._process_agent_commands_output(
            "reduction_command", "run_result")

        mock_json.dumps.assert_called_once_with(
            "run_result", default=utils.default_serialize)

        mock_subprocess_popen.assert_called_once_with(
            "reduction_command",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        mock_subprocess_popen.return_value.communicate.assert_called_once_with(
            mock_json.dumps.return_value)

        mock_json.loads.assert_called_once_with("stdout")

        self.assertEqual(
            mock_json.loads.return_value,
            retval)

    def test__agent_run_command(self):
        scenario = utils.VMScenario(self.context)

        scenario._wait_for_agent_ping = mock.Mock()
        scenario._agent_run_command_wait = mock.Mock()

        servers_with_ips = [
            (0, {"ip": "foobar"}, "there"),
            (0, None, "here"),
            (0, None, "onmoon")
        ]
        command_with_args = "all your base belongs to us"

        scenario._agent_run_command(
            command_with_args,
            servers_with_ips,
            expected_runtime=137,
            can_run_off=42)

        scenario._wait_for_agent_ping.assert_called_once_with(
            "http://foobar:8080", 3)

        scenario._agent_run_command_wait.assert_called_once_with(
            "http://foobar:8080", 3,
            {
                "path": [command_with_args],
                "thread": "true",
                "env": [
                    "FIXED_IP0=there",
                    "FIXED_IP1=here",
                    "FIXED_IP2=onmoon",
                    "AGENT_ID=None",
                    "AGENTS_TOTAL=3"
                ]
            },
            137, 42)

    @mock.patch(VMTASKS_UTILS + ".time.sleep")
    @mock.patch(VMTASKS_UTILS + ".requests")
    def test__agent_run_command_wait(self, mock_requests, mock_time_sleep):
        scenario = utils.VMScenario(self.context)

        def J(o):
            return mock.Mock(**{"json.return_value": o})

        mock_requests.post.side_effect = map(
            J,
            [
                [],  # commands
                [  # tail
                    {
                        "agent": "foo",
                        "stdout": "FORGET ABOUT YOUR ",
                        "stderr": "DENIAL, DENIAL ",
                    },
                    {
                        "agent": "bar",
                        "stdout": "AND I'LL ",
                        "stderr": "YOUR EARS ",
                    }
                ],
                [],  # empty tail
                [  # unfinished check
                    {
                        "agent": "foo",
                        "exit_code": None
                    },
                    {
                        "agent": "bar",
                        "exit_code": None
                    }
                ],
                [  # tail
                    {
                        "agent": "foo",
                        "stdout": "HOUSE OF CARDS",
                        "stderr": "DENIAL, DENIAL",
                    },
                    {
                        "agent": "bar",
                        "stdout": "DO MINE",
                        "stderr": "SHOULD BE BURNING",
                    }
                ],
                [],  # empty tail
                [  # finished check
                    {
                        "agent": "foo",
                        "exit_code": 63
                    },
                    {
                        "agent": "bar",
                        "exit_code": None
                    }
                ],
            ]
        )

        retval = scenario._agent_run_command_wait(
            "foobar", 2, "barfoo", 137, 1)

        mock_time_sleep.assert_called_once_with(137)

        self.assertEqual({"foo": 63}, retval["exit_code"])

        def check_content(fh, expected):
            fh.seek(0)
            self.assertEqual(expected.encode("utf-8"), fh.read())

        check_content(
            retval["stdout"]["foo"],
            "FORGET ABOUT YOUR HOUSE OF CARDS")
        check_content(
            retval["stdout"]["bar"],
            "AND I'LL DO MINE")
        check_content(
            retval["stderr"]["foo"],
            "DENIAL, DENIAL DENIAL, DENIAL")
        check_content(
            retval["stderr"]["bar"],
            "YOUR EARS SHOULD BE BURNING")

    @mock.patch(VMTASKS_UTILS + ".requests")
    def test__ping_agent(self, mock_requests):
        scenario = utils.VMScenario(self.context)

        mock_requests.get.return_value.json.return_value = "1234"
        retval = scenario._ping_agent(("foobar", 42))

        mock_requests.get.assert_called_once_with(
            "foobar/ping?agents=42")

        self.assertEqual("UP 4", retval)

    @mock.patch(VMTASKS_UTILS + ".requests")
    def test__ping_agent_down(self, mock_requests):
        scenario = utils.VMScenario(self.context)

        mock_requests.exceptions.RequestException = ValueError
        mock_requests.get.side_effect = ValueError()
        retval = scenario._ping_agent(("foobar", 42))

        self.assertEqual("DOWN", retval)

    def test__wait_for_agent_ping(self):
        scenario = utils.VMScenario(self.context)

        scenario._ping_agent = mock.Mock(return_value=True)

        scenario._wait_for_agent_ping("foobar", 42)

        self.mock_wait_for.mock.assert_called_once_with(
            ("foobar", 42),
            is_ready=self.mock_resource_is.mock.return_value,
            timeout=CONF.benchmark.vm_agent_ping_timeout,
            check_interval=CONF.benchmark.vm_agent_ping_poll_interval
        )
        self.mock_resource_is.mock.assert_called_once_with(
            "UP 42", scenario._ping_agent)


class ModuleTestCase(test.TestCase):
    def test_default_serialize_name(self):
        tf = utils.tempfile.NamedTemporaryFile()
        retval = utils.default_serialize(tf)
        self.assertEqual(tf.name, retval)

    def test_default_serialize(self):
        retval = utils.default_serialize(42)
        self.assertEqual(42, retval)
