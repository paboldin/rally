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

from __future__ import print_function

import json
import re
import sys


def parse_output(stdout):
    connected = re.findall(
        "\[.*?(\d+)\].*\s+local ([\d\.]+).*connected with ([\d\.]+)",
        stdout)
    clients = dict((thread, "%s-%s" % (local, remote))
                   for thread, local, remote in connected)

    file_throughput = 0.0
    per_client_throughput = {}

    thread_values = re.findall(
        "\[.*?(\d+)\].*\s+(\d+\.?\d*).([GM])bits/sec",
        stdout)

    for thread, value, suffix in thread_values:
        value = float(value)
        if suffix == "G":
            value *= 1024
        file_throughput += value

        ip = clients[thread]
        per_client_throughput.setdefault(ip, 0.0)
        per_client_throughput[ip] += value

    return file_throughput, per_client_throughput


def main():
    result_input = json.load(sys.stdin)

    total_throughput = 0.0
    per_client_throughput = {}

    for agent_id, filename in result_input["stdout"].items():
        with file(filename) as fh:
            stdout = fh.read()

        print("============\n\n", file=sys.stderr)
        print("AGENT %s\n" % agent_id, file=sys.stderr)
        print(stdout, file=sys.stderr)
        print("============\n\n", file=sys.stderr)

        subtotal, perclient = parse_output(stdout)
        total_throughput += subtotal
        per_client_throughput.update(perclient)

    data = {
        "total": total_throughput,
    }
    data.update(per_client_throughput)
    json.dump(
        {
            "data": data,
        }, sys.stdout, indent=2)

if __name__ == "__main__":
    main()
