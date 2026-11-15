#!/usr/bin/env bash
# Clone each baseline's original repository at its pinned commit into
# third_party/upstream.  Those paths are git submodules of this repository
# (only URL + commit are recorded; SADI, MERA and AUSteer publish no license,
# so their code is never copied here).  `git submodule update --init` gives
# the same checkouts; this script makes shallow clones instead and skips
# CAA's ~280 MB of result files.
set -Eeuo pipefail

ROOT="${JLENS_UPSTREAM_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/third_party/upstream}"
mkdir -p "$ROOT"

fetch() {
  local name="$1" url="$2" commit="$3" sparse="${4:-}"
  local dest="$ROOT/$name"
  if [[ -d "$dest/.git" ]] && [[ "$(git -C "$dest" rev-parse HEAD)" == "$commit" ]]; then
    echo "ok   $name @ $commit"
    return
  fi
  rm -rf "$dest"
  git init -q "$dest"
  git -C "$dest" remote add origin "$url"
  if [[ -n "$sparse" ]]; then
    local patterns
    read -r -a patterns <<<"$sparse"
    git -C "$dest" sparse-checkout set --no-cone "${patterns[@]}"
  fi
  git -C "$dest" fetch -q --depth 1 --filter=blob:none origin "$commit"
  git -C "$dest" checkout -q --detach FETCH_HEAD
  local head
  head="$(git -C "$dest" rev-parse HEAD)"
  [[ "$head" == "$commit" ]] || { echo "ERROR: $name is at $head, expected $commit" >&2; exit 1; }
  echo "$commit" > "$dest/.jlens-upstream-commit"
  echo "got  $name @ $commit"
}

# CAA ships ~280 MB of result files; only the code is needed.
fetch CAA https://github.com/nrimsky/CAA.git \
  5dabbbd9a0bca5f25e174501e959de378806aa48 \
  '/*.py /utils/ /LICENSE /requirements.txt'
fetch activation-steering https://github.com/IBM/activation-steering.git \
  52be60235ee309b46c49d6d5877f36e20c52e6ab
fetch MERA-steering https://github.com/annahedstroem/MERA-steering.git \
  1a1e6880e885ef9905815baed065e0cbbeed70c7
fetch SADI https://github.com/weixuan-wang123/SADI.git \
  47b11e4f0818ce4ca625f0c86e59f882ddb0656b
fetch honest_llama https://github.com/likenneth/honest_llama.git \
  2c6b2179be7b5aa8f0a171688cf9e01b812ca327
fetch AUSteer https://github.com/zijian678/AUSteer.git \
  d6573876734f662824062a69c5b9dee31ae57f81

echo "Upstreams ready under $ROOT"
