# ktn-repo

The signed pacman repository behind `[ktn]`. One database for every Kautiontape package,
published to the `repo` release tag by `.github/workflows/publish.yml`.

## Client setup

In `/etc/pacman.conf`:

```ini
[ktn]
SigLevel = Required
Server = https://github.com/Kautiontape/ktn-repo/releases/download/repo
```

Trust the signing key, then sync:

```sh
sudo pacman-key --recv-keys 36EF1180D7CBA87C0C0F8CBCE480A935E543D3C8
sudo pacman-key --lsign-key 36EF1180D7CBA87C0C0F8CBCE480A935E543D3C8
sudo pacman -Sy
```

## Packages

| Package | Source | Built |
|---|---|---|
| `yeetbin-app` | [yeetbin-app](https://github.com/Kautiontape/yeetbin-app) | here, from the tagged tarball |
| `triliumnext-ktn-bin` | [trilium](https://github.com/Kautiontape/trilium) | in that repo, pulled in prebuilt |

Anything in `packages/<name>/PKGBUILD` is built here. Anything in `external.txt` is
downloaded already built, for projects whose toolchain lives elsewhere — trilium needs its
Electron pipeline, so duplicating that here would be pointless.

Every package is re-signed with this repo's key, upstream signatures discarded, so clients
trust exactly one key no matter where a package was built.

Declared `depends`/`makedepends` are installed automatically, so adding a package needs no
workflow change.

## Why one repository

`repo-add` rewrites the whole database. Two workflows in different GitHub repos cannot be
serialised against each other, so if each published its own entry into a shared database,
whichever ran last would publish an index containing only its own package.

Keeping the index in one repo makes `concurrency: group: publish` a real lock, and clients
need exactly one `pacman.conf` section no matter how many packages get added.

## Adding a package

Built here:

```sh
mkdir -p packages/<name> && $EDITOR packages/<name>/PKGBUILD
```

Set `options=('!debug')` for compiled languages, or makepkg splits a second `-debug`
package. Then commit — pushing to `main` publishes.

Built elsewhere: append `<owner/repo> <release-tag>` to `external.txt`. The release only
needs the `*.pkg.tar.zst` files. They're downloaded and re-signed here, so their own
signatures, if any, are ignored.

Every package should carry a `ktn.md` descriptor (next to its PKGBUILD here, or at
`packaging/arch/ktn.md` in a fork); see [The /arch/ page](#the-arch-page).

## Fork packages

A Kautiontape fork of someone else's project (vesktop, xdg-desktop-portal-wlr) follows one
contract, written up in `docs/design/2026-10-03-ktn-fork-packages.md`:

- `ktn` is the deploy branch: an upstream release tag (or a pinned upstream commit) plus a
  few carried commits. `.ktn-base` names that tag.
- `packaging/arch/PKGBUILD.in` builds from `ktn-src.tar.gz`, a `git archive` of the branch.
  `@PKGVER@` and `@UPSTREAM_VERSION@` are filled in by `scripts/build-package.sh`.
- `packaging/arch/ktn.md` is the package's page.
- `.github/workflows/ktn-package.yml` calls this repo's reusable build:

  ```yaml
  name: ktn package
  on:
    push:
      branches: [ktn, 'sync/**']
      paths-ignore: ['**/*.md', 'docs/**']
    workflow_dispatch:
  concurrency:
    group: ktn-package-${{ github.ref }}
    cancel-in-progress: true
  permissions:
    contents: write
  jobs:
    package:
      uses: Kautiontape/ktn-repo/.github/workflows/build-package.yml@main
      with:
        publish: ${{ github.ref == 'refs/heads/ktn' }}
  ```

  A push to `ktn` builds and uploads to the fork's `ktn-repo` release. A push to `sync/**`
  only builds, which is the check fork-sync's promote waits for. The build refuses to
  publish a pkgver that doesn't sort above the one already released.
- Upstream tracking is fork-sync in rebase mode (`ktn-upstream-sync.yml` plus
  `ktn-promote.yml`, as in Kautiontape/actual).

To build a fork locally on an Arch machine:

```sh
scripts/build-package.sh --syncdeps ~/Projects/<fork> /tmp/out
```

## The /arch/ page

`kautiontape.com/arch/` is rendered by the `site` job after every publish, including the
nightly run, and deployed to `/opt/services/ktn-arch` on ktn by `deploy-site`. Nothing
there is edited by hand:

- versions, dependencies and build dates come from `ktn.db`;
- each package's prose comes from its `ktn.md`. Frontmatter fields are `package`,
  `summary`, `upstream`, and optionally `pinned` and `retire_when`, followed by the
  markdown body;
- for packages built here, "updated" is the last commit to their PKGBUILD, because the
  nightly run rebuilds them with an unchanged version.

A package without a `ktn.md` still gets a card from its `pkgdesc`. To preview locally:

```sh
gh release download repo -p ktn.db.tar.gz -D /tmp/site
mkdir -p /tmp/site/desc/yeetbin-app && cp packages/yeetbin-app/ktn.md /tmp/site/desc/yeetbin-app/
python3 site/render.py --db /tmp/site/ktn.db.tar.gz --descriptors /tmp/site/desc --out /tmp/site/out
```

## Releasing an update

For `yeetbin-app`, tag the app repo, then bump `pkgver` here:

```sh
cd packages/yeetbin-app
sed -i 's/^pkgver=.*/pkgver=0.2.0/; s/^pkgrel=.*/pkgrel=1/' PKGBUILD
updpkgsums
git commit -am "yeetbin-app 0.2.0" && git push
```

External packages are picked up by the nightly run, or immediately with:

```sh
gh workflow run publish --repo Kautiontape/ktn-repo
```

To have a project repo trigger this on release, give it a PAT with `contents:write` here and
send a `repository_dispatch` of type `package-updated`.

## Secrets

One secret: `ARCH_REPO_GPG_KEY`, holding the `Shawn Squire (ktn repo 2026-07-30)` key
(`36EF1180D7CBA87C0C0F8CBCE480A935E543D3C8`). The key has no passphrase, so there is
nothing else to store and nothing to lose.

```sh
gpg --export-secret-keys --armor 36EF1180D7CBA87C0C0F8CBCE480A935E543D3C8 \
  | gh secret set ARCH_REPO_GPG_KEY --repo Kautiontape/ktn-repo
```

The workflow rejects a key that is empty or not a PGP block, and test-signs immediately
after import, so a bad secret fails in seconds.

## Notes

- Packages are built in `archlinux:base-devel`, not on the Ubuntu runner, so they link
  against Arch's glibc.
- `check()` runs during the build, so a failing test suite fails the publish.
- `SigLevel = Required` covers the database as well as the packages, so all four database
  files are signed.
