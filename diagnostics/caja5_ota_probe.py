"""Controlled, non-deploying F3 capability probe for box 5.

Uses prior CKv2 nonces issued to *other* nodes, which are already behind CKv2's
global counter but unused within each target node's replay window. No secrets
or API tokens are written to the trace.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import socket
import struct
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


BASE = Path(r"C:\ProgramData\OKUA\apps\ckv2")
TOKEN_STORE = Path(r"C:\Users\jogoa\AppData\Local\OKUA\startup\secrets\remote_api_tokens.json")
TRACE_DIR = Path(__file__).resolve().parent / "caja5_ota_traces"
HOST_IP = "192.168.88.251"
NODE_IDS = (21, 22, 23, 24, 25)
CMD = struct.Struct("<HBBHHBBHHQ2sI")
ACK = struct.Struct("<HBBHHBBBBHHQI")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def get_secrets() -> tuple[bytes, str]:
    startup = (BASE / "start_ckv2_with_secret.bat").read_text(encoding="utf-8")
    match = re.search(r'^set "CKV2_CONTROL_SECRET=([^"\r\n]+)"', startup, re.M)
    if not match:
        raise RuntimeError("Control secret unavailable in configured startup script")
    data = json.loads(TOKEN_STORE.read_text(encoding="utf-8-sig"))
    return match.group(1).encode("utf-8"), data["tokens"][0]["token"]


def get_node(node_id: int, token: str) -> dict:
    req = Request(
        f"http://127.0.0.1:8788/api/v1/nodes/{node_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urlopen(req, timeout=5) as response:
        return json.load(response)["data"]


def tag(secret: bytes, first_24: bytes) -> int:
    return int.from_bytes(hmac.new(secret, first_24, hashlib.sha256).digest()[:4], "little")


def packet(secret: bytes, node_id: int, seq: int, nonce: int, cmd_id: int) -> bytes:
    pre = CMD.pack(0x4B4F, 1, 3, node_id, seq, cmd_id, 1, 0, 0, nonce, b"\0\0", 0)
    return pre[:24] + struct.pack("<I", tag(secret, pre[:24]))


def exchange(recv: socket.socket, send: socket.socket, secret: bytes,
             node_id: int, ip: str, seq: int, nonce: int, cmd_id: int) -> dict:
    data = packet(secret, node_id, seq, nonce, cmd_id)
    sent_at = now()
    send.sendto(data, (ip, 5007))
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline:
        recv.settimeout(max(0.01, deadline - time.monotonic()))
        try:
            raw, source = recv.recvfrom(2048)
        except socket.timeout:
            break
        if len(raw) != ACK.size:
            continue
        fields = ACK.unpack(raw)
        magic, version, kind, ack_node, ack_seq, echo, stage, status, flags, detail, retry, ack_nonce, auth = fields
        if (magic, version, kind, ack_node, ack_seq, echo, ack_nonce) != (
            0x4B4F, 1, 4, node_id, seq, cmd_id, nonce
        ):
            continue
        return {
            "sent_at_utc": sent_at, "received_at_utc": now(), "node_id": node_id,
            "ip": ip, "cmd_id": cmd_id, "seq": seq, "nonce": nonce,
            "packet_sha256": hashlib.sha256(data).hexdigest(), "ack": True,
            "ack_source": source[0], "ack_auth_valid": auth == tag(secret, raw[:24]),
            "ack_stage": stage, "status_code": status, "err_detail": detail,
            "ack_flags": flags, "retry_after_ms": retry,
        }
    return {"sent_at_utc": sent_at, "node_id": node_id, "ip": ip,
            "cmd_id": cmd_id, "seq": seq, "nonce": nonce,
            "packet_sha256": hashlib.sha256(data).hexdigest(), "ack": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ping-only", action="store_true")
    args = parser.parse_args()
    secret, token = get_secrets()
    snapshots = {i: get_node(i, token) for i in NODE_IDS}
    control = {i: snapshots[i]["control_plane"] for i in NODE_IDS}
    for i in NODE_IDS:
        assert snapshots[i]["runtime"]["status"] == "online", f"Node {i} not online"
        assert control[i]["last_final_status"] == "ack_matched", f"Node {i} lacks baseline ACK"
        assert control[i]["resolved_ip"].startswith("192.168.88."), f"Unexpected IP for {i}"
    seqs = [control[i]["last_cmd_seq"] for i in NODE_IDS]
    nonces = [control[i]["last_nonce"] for i in NODE_IDS]
    assert seqs == list(range(seqs[0], seqs[0] + len(NODE_IDS))), "Sequences not consecutive"
    assert nonces == list(range(nonces[0], nonces[0] + len(NODE_IDS))), "Nonces not consecutive"

    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    trace = TRACE_DIR / f"probe_{datetime.now().strftime('%Y%m%dT%H%M%S')}.jsonl"
    records = []

    def record(event: dict) -> None:
        records.append(event)
        with trace.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")

    record({"event": "baseline", "at_utc": now(), "host_ip": HOST_IP,
            "mode": "ping_only" if args.ping_only else "ping_then_ota_zero_token",
            "nodes": {str(i): {"ip": control[i]["resolved_ip"],
                                "status": snapshots[i]["runtime"]["status"],
                                "fw": f"{snapshots[i]['runtime']['fw_major']}.{snapshots[i]['runtime']['fw_minor']}",
                                "uptime_s": snapshots[i]["runtime"]["last_uptime_s"],
                                "prior_seq": control[i]["last_cmd_seq"],
                                "prior_nonce": control[i]["last_nonce"]} for i in NODE_IDS}})

    recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    recv.bind((HOST_IP, 5008))
    send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    send.bind((HOST_IP, 0))
    try:
        targets = NODE_IDS[:1] if args.ping_only else NODE_IDS
        for index, node_id in enumerate(targets):
            ip = control[node_id]["resolved_ip"]
            # EB5 already consumed the nonce from node 22 during the listener
            # validation run; use another previously issued nonce here.
            ping_source = 4 if node_id == 21 and not args.ping_only else (index + 1) % len(NODE_IDS)
            ping = exchange(recv, send, secret, node_id, ip,
                            seqs[ping_source], nonces[ping_source], 1)
            record({"event": "ping", **ping})
            if not ping["ack"] or not ping.get("ack_auth_valid") or ping.get("status_code") != 0:
                record({"event": "halt", "at_utc": now(), "reason": "PING probe not validated"})
                break
            if args.ping_only:
                continue
            ota_source = (index + 2) % len(NODE_IDS)
            ota = exchange(recv, send, secret, node_id, ip,
                           seqs[ota_source], nonces[ota_source], 8)
            record({"event": "ota_zero_token", **ota})
            after = get_node(node_id, token)
            record({"event": "after", "at_utc": now(), "node_id": node_id,
                    "status": after["runtime"]["status"],
                    "uptime_s": after["runtime"]["last_uptime_s"],
                    "ota_state": after["ota"]["state_key"],
                    "ota_error": after["ota"]["error_key"]})
    finally:
        send.close()
        recv.close()
    print(json.dumps({"trace": str(trace), "results": records}, ensure_ascii=False))


if __name__ == "__main__":
    main()
