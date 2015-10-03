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

import collections
import json
import subprocess
import sys
import tempfile
import time

import netaddr
from oslo_config import cfg
import requests
import six

from rally.common.i18n import _
from rally.common import log as logging
from rally.common import sshutils
from rally.plugins.openstack.scenarios.cinder import utils as cinder_utils
from rally.plugins.openstack.scenarios.nova import utils as nova_utils
from rally.plugins.openstack.wrappers import network as network_wrapper
from rally.task import atomic
from rally.task import utils
from rally.task import validation

LOG = logging.getLogger(__name__)

ICMP_UP_STATUS = "ICMP UP"
ICMP_DOWN_STATUS = "ICMP DOWN"

VM_BENCHMARK_OPTS = [
    cfg.FloatOpt("vm_ping_poll_interval", default=1.0,
                 help="Interval between checks when waiting for a VM to "
                 "become pingable"),
    cfg.FloatOpt("vm_ping_timeout", default=120.0,
                 help="Time to wait for a VM to become pingable"),
    cfg.FloatOpt("vm_agent_ping_poll_interval", default=5.0,
                 help="Interval between checks when waiting for a VM agents "
                 "to become pingable"),
    cfg.FloatOpt("vm_agent_ping_timeout", default=600.0,
                 help="Time to wait for a VM agents to become pingable")]

CONF = cfg.CONF
benchmark_group = cfg.OptGroup(name="benchmark", title="benchmark options")
CONF.register_opts(VM_BENCHMARK_OPTS, group=benchmark_group)


def default_serialize(obj):
    try:
        obj.flush()
        return obj.name
    except AttributeError:
        return obj


