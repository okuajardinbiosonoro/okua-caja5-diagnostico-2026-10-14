"""Read-only recording using current CKv2-resolved addresses, not old DHCP leases."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import caja5_signal_check_20261010 as capture
from caja5_ota_probe import get_secrets, get_node

_, token = get_secrets()
inventory = []
for node_id, (label, port, old_ip) in list(capture.NODES.items()):
    node = get_node(node_id, token)
    current_ip = node['control_plane']['resolved_ip']
    if not current_ip.startswith('192.168.88.') or node['label'] != label:
        raise RuntimeError('Unexpected node identity or network')
    capture.NODES[node_id] = (label, port, current_ip)
    inventory.append({'id': node_id, 'label': label, 'ip': current_ip, 'port': port})
print(json.dumps({'at_utc': datetime.now(timezone.utc).isoformat(), 'capture_inventory': inventory}), flush=True)
capture.main()
