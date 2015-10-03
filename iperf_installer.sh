#!/bin/sh

set -e
set -x

main() {
    apt-get install iperf
    cat > /usr/bin/start_iperf.sh <<'EOF'
#!/bin/sh

if [ "$AGENT_ID" != "$(($AGENTS_TOTAL - 1))" ]; then
    iperf -s &
fi

sleep 1

for target_agent_id in $(seq 0 $((AGENT_ID - 1))); do
    fixed_ip_var=FIXED_IP$target_agent_id
    eval fixed_ip=\$$fixed_ip_var
    iperf -c $fixed_ip -t 60 -P 3 >/dev/null 2>&1 &
done
EOF

    chmod a+x /usr/bin/start_iperf.sh
}

main
