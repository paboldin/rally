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

import collections
import tempfile
import time

import requests

from rally.common import log as logging

LOG = logging.getLogger(__name__)


class SwarmConnection(object):
    def __init__(self, http_url, agents=None):
        self.http_url = http_url
        self.agents = agents

    def _get_url(self, path):
        url = self.http_url + "/" + path
        if self.agents is not None:
            url += "?agents=%d" % self.agents
        return url

    def run_command_thread(self, command_with_args, env=None, stdin=None):
        command = {
            "path": command_with_args,
            "thread": "true"
        }

        if env is not None:
            command["env"] = env
        if stdin is not None:
            command["stdin"] = stdin

        LOG.debug("Running command %r on %d agent(s) via %s" % (
            command, self.agents, self.http_url))

        commands = requests.post(
            self._get_url("command"),
            data=command,
        ).json()

        LOG.debug("Commands %r started on %s" % (commands, self.http_url))

        return commands

    def wait(self, can_run_off=0, loop_sleep=1, loops=1000):

        assert self.agents > can_run_off

        run = {
            "stdout": collections.defaultdict(tempfile.NamedTemporaryFile),
            "stderr": collections.defaultdict(tempfile.NamedTemporaryFile),
            "exit_code": {}
        }

        updated = False
        finished = 0

        for x in range(loops):
            if not updated:
                checks = self.check()

                LOG.debug("Checking %r" % checks)

                finished = 0
                for check in checks:
                    if check["exit_code"] is not None:
                        finished += 1
                        run["exit_code"][check["agent"]] = check["exit_code"]

            tails = self.tail()

            LOG.debug("Tailed %r" % tails)

            updated = False
            for tail in tails:
                agent = tail["agent"]
                for fd in "stdout", "stderr":
                    if tail[fd]:
                        run[fd][agent].write(tail[fd].encode("utf-8"))
                        updated = True

            # NOTE(pboldin): Always tail after agent's process is done,
            #                otherwise there could be a data lost.
            if finished >= self.agents - can_run_off:
                break

            time.sleep(loop_sleep)

        return run

    def check(self):
        return requests.post(self._get_url("check")).json()

    def tail(self):
        return requests.post(self._get_url("tail")).json()

    def ping(self, verbose=False):
        try:
            pings = requests.get(self._get_url("ping")).json()
        except requests.exceptions.RequestException:
            LOG.debug("MasterAgent %s is down." % self.http_url)
            return

        LOG.debug("%d agents is up through %s." % (len(pings), self.http_url))

        if verbose:
            LOG.debug("Response is %r" % pings)

        return pings

    def status(self, dummy=None):
        pings = self.ping()
        if pings is None:
            return "DOWN"

        if len(pings) == self.agents:
            return "UP ALL"

        return "UP %d" % len(pings)
