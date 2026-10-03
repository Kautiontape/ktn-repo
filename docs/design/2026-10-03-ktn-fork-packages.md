# Fork packages in [ktn], and the kautiontape.com/arch/ page

**Status:** agreed 2026-10-03 (brainstorm with Shawn). Implementation follows the phases at the end.

## Goal

1. Two locally patched packages, `vesktop-ptt` and a patched `xdg-desktop-portal-wlr`, become proper
   Kautiontape forks. They track upstream the same way trilium and actual do, and publish into the
   signed `[ktn]` repo.
2. A page at `kautiontape.com/arch/` lists every `[ktn]` package with copyable setup instructions,
   and has one page per package explaining what it is, why it exists, how it differs from upstream,
   and when it was last built. Nobody edits the page. Each package's own repo holds its content.

## What already exists (and is reused)

| Piece | Where | Role |
|---|---|---|
| `[ktn]` repo | `Kautiontape/ktn-repo`, `publish.yml` | The only writer of the signed index. Builds `packages/*`, pulls `external.txt` releases, re-signs everything, publishes to the `repo` release. Runs nightly at 06:17 UTC. |
| fork-sync | `Kautiontape/fork-sync` | Reusable upstream-release detector. Rebase or merge onto new tags, opens a `sync/<tag>` PR, sends an ntfy ping. `fork-sync-promote.yml` ships rebase syncs. |
| Fork template | `Kautiontape/trilium` (merge), `Kautiontape/actual` (rebase) | Deploy branch `ktn`, a `.ktn-base` marker, and `ktn-*` workflows. |
| Org secrets | `NTFY_URL`, `SYNC_PR_TOKEN` | Used by fork-sync. |
| Self-hosted runner | `[self-hosted, ktn]`, Default group (all repos, public allowed) | Deploys static sites into `/opt/services/*`. |
| nginx | `/etc/nginx/sites-available/kautiontape.com` on ktn (hand-managed) | `/window-runner/` alias is the separate-deploy precedent. |

Renovate (the Mend app plus `Kautiontape/renovate-config`) only handles dependencies. **Upstream
release tracking is fork-sync's job**, and that is what "set up like our other forks" means here.

## Decisions

| # | Decision | Why |
|---|---|---|
| D1 | Upstream tracking is done by a fork-sync caller, as in trilium and actual. Renovate is not involved. | Matches every existing fork. |
| D2 | Each fork's own CI builds its package (trilium's pattern), and ktn-repo pulls it through `external.txt`. | The toolchain stays with the code, and a promoted sync publishes with no pkgver bump commit elsewhere. |
| D3 | A reusable `build-package.yml` lives in ktn-repo. Each fork calls it in about 15 lines. Trilium keeps its custom electron-forge job for now. | One copy of the packaging contract, kept in the repo that owns it. |
| D4 | The page is at `kautiontape.com/arch/`. ktn-repo's publish workflow renders it, the self-hosted runner deploys it, and an nginx alias serves it. | No DNS or cert work. It updates whenever the index does. |
| D5 | Both forks use fork-sync **rebase** mode plus promote. | The carried patch sets are small. Replaying them keeps `ktn` = upstream + N commits. |
| D6 | The xdpw patch goes upstream after it has soaked. Nothing is posted without Shawn's review. | A real gap upstream (#170 has been open since 2021), and it lets the fork retire. |
| D7 | **Pinned-ahead-of-release standard** (see below). Vesktop starts pinned to upstream main. | The Electron 44 build and the fixes on main are wanted now. Release tags are the default. |

## Forks

| Fork | Upstream | `ktn` = | `.ktn-base` | Package |
|---|---|---|---|---|
| `Kautiontape/vesktop` | `Vencord/Vesktop` | main @ `0ead609` + PR #1238 squashed + modal-API port | `v1.6.7` | `vesktop-ktn` |
| `Kautiontape/xdg-desktop-portal-wlr` | `emersion/xdg-desktop-portal-wlr` | `v0.8.4` + window-restore patch | `v0.8.4` | `xdg-desktop-portal-wlr-ktn` |

- `.ktn-base` must be committed on `ktn` **before** fork-sync first runs. fork-sync fails loudly
  without it.
- Packages declare `provides`/`conflicts` against the stock names and **never `replaces`**.
  `replaces` would make `pacman -Syu` offer the swap to every `[ktn]` user.
- Upstream workflows that come with a fork are disabled with `gh workflow disable` (Vesktop: release,
  test, meta, update-vencord-dev, winget-submission). xdpw ships none, only `.builds/`.

