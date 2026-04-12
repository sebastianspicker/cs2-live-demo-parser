from __future__ import annotations

import multiprocessing as mp
from typing import Any, Dict

from demo_parser import AdvancedDemoParser


def worker_loop(in_queue: mp.Queue, out_queue: mp.Queue) -> None:
    parser = None
    while True:
        message: Dict[str, Any] = in_queue.get()
        cmd = message.get("cmd")
        if cmd == "stop":
            break
        if cmd == "set_demo":
            demo_path = message.get("path")
            if demo_path:
                parser = AdvancedDemoParser(demo_path)
            out_queue.put({"cmd": "set_demo", "ok": parser is not None})
            continue
        if cmd == "poll":
            if not parser:
                out_queue.put({"cmd": "poll", "update": None})
                continue
            update = parser.parse_incremental()
            out_queue.put({"cmd": "poll", "update": update})


def start_worker() -> tuple[mp.Process, mp.Queue, mp.Queue]:
    in_queue: mp.Queue = mp.Queue()
    out_queue: mp.Queue = mp.Queue()
    process = mp.Process(target=worker_loop, args=(in_queue, out_queue), daemon=True)
    process.start()
    return process, in_queue, out_queue
