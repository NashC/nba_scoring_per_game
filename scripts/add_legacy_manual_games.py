from __future__ import annotations

import argparse

from nba_scoring_per_game.manual_games import write_supported_legacy_approximations


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add the supported legacy manual approximations to a dataset directory."
    )
    parser.add_argument("--out-dir", default="data")
    parser.add_argument(
        "--game-id",
        action="append",
        dest="game_ids",
        help="Optional legacy game id to write. Repeat to write a subset.",
    )
    args = parser.parse_args()

    written = write_supported_legacy_approximations(args.out_dir, game_ids=args.game_ids)
    print(f"WRITTEN_GAMES {len(written)}")
    for game_id, targets in written.items():
        print(f"GAME_ID {game_id}")
        for name, path in targets.items():
            print(f"{name} {path}")


if __name__ == "__main__":
    main()
