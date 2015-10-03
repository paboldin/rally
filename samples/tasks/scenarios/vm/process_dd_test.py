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

import collections
import json
import sys


def main():
    run_results = json.load(sys.stdin)

    disk_bandwidth = collections.defaultdict(float)

    for agent_id, filename in run_results["stdout"].items():
        with file(filename) as fh:
            stdout = fh.read()

        print("============\n\n", file=sys.stderr)
        print("AGENT %s\n" % agent_id, file=sys.stderr)
        print(stdout, file=sys.stderr)
        print("============\n\n", file=sys.stderr)

        agent_result = json.loads(stdout)

        for key, value in agent_result.items():
            disk_bandwidth[key] += value
            disk_bandwidth[key + "_" + agent_id] = value

    json.dump(
        {
            "data": disk_bandwidth,
        }, sys.stdout, indent=2)

if __name__ == "__main__":
    main()
