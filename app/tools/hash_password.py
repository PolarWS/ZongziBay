import argparse
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.core.password_hash import hash_password


def main() -> int:
    parser = argparse.ArgumentParser(description="生成可写入 config 的 security.password 哈希")
    parser.add_argument("password", help="明文密码")
    args = parser.parse_args()

    print(hash_password(args.password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
