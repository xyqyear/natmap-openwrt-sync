#!/bin/ash

ip=$1
port=$2
ip4p=$3
inner_port=$4
protocol=$5

# space separated
urls="http://example1.com/mappings http://example2.com/mappings"

json_data="{\"$protocol:$inner_port\": {\"ip\": \"$ip\", \"port\": $port}}"

for url in "$urls"; do
    echo "Sending data to $url"
    echo "$json_data" | curl -m 5 -X PUT -H 'Content-Type:application/json' -d @- "$url"
done
