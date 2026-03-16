# Legacy Games Catalog

This file tracks important pre-1996 scoring games that sit outside the core official `PlayByPlayV3` era used by the pipeline.

The purpose is operational:

- keep a vetted list of legacy scoring-game candidates
- distinguish true event-level coverage from manual approximation candidates
- prioritize which old games are worth reconstructing next

The current seed catalog lives in:

- [legacy_game_catalog.csv](/Users/nash/Documents/coding_projects/nba_scoring_per_game/docs/legacy_game_catalog.csv)
- [legacy_split_catalog.csv](/Users/nash/Documents/coding_projects/nba_scoring_per_game/docs/legacy_split_catalog.csv)

## How to use it

- Treat Wikipedia as the discovery index only, not the canonical source.
- Prefer official NBA pages, then box scores or reputable historical recaps, when deciding whether a manual approximation is justified.
- Do not mix legacy approximations into the core official-source logic without labeling them clearly.

## Coverage tiers

- `manual_approximation_added`
  - A synthetic version already exists in the local parquet dataset.
- `quarter_split_available`
  - Quarter scoring detail is available, which is usually enough for a credible quarter-even approximation.
- `half_split_available`
  - Half-level detail exists, but not full quarter scoring.
- `quarter_partial_available`
  - Some quarter detail exists, but it is incomplete.
- `box_score_plus_video`
  - Good confirmation of the box score and game context, but not enough structured intra-game scoring detail.
- `box_score_plus_official_story`
  - Strong official narrative support, but still not enough structured intra-game scoring detail.
- `box_score_indexed`
  - The game is well established in scoring-history lists, but we do not yet have a strong supporting detail source for reconstruction.

## Suggested modeling labels

- `existing_manual_model`
  - Already implemented.
- `quarter_even_model`
  - Spread the known quarter scoring evenly within each quarter.
- `half_even_model`
  - Spread known half scoring evenly within each half.
- `quarter_partial_model`
  - Use the known quarter fragments directly, then fill the remaining scoring evenly.
- `regulation_plus_ot_model`
  - Keep the known overtime split and spread the unresolved regulation scoring evenly unless better quarter evidence is found.
- `game_even_model`
  - Spread scoring evenly across the full game. Lowest-confidence approximation tier.

## Current best next candidates

Based on current source quality, the best next manual legacy additions are:

1. Michael Jordan 69, March 28, 1990
2. David Thompson 73, April 9, 1978
3. David Robinson 71, April 24, 1994
4. Pete Maravich 68, February 25, 1977
5. Elgin Baylor 71, November 15, 1960

The split catalog makes the evidence level explicit:

- full quarter-ready:
  - Wilt 100
  - Baylor 71
  - Thompson 73
  - Robinson 71
  - Jordan 69
  - Maravich 68
- partial but still modelable:
  - Gervin 63
  - Baylor 61 Finals
  - Jordan 63 playoffs
- still weak:
  - Wilt 78 and other non-Wilt repeat mega-games without verified split checkpoints

## Important constraint

These legacy rows should stay explicitly labeled as approximations. They are useful for historical comparison in the app, but they are not equivalent in confidence to official post-1996 event-level play-by-play.
