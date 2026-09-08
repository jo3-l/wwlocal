"""wwlocal: a local mirror + browser for WaterlooWorks co-op postings.

login   open a browser, complete UW SSO + Duo, save the session cookies
sync    pull the (filtered) board into data/waterlooworks_jobs.db
view    serve the viewer page over the local databases
"""

import argparse
import sys

from wwlocal import login, sync, viewer, waterlooworks
from wwlocal.config import DEFAULT_CLUSTERS


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="wwlocal", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login", help="save a WaterlooWorks session")

    sp = sub.add_parser("sync", help="pull postings into the local database")
    sp.add_argument(
        "--clusters", help=f"comma-separated cluster ids (default {','.join(DEFAULT_CLUSTERS)})"
    )
    sp.add_argument(
        "--all", action="store_true", help="no cluster filter: every posting on the board"
    )
    sp.add_argument("--keyword", default="", help="server-side keyword search")
    sp.add_argument(
        "--refresh-details", action="store_true", help="re-fetch details for every listed posting"
    )

    vp = sub.add_parser("view", help="serve the viewer and open it in a browser")
    vp.add_argument("--host", default="127.0.0.1")
    vp.add_argument("--port", type=int, default=8765)
    vp.add_argument(
        "--include-closed", action="store_true", help="also show postings that left the board"
    )
    vp.add_argument("--no-open", action="store_true", help="don't open a browser tab")

    args = ap.parse_args()
    try:
        if args.cmd == "login":
            login.run()
        elif args.cmd == "sync":
            clusters = (
                []
                if args.all
                else (args.clusters.split(",") if args.clusters else DEFAULT_CLUSTERS)
            )
            sync.run(clusters, args.keyword, args.refresh_details)
        else:
            viewer.serve(args.host, args.port, args.include_closed, open_browser=not args.no_open)
    except waterlooworks.NotLoggedIn as e:
        sys.exit(f"{e}. Run: uv run wwlocal login")


if __name__ == "__main__":
    main()
