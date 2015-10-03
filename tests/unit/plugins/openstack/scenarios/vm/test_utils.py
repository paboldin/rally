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
            server, "foo_ip", fixed_address="foo_ip", atomic_action=False)

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
            server, "foo_ip", atomic_action=False)
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

        mock_stdout = test.NamedMock(name_="stdout")
        mock_stderr = test.NamedMock(name_="stderr")
        run_result = {
            "stdout": {"0": mock_stdout},
            "stderr": {"0": mock_stderr}
        }

        retval = scenario._process_agent_commands_output(
            "reduction_command", run_result)

        mock_stdout.flush.assert_called_once_with()
        mock_stderr.flush.assert_called_once_with()

        mock_json.dumps.assert_called_once_with(
            {
                "stdout": {"0": "stdout"},
                "stderr": {"0": "stderr"},
            })

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

    @mock.patch(VMTASKS_UTILS + ".agent_api.SwarmConnection")
    def test__run_command_swarm(self, mock_agent_api_swarm_connection):
        scenario = utils.VMScenario(self.context)

        scenario._wait_for_swarm_ping = mock.Mock()

        servers_with_ips = [
            (0, {"ip": "foobar"}, "there"),
            (0, {"ip": "barfoo"}, "here"),
            (0, None, "onmoon")
        ]
        command_with_args = "all your base belongs to us"

        scenario._run_command_swarm(
            command_with_args,
            servers_with_ips,
            expected_runtime=137,
            can_run_off=42)

        mock_agent_api_swarm_connection.assert_called_once_with(
            "http://foobar:8080", 3)
        swarm_connection = mock_agent_api_swarm_connection.return_value

        scenario._wait_for_swarm_ping.assert_called_once_with(swarm_connection)

        swarm_connection.run_command_thread.assert_called_once_with(
            [command_with_args],
            env=[
                "AGENT_ID=None",
                "AGENTS_TOTAL=3",
                "FLOATING_IP0=foobar",
                "FIXED_IP0=there",
                "FLOATING_IP1=barfoo",
                "FIXED_IP1=here",
                "FIXED_IP2=onmoon",
            ]
        )

        swarm_connection.wait.assert_called_once_with(42)

    def test__wait_for_swarm_ping(self):
        scenario = utils.VMScenario(self.context)

        swarm_connection = mock.Mock()

        scenario._wait_for_swarm_ping(swarm_connection)

        self.mock_wait_for.mock.assert_called_once_with(
            None,
            is_ready=self.mock_resource_is.mock.return_value,
            timeout=CONF.benchmark.vm_swarm_ping_timeout,
            check_interval=CONF.benchmark.vm_swarm_ping_poll_interval
        )
        self.mock_resource_is.mock.assert_called_once_with(
            "UP ALL", swarm_connection.status)