### Pinned ahead of release (D7)

Normally `ktn` = the latest upstream release tag + carried commits. When a needed change exists
only on upstream main, `ktn` may instead be a **main commit** + carried commits. `.ktn-base` stays
at the newest release that is an ancestor of that commit.

This needs no fork-sync change. Rebase mode replays
`git rev-list --reverse --no-merges HEAD --not <old base> <new tag>`. Once a release tag contains
the pinned commit, every upstream commit is reachable from the new tag and gets excluded. Only the
carried commits are replayed, so the fork is back on releases without anyone acting. If a release is
cut from a branch that *lacks* the pin, the sync PR visibly carries those main commits, and Shawn
decides. The descriptor's `pinned:` field shows the state on the page. Remove it once the base is a
release tag.

## Descriptor: `packaging/arch/ktn.md`

This is the only per-package content the page reads. It lives in the fork, or at
`ktn-repo/packages/<name>/ktn.md` for packages built centrally.

```markdown
---
package: vesktop-ktn
summary: One line for the package card
upstream: https://github.com/Vencord/Vesktop
pinned: upstream main @ 0ead609 (Electron 44), until a release includes it   # optional
retire_when: An upstream release ships the vesktop.sock IPC socket (PR #1238); checked by hand
---
## What it is
## Why it exists
## How it differs from upstream
```

Version, build date and upstream base come from `ktn.db` (`%VERSION%`, `%BUILDDATE%`) and
`.ktn-base`. They are never typed by hand. A missing or broken descriptor falls back to `%DESC%`
and never fails a run. Existing packages get descriptors too: `triliumnext-ktn-bin` in the trilium
fork, and `yeetbin-app` in `packages/yeetbin-app/`.

## Build and publish: `ktn-repo/.github/workflows/build-package.yml` (workflow_call)

The fork caller triggers on push to `ktn` (publish) and on push to `sync/**` (build only, which is
the promote gate). `paths-ignore` covers docs, `**/*.md` and `packaging/arch/ktn.md`, so a
descriptor-only edit causes no rebuild. The nightly run re-renders the page instead.

1. **pkgver** = `<.ktn-base without v>.<HEAD committer time UTC %Y%m%d%H%M%S>.g<sha7>`.
   Not trilium's `r<count>`: rebase+promote can *lower* the commit count on the same base, while
   cherry-picks always restamp the committer time. A new upstream base outranks both.
2. **Monotonic gate.** In the Arch container, `vercmp <new> <currently published>` must be > 0, or
   the job fails before anything is uploaded. This fails closed, because there is no epoch to recover
   a wedged client with.
3. `git archive HEAD` → source tarball. Render `packaging/arch/PKGBUILD.in` (`@PKGVER@`,
   `@UPSTREAM_VERSION@`). The real compile happens in the PKGBUILD's `build()`, with makedepends
   installed from the PKGBUILD, as ktn-repo already does. `check()` is the gate's test step.
4. `makepkg` in `archlinux:base-devel` as a non-root user. No signing in forks: ktn-repo re-signs
   everything, so forks hold no GPG secret.
5. On `ktn` only: upload `*.pkg.tar.zst` to the fork's `ktn-repo` release (created if missing) and
   delete superseded assets. ktn-repo picks it up on the **next nightly run**. Forks cannot trigger
   ktn-repo with the default token, and a dispatch PAT was deliberately left out.

Per-package specifics:
- **vesktop-ktn**: the PKGBUILD is adapted from the local `~/Projects/vesktop-ptt-pkg`. It installs
  to `/opt/vesktop`, ships the launcher with flags-file support, and adds a desktop entry and icon.
  Makedepends are `nodejs pnpm git`. `check()` runs `pnpm testTypes`.
- **xdg-desktop-portal-wlr-ktn**: a meson build mirroring Arch's PKGBUILD. It **ships
  `/usr/lib/systemd/user/xdg-desktop-portal-wlr.service.d/ktn-persist.conf`**
  (`Environment=XDPW_PERSIST_MODE=transient`). Without that, xdpw issues no restore tokens and the
  patch is inert, so every `[ktn]` user would otherwise need hand setup.

## Sync, promote, retire

- Each fork gets `ktn-upstream-sync.yml` (fork-sync `mode: rebase`, weekly on Monday at 13:00 UTC,
  `tag_pattern: '^v[0-9]+\.[0-9]+\.[0-9]+$'`) and `ktn-promote.yml`, both copied from actual.
