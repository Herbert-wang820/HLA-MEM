from __future__ import annotations

import os

import uvicorn

from hla_memory_graph.app import create_app
from hla_memory_graph.internal.settings import Settings


def main() -> None:
    settings = Settings.load()
    uvicorn.run(
        create_app,
        factory=True,
        host=os.environ.get("HLA_BIND_HOST", "127.0.0.1"),
        port=settings.port,
        access_log=False,
    )


if __name__ == "__main__":
    main()
