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
sudo pacman-key --recv-keys C20F8574816A1B67C81E6F829DA4E0459723DB07
sudo pacman-key --lsign-key C20F8574816A1B67C81E6F829DA4E0459723DB07
sudo pacman -Sy
```

## Packages

| Package | Source | Built |
|---|---|---|
| `yeetbin-app` | [yeetbin-app](https://github.com/Kautiontape/yeetbin-app) | here, from the tagged tarball |
| `triliumnext-ktn-bin` | [trilium](https://github.com/Kautiontape/trilium) | in that repo, pulled in prebuilt |

Anything in `packages/<name>/PKGBUILD` is built here. Anything listed in `external.txt` is
downloaded already-built and already-signed, for projects whose build toolchain lives
elsewhere — trilium needs its Electron pipeline, so duplicating that here would be
pointless.

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

Built elsewhere: append `<owner/repo> <release-tag>` to `external.txt`. The release must
carry `*.pkg.tar.zst` and matching `.sig` files signed by the same key.

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

Both hold the `Shawn Squire (ktn repo)` key (`C20F8574816A1B67C81E6F829DA4E0459723DB07`),
the same one that signs the existing packages:

```sh
gpg --export-secret-keys --armor C20F8574816A1B67C81E6F829DA4E0459723DB07 \
  | gh secret set ARCH_REPO_GPG_KEY --repo Kautiontape/ktn-repo

gh secret set ARCH_REPO_GPG_PASSPHRASE --repo Kautiontape/ktn-repo
```

## Notes

- Packages are built in `archlinux:base-devel`, not on the Ubuntu runner, so they link
  against Arch's glibc.
- `check()` runs during the build, so a failing test suite fails the publish.
- `SigLevel = Required` covers the database as well as the packages, so all four database
  files are signed.
