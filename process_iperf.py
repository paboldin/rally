#!/usr/bin/python

import re
import sys

import json

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

        print >>sys.stderr, "============\n\n"
        print >>sys.stderr, "AGENT %s\n" % agent_id
        print >>sys.stderr, stdout
        print >>sys.stderr, "============\n\n"

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
