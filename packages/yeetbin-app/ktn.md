---
package: yeetbin-app
summary: The `yeet` CLI — throw a file or stdin at yeetbin and get a shareable link back
upstream: https://github.com/Kautiontape/yeetbin-app
---
## What it is

`yeet`, the command-line client for [yeetbin](https://yeet.kautiontape.com). Pass it a file
or pipe stdin, and it uploads, prints the link and opens it in your browser. It's one static
Go binary with no runtime dependencies.

## Why it exists

yeetbin is a self-hosted, Obsidian-flavored alternative to yeet.md. Sharing from a terminal
should be one word, without opening a browser to paste into.

## How it differs from upstream

This is not a fork. It's a Kautiontape project, and `[ktn]` is its home for Arch. The package
installs `/usr/bin/yeet`, so it conflicts with the unrelated
[`yeet`](https://aur.archlinux.org/packages/yeet) pacman wrapper from the AUR.
