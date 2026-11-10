"""Applies board/migrations/*.sql in name order to the board database. Each migration is safe to run again.

python3 -m board.migrate            the real board (W/data/board.db)
python3 -m board.migrate PATH       another copy, for testing
"""
import glob, os, sqlite3, sys

from board.mirror import DB

MIGRATIONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")


def main(path=DB):
    if not os.path.exists(path):
        sys.exit(f"no database at {path}")
    db = sqlite3.connect(path)
    for f in sorted(glob.glob(os.path.join(MIGRATIONS, "*.sql"))):
        with open(f) as fh:
            db.executescript(fh.read())
        print(f"applied {os.path.basename(f)}")
    db.close()


if __name__ == "__main__":
    main(*sys.argv[1:2])
