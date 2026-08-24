from __future__ import annotations

import argparse
import json
from pathlib import Path

from console.devos_console.settings import load_settings

from .exact_delivery import ExactDeliveryStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-id", required=True)
    parser.add_argument("--runtime-dir", type=Path)
    args = parser.parse_args()
    settings = load_settings(dev_mode=True)
    runtime_dir = (args.runtime_dir or settings.runtime_dir).resolve()
    store = ExactDeliveryStore(
        runtime_dir / "exact-deliveries",
        runtime_dir / "return-handoffs",
    )
    value = store.create("btest", args.return_id)
    print(json.dumps({
        "delivery_id": value["delivery_id"],
        "delivery_packet_sha256": value["delivery_packet_sha256"],
        "return_envelope_sha256": value["return_envelope_sha256"],
        "source_dispatch_id": value["source_dispatch_id"],
        "destination_node_id": value["destination_node_id"],
        "result_content_sha256": value["result_content_sha256"],
        "state": value["state"],
        "actual_mainline_send_count": value["actual_mainline_send_count"],
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
