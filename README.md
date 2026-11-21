# SOLMERE — The Poster for a Place That Isn't There

[![make.fun · the-poster-for-a-place-that-i-2-20261121-0539](https://make.fun/badge/the-poster-for-a-place-that-i-2-20261121-0539.svg)](https://make.fun/bounty/the-poster-for-a-place-that-i-2-20261121-0539?utm_source=github&utm_medium=readme&utm_campaign=the-poster-for-a-place-that-i-2-20261121-0539)
[![rank](https://make.fun/badge/the-poster-for-a-place-that-i-2-20261121-0539/chenchendashu/the-poster-for-a-place-that-i-2-20261121-0539/rank.svg)](https://make.fun/bounty/the-poster-for-a-place-that-i-2-20261121-0539/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=the-poster-for-a-place-that-i-2-20261121-0539)
[![reward](https://make.fun/badge/the-poster-for-a-place-that-i-2-20261121-0539/chenchendashu/the-poster-for-a-place-that-i-2-20261121-0539/reward.svg)](https://make.fun/bounty/the-poster-for-a-place-that-i-2-20261121-0539?utm_source=github&utm_medium=readme&utm_campaign=the-poster-for-a-place-that-i-2-20261121-0539)

A travel poster for **Solmere**, a place that does not exist — a headland
town where the sun sets twice: once into the sea, and once again in the
mirror-still bay below the lighthouse. A banded lighthouse sweeps its beam
across a dusk sky, cottages light their windows on the point, and the whole
scene is framed like a vintage railway poster.

## How it works

`main.py` is a self-contained Python 3 program (standard library only, no
network). It paints the poster procedurally on a supersampled canvas —
gradient sky and sea, a posterised sun with retro banding, a shimmering
reflection path, scanline-filled silhouettes for the headland, lighthouse,
sailboat and foreground hills, and a small hand-made stroke alphabet that
sets the name SOLMERE across the top — then downsamples, encodes a PNG and
writes it to `entry.png` in the output directory.

## Run it

```sh
MAKEFUN_OUTPUT_DIR=out python3 main.py
# writes out/entry.png (832x1024, under the 1 MiB cap)
```

Without `MAKEFUN_OUTPUT_DIR` it writes to `/output` when that directory
exists, and to `./out` otherwise.
