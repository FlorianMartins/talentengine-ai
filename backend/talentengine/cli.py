"""Command line: ``talentengine serve | seed | verify | keygen``."""

from __future__ import annotations

import argparse
import json

from .config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="talentengine", description="TalentEngine-AI command line")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve", help="run the API (and the built front-end if present)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    sub.add_parser("seed", help="load the fictional demo jobs and candidates")
    sub.add_parser("verify", help="verify the integrity of the audit ledger")
    sub.add_parser("keygen", help="print fresh values for TE_VAULT_KEY and TE_LEDGER_SEAL_KEY")
    args = parser.parse_args()

    if args.cmd == "keygen":
        import secrets

        from cryptography.fernet import Fernet

        print(f"TE_VAULT_KEY={Fernet.generate_key().decode()}")
        print(f"TE_LEDGER_SEAL_KEY={secrets.token_hex(32)}")
        return
    if args.cmd == "serve":
        import uvicorn

        uvicorn.run("talentengine.main:app", host=args.host, port=args.port)
        return

    from .pipeline import Engine

    engine = Engine(get_settings())
    if args.cmd == "seed":
        from .demo import seed_demo

        print(json.dumps(seed_demo(engine), indent=2, ensure_ascii=False))
    elif args.cmd == "verify":
        result = engine.verify_ledger()
        print(result.model_dump_json(indent=2))
        raise SystemExit(0 if result.valid else 1)


if __name__ == "__main__":
    main()
