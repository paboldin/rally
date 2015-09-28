#!/bin/sh

set -e
set -x

main() {
    apt-get update
    apt-get update
    apt-get install python-zmq -y

    mkdir -p /opt/rally-agent
    wget https://raw.githubusercontent.com/paboldin/rally-agent/master/masteragent.py -O /opt/rally-agent/masteragent.py
    wget https://raw.githubusercontent.com/paboldin/rally-agent/master/agent.py -O /opt/rally-agent/agent.py

    cat > /opt/rally-agent/init.sh <<'EOF'
#!/bin/sh

set -e
set -x

exec 2>&1
exec > /tmp/agent.log

URLS="--subscribe-url tcp://127.0.0.1:1234 --push-url tcp://127.0.0.1:1235"
AGENT_ID="--agent-id 0"
if [ ! -f /opt/rally-agent/master-agent-host ]; then
    python /opt/rally-agent/masteragent.py &
else
    . /opt/rally-agent/master-agent-host
    URLS="--subscribe-url tcp://${ZMQ_MASTER_AGENT_HOST}:1234 --push-url tcp://${ZMQ_MASTER_AGENT_HOST}:1235"
    [ -n "$AGENT_ID" ] && AGENT_ID="--agent-id $AGENT_ID"
fi

python /opt/rally-agent/agent.py $URLS $AGENT_ID &
EOF

    chmod a+x /opt/rally-agent/init.sh

    sed -i '$d' /etc/rc.local

    echo "/opt/rally-agent/init.sh &" >> /etc/rc.local
    echo exit 0 >> /etc/rc.local
}

main