class VMScenario(nova_utils.NovaScenario, cinder_utils.CinderScenario):
    """Base class for VM scenarios with basic atomic actions.

    VM scenarios are scenarios executed inside some launched VM instance.
    """

    USER_RWX_OTHERS_RX_ACCESS_MODE = 0o755

    RESOURCE_NAME_PREFIX = "rally_vm_"

    @atomic.action_timer("vm.run_command_over_ssh")
    def _run_command_over_ssh(self, ssh, command):
        """Run command inside an instance.

        This is a separate function so that only script execution is timed.

        :param ssh: A SSHClient instance.
        :param command: Dictionary specifying command to execute.
            See `rally info find VMTasks.boot_runcommand_delete' parameter
            `command' docstring for explanation.

        :returns: tuple (exit_status, stdout, stderr)
        """
        validation.check_command_dict(command)

        # NOTE(pboldin): Here we `get' the values and not check for the keys
        # due to template-driven configuration generation that can leave keys
        # defined but values empty.
        if command.get("script_file") or command.get("script_inline"):
            cmd = command["interpreter"]
            if command.get("script_file"):
                stdin = open(command["script_file"], "rb")
            elif command.get("script_inline"):
                stdin = six.moves.StringIO(command["script_inline"])
        elif command.get("remote_path"):
            cmd = command["remote_path"]
            stdin = None

        if command.get("local_path"):
            remote_path = cmd[-1] if isinstance(cmd, (tuple, list)) else cmd
            ssh.put_file(command["local_path"], remote_path,
                         mode=self.USER_RWX_OTHERS_RX_ACCESS_MODE)

        if command.get("command_args"):
            if not isinstance(cmd, (list, tuple)):
                cmd = [cmd]
            # NOTE(pboldin): `ssh.execute' accepts either a string interpreted
            # as a command name or the list of strings that are converted into
            # single-line command with arguments.
            cmd = cmd + list(command["command_args"])

        return ssh.execute(cmd, stdin=stdin)

    def _boot_server_with_fip(self, image, flavor, use_floating_ip=True,
                              floating_network=None, **kwargs):
        """Boot server prepared for SSH actions."""
        kwargs["auto_assign_nic"] = True
        server = self._boot_server(image, flavor, **kwargs)

        if not server.networks:
            raise RuntimeError(
                "Server `%s' is not connected to any network. "
                "Use network context for auto-assigning networks "
                "or provide `nics' argument with specific net-id." %
                server.name)

        if use_floating_ip:
            fip = self._attach_floating_ip(server, floating_network)
        else:
            internal_network = list(server.networks)[0]
            fip = {"ip": server.addresses[internal_network][0]["addr"]}

        return server, {"ip": fip.get("ip"),
                        "id": fip.get("id"),
                        "is_floating": use_floating_ip}

    @atomic.action_timer("vm.attach_floating_ip")
    def _attach_floating_ip(self, server, floating_network):
        internal_network = list(server.networks)[0]
        fixed_ip = server.addresses[internal_network][0]["addr"]

        fip = network_wrapper.wrap(self.clients,
                                   self.context["task"]).create_floating_ip(
            ext_network=floating_network,
            tenant_id=server.tenant_id, fixed_ip=fixed_ip)

        self._associate_floating_ip(server, fip["ip"], fixed_address=fixed_ip)

        return fip

    @atomic.action_timer("vm.delete_floating_ip")
    def _delete_floating_ip(self, server, fip):
        with logging.ExceptionLogger(
                LOG, _("Unable to delete IP: %s") % fip["ip"]):
            if self.check_ip_address(fip["ip"])(server):
                self._dissociate_floating_ip(server, fip["ip"])
                network_wrapper.wrap(
                    self.clients, self.context["task"]).delete_floating_ip(
                        fip["id"],
                        wait=True)

    def _delete_server_with_fip(self, server, fip, force_delete=False):
        if fip["is_floating"]:
            self._delete_floating_ip(server, fip)
        return self._delete_server(server, force=force_delete)

    @atomic.action_timer("vm.wait_for_ssh")
    def _wait_for_ssh(self, ssh):
        ssh.wait()

    @atomic.action_timer("vm.wait_for_ping")
    def _wait_for_ping(self, server_ip):
        server_ip = netaddr.IPAddress(server_ip)
        utils.wait_for(
            server_ip,
            is_ready=utils.resource_is(ICMP_UP_STATUS, self._ping_ip_address),
            timeout=CONF.benchmark.vm_ping_timeout,
            check_interval=CONF.benchmark.vm_ping_poll_interval
        )

    @staticmethod
    def _ping_agent(args):
        http_url, agents = args
        try:
            pings = requests.get(http_url + "/ping?agents=%d" % agents).json()
        except requests.exceptions.RequestException:
            LOG.debug("MasterAgent %s is down." % http_url)
            return "DOWN"
        LOG.debug("%d agents is up through %s." % (len(pings), http_url))
        return "UP %d" % len(pings)

    @atomic.action_timer("vm.wait_for_agent_ping")
    def _wait_for_agent_ping(self, http_url, expected_agents):
        utils.wait_for(
            (http_url, expected_agents),
            is_ready=utils.resource_is("UP %d" % expected_agents,
                                       self._ping_agent),
            timeout=CONF.benchmark.vm_agent_ping_timeout,
            check_interval=CONF.benchmark.vm_agent_ping_poll_interval
        )

    def _agent_run_command_wait(self, http_url, agents, command,
                                expected_runtime, can_run_off):
        LOG.debug("Running command %r on %d agent(s) via %s" % (
            command, agents, http_url))

        commands = requests.post(
            http_url + "/command?agents=%d" % agents,
            data=command,
        ).json()

        LOG.debug("Commands %r started on %s" % (commands, http_url))

        if expected_runtime is not None:
            time.sleep(expected_runtime)

        run = {
            "stdout": collections.defaultdict(tempfile.NamedTemporaryFile),
            "stderr": collections.defaultdict(tempfile.NamedTemporaryFile),
            "exit_code": {}
        }

        while True:
            tails = requests.post(http_url + "/tail?agents=%d" % agents).json()

            LOG.debug("Tailed %r" % tails)

            updated = False
            for tail in tails:
                agent = tail["agent"]
                for fd in "stdout", "stderr":
                    if tail[fd]:
                        run[fd][agent].write(tail[fd].encode("utf-8"))
                        updated = True

            if not updated:
                checks = requests.post(
                    http_url + "/check?agents=%d" % agents
                ).json()

                LOG.debug("Checking %r" % checks)

                finished = 0
                for check in checks:
                    if check["exit_code"] is not None:
                        finished += 1
                        run["exit_code"][check["agent"]] = check["exit_code"]
                if finished >= agents - can_run_off:
                    break

        return run

    def _agent_run_command(self, command_with_args, servers_with_ips,
                           expected_runtime=None, can_run_off=0):
        fip = servers_with_ips[0][1]
        http_url = "http://%s:8080" % fip["ip"]

        agents = len(servers_with_ips)

        self._wait_for_agent_ping(http_url, agents)

        # TODO(pboldin): Should do better job moving requests out of this

        env = ["FIXED_IP%d=%s" % (i, d[2])
               for i, d in enumerate(servers_with_ips)]
        env.append("AGENT_ID=None")
        env.append("AGENTS_TOTAL=%d" % agents)

        if not isinstance(command_with_args, list):
            command_with_args = [command_with_args]

        command = {
            "path": command_with_args,
            "thread": "true",
            "env": env
        }

        return self._agent_run_command_wait(
            http_url, agents, command, expected_runtime, can_run_off)

    def _process_agent_commands_output(self, reduction_command, run_result):
        stdin = json.dumps(run_result, default=default_serialize)
        LOG.debug("Dumping %s into stdin." % stdin)

        process = subprocess.Popen(
            reduction_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        stdout, stderr = process.communicate(stdin)
        LOG.debug("Got STDOUT:\n\n%s\n\nGot STDERR\n\n%s\n\n" %
                  (stdout, stderr))

        return json.loads(stdout)

    def _run_command(self, server_ip, port, username, password, command,
                     pkey=None):
        """Run command via SSH on server.

        Create SSH connection for server, wait for server to become available
        (there is a delay between server being set to ACTIVE and sshd being
        available). Then call run_command_over_ssh to actually execute the
        command.

        :param server_ip: server ip address
        :param port: ssh port for SSH connection
        :param username: str. ssh username for server
        :param password: Password for SSH authentication
        :param command: Dictionary specifying command to execute.
            See `rally info find VMTasks.boot_runcommand_delete' parameter
            `command' docstring for explanation.
        :param pkey: key for SSH authentication

        :returns: tuple (exit_status, stdout, stderr)
        """
        pkey = pkey if pkey else self.context["user"]["keypair"]["private"]
        ssh = sshutils.SSH(username, server_ip, port=port,
                           pkey=pkey, password=password)
        self._wait_for_ssh(ssh)
        return self._run_command_over_ssh(ssh, command)

    @staticmethod
    def _ping_ip_address(host):
        """Check ip address that it is pingable.

        :param host: instance of `netaddr.IPAddress`
        """
        ping = "ping" if host.version == 4 else "ping6"
        if sys.platform.startswith("linux"):
            cmd = [ping, "-c1", "-w1", str(host)]
        else:
            cmd = [ping, "-c1", str(host)]

        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        proc.wait()
        LOG.debug("Host %s is ICMP %s"
                  % (host, proc.returncode and "down" or "up"))
        return ICMP_UP_STATUS if (proc.returncode == 0) else ICMP_DOWN_STATUS
