#!/usr/bin/env bash
#
# build-package.sh — build a ktn fork's Arch package from its checkout.
#
# The contract every fork follows (docs/design/2026-10-03-ktn-fork-packages.md):
#   .ktn-base                    upstream tag the fork sits on (e.g. v0.8.4)
#   packaging/arch/PKGBUILD.in   template; @PKGVER@ and @UPSTREAM_VERSION@ are filled in,
#                                and it builds from source=("ktn-src.tar.gz"), which
#                                unpacks to ktn-src/ (a `git archive` of HEAD)
#
# pkgver = <base without v>.<HEAD committer time, UTC %Y%m%d%H%M>.g<sha7>
# Committer time rather than a commit count: a rebase-mode promote can lower the count
# on the same base, but cherry-picks always restamp the committer time.
#
# Used by .github/workflows/build-package.yml inside an archlinux container, and runnable
# by hand on an Arch machine to build a fork locally.
#
# Usage: build-package.sh [--syncdeps] [--newer-than <pkgver>] <repo-dir> <out-dir>
#        build-package.sh --print-pkgver <repo-dir>
#   --syncdeps          pass -s to makepkg (installs depends/makedepends; needs sudo)
#   --newer-than VER    fail unless the computed pkgver is newer than VER (vercmp), so a
#                       history rewrite can never publish a version pacman won't upgrade to
#   --print-pkgver      print the pkgver this checkout would build, and exit
#
# Prints `pkgver=<ver>` and `package=<path>` lines on success.

set -euo pipefail

die() { echo "build-package: $*" >&2; exit 1; }

SYNCDEPS=()
NEWER_THAN=""
PRINT_ONLY=0
while (( $# )); do
    case "$1" in
        --syncdeps) SYNCDEPS=(--syncdeps); shift ;;
        --newer-than) NEWER_THAN="${2:-}"; shift 2 ;;
        --print-pkgver) PRINT_ONLY=1; shift ;;
        -h|--help) sed -n '3,27p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        -*) die "unknown option: $1" ;;
        *) break ;;
    esac
done
if (( PRINT_ONLY )); then
    (( $# == 1 )) || die "usage: build-package.sh --print-pkgver <repo-dir>"
else
    (( $# == 2 )) || die "usage: build-package.sh [--syncdeps] [--newer-than VER] <repo-dir> <out-dir>"
fi

REPO=$(cd "$1" && pwd)
TEMPLATE="$REPO/packaging/arch/PKGBUILD.in"

[[ -f "$REPO/.ktn-base" ]] || die "$REPO/.ktn-base is missing"
[[ -f "$TEMPLATE" ]] || die "$TEMPLATE is missing"

BASE=$(tr -d '[:space:]' < "$REPO/.ktn-base")
UPSTREAM_VERSION=${BASE#v}
[[ "$UPSTREAM_VERSION" =~ ^[0-9][0-9A-Za-z.]*$ ]] \
    || die ".ktn-base '$BASE' is not a pacman-safe version"

STAMP=$(TZ=UTC git -C "$REPO" log -1 --format=%cd --date=format-local:%Y%m%d%H%M HEAD)
SHA=$(git -C "$REPO" rev-parse --short=7 HEAD)
PKGVER="${UPSTREAM_VERSION}.${STAMP}.g${SHA}"

if (( PRINT_ONLY )); then
    echo "$PKGVER"
    exit 0
fi
OUT=$(mkdir -p "$2" && cd "$2" && pwd)

if [[ -n "$NEWER_THAN" ]] && (( $(vercmp "$PKGVER" "$NEWER_THAN") <= 0 )); then
    die "pkgver $PKGVER is not newer than the published $NEWER_THAN — pacman would never
       offer it as an upgrade. This usually means ktn's history was rewritten to an older commit."
fi

WORK="$OUT/build"
rm -rf "$WORK"
mkdir -p "$WORK"

git -C "$REPO" archive --format=tar.gz --prefix=ktn-src/ -o "$WORK/ktn-src.tar.gz" HEAD
sed -e "s/@PKGVER@/${PKGVER}/g" -e "s/@UPSTREAM_VERSION@/${UPSTREAM_VERSION}/g" \
    "$TEMPLATE" > "$WORK/PKGBUILD"
grep -q '@[A-Z_]*@' "$WORK/PKGBUILD" && die "PKGBUILD.in has an unknown @PLACEHOLDER@"

( cd "$WORK" && makepkg "${SYNCDEPS[@]}" --noconfirm --clean --cleanbuild )

shopt -s nullglob
pkgs=("$WORK"/*.pkg.tar.zst)
shopt -u nullglob
(( ${#pkgs[@]} )) || die "makepkg produced no package"
for p in "${pkgs[@]}"; do
    [[ "$p" == *-debug-* ]] && continue
    mv "$p" "$OUT/"
    echo "package=$OUT/$(basename "$p")"
done
echo "pkgver=$PKGVER"