- A new tag produces an ntfy ping and a `sync/<tag>` PR. The gate builds it, and Shawn runs
  **ktn promote sync**. That replaces `ktn` and publishes, and `[ktn]` updates on the next nightly
  run. On conflicts, fork-sync stops and pings, and Shawn resolves by hand on the sync branch.
- Manual check: `SYNC_PR_TOKEN` must cover both new forks if it is a selected-repo PAT. Vesktop's
  upstream edits workflow files, which the default token cannot push.
- **Retirement is manual.** A carried commit only drops out silently if upstream applies an
  *identical* patch. #1238 is a conflicted draft and will land changed, so expect a sync conflict.
  That conflict is the cue to check `retire_when`. To retire: switch back to the stock package,
  archive the fork, and remove its `external.txt` line. The page drops it automatically.

## The /arch/ page

- `site/render.py` (Python, markdown-it-py with `html: False`, everything else escaped), two
  templates, and a stylesheet borrowing the landing page's palette.
- Inputs:
  - `ktn.db` from the publish run;
  - `packages/*/ktn.md`;
  - for each `external.txt` repo, `packaging/arch/ktn.md` and `.ktn-base`, read via `gh api` from
    the default branch.
- Output:
  - `/arch/`: setup with copy buttons (the `[ktn]` `pacman.conf` block, key `recv`/`lsign`
    commands), then a card per package (version, relative and absolute build date, summary,
    *pinned* badge, upstream and fork links).
  - `/arch/<pkg>/`: the descriptor body, a facts table (version, build date, upstream base,
    depends/provides/conflicts), `sudo pacman -S <pkg>`, and `retire_when`.
- Jobs in `publish.yml`, **isolated from publishing**:
  - `site` (needs `publish`, GitHub-hosted): renders and uploads an artifact.
  - `deploy-site` (needs `site`, `[self-hosted, ktn]`): unpacks into
    `/opt/services/ktn-arch/releases/<run_id>`, flips a `current` symlink, and keeps the previous
    release for rollback.

  The workflow has no `pull_request` trigger, so untrusted code never reaches the self-hosted
  runner. A site failure cannot affect the pacman repo.
- One-time host change: an nginx `location /arch/` alias to `/opt/services/ktn-arch/current/`,
  next to `/window-runner/`, with the same dotfile deny. Plus a landing card linking to `/arch/`.

## xdpw window-restore patch

- `restore_data` v1 gains an optional `toplevel_identifier` (`s`) key. The v1 parser already skips
  unknown keys, so no version bump is needed.
- `xdpw_wlr_target_from_data` gains a NULL guard on `output_name`. Stock xdpw `strcmp`s NULL when a
  token has no `output_name`. It also gets the request's `type_mask`:
  - an output name restores a MONITOR (requires the MONITOR bit);
  - an identifier restores a toplevel from `ctx->toplevels` (requires the WINDOW bit);
  - no match falls back to the chooser (existing behaviour: a closed or remapped window prompts).
- The Start response emits `toplevel_identifier` for window targets, **including restored
  sessions**, so a restarted capture (Vesktop calls `applyConstraints` right after start, and again
  on quality changes) can chain-restore.
- ext-foreign-toplevel identifiers are unique for each mapped toplevel, survive title changes and are
  invalid after unmap. That is exactly right for `transient` persistence.

## Testing

xdpw (manual, with xdpw `-l INFO` in the journal):
1. A window share shows the chooser once. Follow-up sessions log a restored toplevel.
2. A mid-stream quality change in Vesktop does not prompt.
3. A closed or hidden window, shared again, gets the chooser.
4. Monitor shares still restore (regression).

vesktop-ktn: `testTypes` in `check()`. After install: a socket Start/Stop round trip, plus the
uinput sniper suite (hold, Shift mid-hold, Shift held first, normal key mid-hold, rapid taps).
Pipeline: a `sync/**` push runs the build-only gate. The vercmp gate rejects a non-increasing pkgver.
`render.py` runs locally against the live `ktn.db` before its first deploy.

## Rollout (✋ = stop for Shawn's approval)

1. **xdpw fix locally**: a clone laid out as the future fork, makepkg, install, tests 1–4. ✋
2. **ktn-repo groundwork**: this doc, `build-package.yml`, `site/` (tested locally), yeetbin's
   `ktn.md`. ✋ before pushing.
3. **Forks**: ✋ create both on GitHub, push `ktn`, disable upstream workflows, add callers, first CI
   builds. ✋ before adding them to `external.txt`, which is the first public publish.
