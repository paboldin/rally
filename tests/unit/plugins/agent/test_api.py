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

import ddt
import mock
import testtools

from rally.plugins.agent import api as agent_api

BASE = "rally.plugins.agent.api"


@ddt.ddt
class SwarmConnectionTestCase(testtools.TestCase):
    @mock.patch(BASE + ".requests")
    def test_ping(self, mock_requests):
        swarm_connection = agent_api.SwarmConnection("foobar", 42)

        mock_requests.get.return_value.json.return_value = list(range(4))
        retval = swarm_connection.ping()

        mock_requests.get.assert_called_once_with(
            "foobar/ping?agents=42")

        self.assertEqual([0, 1, 2, 3], retval)

    @mock.patch(BASE + ".requests")
    def test_ping_down(self, mock_requests):
        swarm_connection = agent_api.SwarmConnection("foobar", 42)

        mock_requests.exceptions.RequestException = ValueError
        mock_requests.get.side_effect = ValueError()
        retval = swarm_connection.ping()

        self.assertIsNone(retval)

    @ddt.data(
        (None, "DOWN"),
        ([0], "UP 1"),
        ([0, 1], "UP ALL")
    )
    @ddt.unpack
    def test_status(self, pings, expected):
        swarm_connection = agent_api.SwarmConnection("foobar", 2)

        swarm_connection.ping = mock.Mock(return_value=pings)
        retval = swarm_connection.status()

        self.assertEqual(expected, retval)

    @mock.patch(BASE + ".requests")
    def test_run_command_thread(self, mock_requests):
        swarm_connection = agent_api.SwarmConnection("foobar", 42)

        retval = swarm_connection.run_command_thread(
            "foobar", env="env", stdin="stdin")

        mock_requests.post.assert_called_once_with(
            "foobar/command?agents=42",
            data={
                "path": "foobar",
                "env": "env",
                "stdin": "stdin",
                "thread": "true"
            }
        )
        self.assertEqual(
            mock_requests.post.return_value.json.return_value, retval)

    @mock.patch(BASE + ".time.sleep")
    def test_wait(self, mock_time_sleep):
        swarm_connection = agent_api.SwarmConnection("foobar", 2)

        swarm_connection.check = mock.Mock(
            side_effect=[
                [  # first check
                    {
                        "agent": "foo",
                        "exit_code": None
                    },
                    {
                        "agent": "bar",
                        "exit_code": None
                    }
                ],
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
                [  # finished check
                    {
                        "agent": "foo",
                        "exit_code": 63
                    },
                    {
                        "agent": "bar",
                        "exit_code": None
                    }
                ]
            ]
        )

        swarm_connection.tail = mock.Mock(
            side_effect=[
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
                [  # tail after check
                    {
                        "agent": "foo",
                        "stdout": ",",
                        "stderr": ",",
                    },
                    {
                        "agent": "bar",
                        "stdout": ".",
                        "stderr": ".",
                    }
                ]
            ]
        )

        retval = swarm_connection.wait(1, loop_sleep=3)

        self.assertEqual(
            [
                mock.call(3),
                mock.call(3),
                mock.call(3),
                mock.call(3),
            ],
            mock_time_sleep.mock_calls)

        self.assertEqual({"foo": 63}, retval["exit_code"])

        self.assertEqual(3, swarm_connection.check.call_count)
        self.assertEqual(5, swarm_connection.tail.call_count)

        def check_content(fh, expected):
            fh.seek(0)
            self.assertEqual(expected.encode("utf-8"), fh.read())

        check_content(
            retval["stdout"]["foo"],
            "FORGET ABOUT YOUR HOUSE OF CARDS,")
        check_content(
            retval["stdout"]["bar"],
            "AND I'LL DO MINE.")
        check_content(
            retval["stderr"]["foo"],
            "DENIAL, DENIAL DENIAL, DENIAL,")
        check_content(
            retval["stderr"]["bar"],
            "YOUR EARS SHOULD BE BURNING.")

    def test__get_url(self):
        swarm_connection = agent_api.SwarmConnection("foobar")
        retval = swarm_connection._get_url("bar")
        self.assertEqual("foobar/bar", retval)

        swarm_connection = agent_api.SwarmConnection("foobar", 3)
        retval = swarm_connection._get_url("bar")
        self.assertEqual("foobar/bar?agents=3", retval)

    @mock.patch(BASE + ".requests")
    def test_check(self, mock_requests):
        swarm_connection = agent_api.SwarmConnection("foobar", 2)
        retval = swarm_connection.check()
        mock_requests.post.assert_called_once_with(
            "foobar/check?agents=2")
        self.assertEqual(
            mock_requests.post.return_value.json.return_value,
            retval)

    @mock.patch(BASE + ".requests")
    def test_tail(self, mock_requests):
        swarm_connection = agent_api.SwarmConnection("foobar", 2)
        retval = swarm_connection.tail()
        mock_requests.post.assert_called_once_with(
            "foobar/tail?agents=2")
        self.assertEqual(
            mock_requests.post.return_value.json.return_value,
            retval)
