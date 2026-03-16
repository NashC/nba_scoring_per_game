from __future__ import annotations

import argparse

from nba_scoring_per_game.manual_games import WILT_100_GAME_ID, write_wilt_100_approximation


def main() -> None:
    parser = argparse.ArgumentParser(description="Add the manual Wilt 100 approximation to a dataset directory.")
    parser.add_argument("--out-dir", default="data")
    args = parser.parse_args()

    written = write_wilt_100_approximation(args.out_dir)
    print(f"WRITTEN_GAME_ID {WILT_100_GAME_ID}")
    for name, path in written.items():
        print(f"{name} {path}")


if __name__ == "__main__":
    main()