4. **Shawn's machine**: install both `-ktn` packages from `[ktn]`. Remove local `vesktop-ptt`, the
   dotfiles xdpw drop-in and `zz-debug.conf`. Re-run the PTT and screen-share tests.
5. **Page**: trilium's `ktn.md` ✋, the nginx alias on ktn ✋, the landing card ✋, then verify
   live.
6. **Later**: after the xdpw patch soaks, draft the upstream PR (refs #170) for Shawn's review.

## Phase 1 results (2026-10-03)

- Window shares prompt once. Sessions 2 and 3 logged `restore_data.toplevel_identifier` and
  restored with no chooser (17:18:34, 17:19:24). Monitor restore did not regress.
- Test 2 as written does not apply, because Vesktop has no mid-share quality control. Its intent
  (a restarted capture chain-restores) is covered: session 3 restored from session 2's re-issued
  token.
- `contrib/ktn/restore-test.py` in the xdpw fork drives xdpw's impl interface directly with
  `restore_data`, with no chooser. Both kinds restore in about 2 ms and re-issue their key
  (`toplevel_identifier` / `output_name`). Use it for regression checks and the upstream PR.

## Follow-ups

### First frame of an idle source waits for damage (pre-existing, not the patch)

After the chooser, Vesktop's Go Live modal waits until the shared source changes, because Chromium
needs a first frame for the thumbnail.
- Window shares waited 15 s and 19 s (2026-10-03 17:18, 17:19), ending when focus moved.
- **Before the patch**, a monitor share waited 10 s (DP-3, 15:14:18.9 to 15:14:28.9), and windows
  about 8 s.
- So any idle source is affected. A busy monitor only looks instant because something on it keeps
  changing.

Evidence the compositor is not at fault: `grim -T <id>` captured idle and hidden windows in
41–96 ms, so sway delivers a session's first frame immediately. The delay is in xdpw's
ext-image-copy path or in the xdpw-to-Chromium PipeWire handoff (format renegotiation spending the
immediate first frame is the leading guess).

Tooling note: xdpw's node has `object.register: false`, so `gst pipewiresrc` cannot attach by
id/serial ("target not found"). A first-frame timing harness needs to go through the portal
frontend's `OpenPipeWireRemote`.

First step for whoever picks this up: check whether xdpw master's August 2026 frame-scheduling
commits ("screencast: Trigger the graph from the wlr-screencopy backend", "Factor out
wlr_frame_done") fix it. If so, the fork inherits the fix at the next upstream release.

Workaround: after picking, make the source change (click into the window, scroll, or move the
cursor onto that monitor).

### Preview chooser (optional)

A dotfiles `chooser_cmd` could show thumbnails instead of a text list. `grim -T <identifier>`
(windows, under 100 ms each) and `grim -o <output>` (monitors) produce the images, and rofi's dmenu
mode can show them as icons. Independent of the first-frame issue above.

## Rollout status (2026-10-03)

Phases 1–5 are done. `[ktn]` carries `triliumnext-ktn-bin`, `yeetbin-app`, `vesktop-ktn` and
`xdg-desktop-portal-wlr-ktn`, and kautiontape.com/arch/ is live and linked from the landing page.

Changes from the plan, and lessons:
- **pkgver uses seconds** (`%Y%m%d%H%M%S`). With minutes, two commits made in the same minute
  ordered by sha, and a local build of an earlier commit sorted above the CI build.
- **build-package.yml fixes from the first real runs**:
  - the upload step needs `GH_REPO`, because `out/` isn't a checkout;
  - the stale-asset prune must tolerate grep matching nothing (`pipefail`);
  - the container hands the workspace back to the runner user, or `actions/checkout`'s post
    step can't clean `.git/config`.
- **Forks inherit upstream's `release: published` workflows.** Our `ktn-repo` pre-release counts
  as published. Bring a new fork up with Actions disabled, push `ktn`, set it as default, enable
  Actions, `gh workflow disable` every upstream workflow, then dispatch `ktn package` by hand. A
  fork whose upstream has no workflows needs its default branch flipped away and back before
  GitHub indexes the new ones.
- **Trilium deploys on any push to `ktn`.** `ktn-build-publish.yml` has no `paths-ignore`, so
  edits to its `ktn.md` need `[skip ci]` or they redeploy the server.
- **G502 sniper → F19** must be written to an *enabled* onboard profile (the mouse runs
  profile 1). libratbag keeps edits to disabled profiles in RAM only. See the comment in
  `sway/config.d/65-ptt` in the dotfiles.

Still open: the first-frame delay and the preview chooser (Follow-ups above), and the upstream
xdpw PR after the patch has soaked.
