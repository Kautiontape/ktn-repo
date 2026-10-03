#!/usr/bin/env python3
"""Render the kautiontape.com/arch/ pages from the [ktn] index and package descriptors.

Nothing here is edited by hand per package: versions, build dates and dependencies come
from ktn.db, and the prose comes from each package's own ktn.md (see
docs/design/2026-10-03-ktn-fork-packages.md).

usage: render.py --db ktn.db.tar.gz --descriptors DIR --out DIR

DIR holds one subdirectory per descriptor: <any>/ktn.md, plus <any>/.ktn-base when the
package is a fork. A package without a descriptor still gets a card from its pkgdesc,
and a broken descriptor is reported and skipped, never fatal.
"""
import argparse
import html
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from string import Template

from markdown_it import MarkdownIt

HERE = Path(__file__).resolve().parent

# The repo's identity. Changing the signing key or the release URL means editing these.
REPO_SECTION = "ktn"
SERVER = "https://github.com/Kautiontape/ktn-repo/releases/download/repo"
KEY = "36EF1180D7CBA87C0C0F8CBCE480A935E543D3C8"
REPO_URL = "https://github.com/Kautiontape/ktn-repo"

md = MarkdownIt("commonmark", {"html": False})
esc = html.escape


def warn(msg):
    print(f"render: warning: {msg}", file=sys.stderr)


LIST_FIELDS = {"DEPENDS", "MAKEDEPENDS", "PROVIDES", "CONFLICTS", "REPLACES",
               "OPTDEPENDS", "LICENSE"}


def read_db(path):
    """Parse a pacman repo db into {pkgname: {FIELD: str | list}}."""
    pkgs = {}
    with tarfile.open(path) as tar:
        for member in tar.getmembers():
            if not member.name.endswith("/desc"):
                continue
            handle = tar.extractfile(member)
            if handle is None:
                continue
            fields, key = {}, None
            for line in handle.read().decode().splitlines():
                if line.startswith("%") and line.endswith("%"):
                    key = line.strip("%")
                    fields[key] = []
                elif line and key:
                    fields[key].append(line)
            entry = {k: (v[0] if len(v) == 1 and k not in LIST_FIELDS else v)
                     for k, v in fields.items()}
            pkgs[entry["NAME"]] = entry
    return pkgs


def read_descriptor(path):
    """Split ktn.md into (frontmatter dict, markdown body). Raises ValueError if malformed."""
    text = path.read_text()
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("no frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise ValueError("unterminated frontmatter") from None
    meta = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"bad frontmatter line: {line!r}")
        meta[key.strip()] = value.strip()
    if "package" not in meta:
        raise ValueError("frontmatter has no package:")
    return meta, "\n".join(lines[end + 1:]).strip()


def load_descriptors(root):
    """Read <dir>/ktn.md, <dir>/.ktn-base and <dir>/.updated for every subdirectory.

    The package is the descriptor's `package:` field, or the directory name when there is
    no (valid) ktn.md, so a package can carry .updated without a descriptor.
    """
    found = {}
    for d in sorted(p for p in Path(root).iterdir() if p.is_dir()):
        meta, body = {}, ""
        if (d / "ktn.md").exists():
            try:
                meta, body = read_descriptor(d / "ktn.md")
            except (ValueError, OSError, UnicodeDecodeError) as e:
                warn(f"{d / 'ktn.md'}: {e}; falling back to pkgdesc")
        for key, file in (("_base", ".ktn-base"), ("_updated", ".updated")):
            if (d / file).exists():
                meta[key] = (d / file).read_text().strip()
        found[meta.get("package", d.name)] = (meta, body)
    return found


def updated(entry, meta):
    """When the package last changed: .updated (git date of a centrally built PKGBUILD,
    which ktn-repo rebuilds nightly with the same version) or the package's build date."""
    if meta.get("_updated"):
        try:
            return datetime.fromisoformat(meta["_updated"]).astimezone(timezone.utc)
        except ValueError:
            warn(f"{entry['NAME']}: unparseable .updated {meta['_updated']!r}")
    return datetime.fromtimestamp(int(entry.get("BUILDDATE", "0") or 0), timezone.utc)


def when(entry, meta):
    dt = updated(entry, meta)
    return f'<time datetime="{dt.isoformat()}" data-rel>{dt:%Y-%m-%d}</time>'


def inline(text):
    """Summaries may use inline markdown such as `code`; raw HTML stays disabled."""
    return md.renderInline(text)


def link(url, text=None):
    if not url:
        return ""
    if not url.startswith(("https://", "http://")):
        return esc(text or url)  # never emit javascript: or other schemes as links
    return f'<a href="{esc(url)}">{esc(text or url)}</a>'


def listing(values):
    if not values:
        return "—"
    if isinstance(values, str):
        values = [values]
    return ", ".join(f"<code>{esc(v)}</code>" for v in values)


def render(template, **values):
    return Template((HERE / "templates" / template).read_text()).substitute(values)


def card(name, entry, meta):
    summary = meta.get("summary") or entry.get("DESC", "")
    badge = '<span class="badge">pinned</span>' if meta.get("pinned") else ""
    return f"""<a class="card" href="{esc(name)}/">
  <div class="card-top"><span class="card-name">{esc(name)}</span>{badge}</div>
  <div class="card-desc">{inline(summary)}</div>
  <div class="card-meta"><code>{esc(entry["VERSION"])}</code> · updated {when(entry, meta)}</div>
</a>"""


def package_page(name, entry, meta, body):
    facts = [
        ("Version", f"<code>{esc(entry['VERSION'])}</code>"),
        ("Updated", when(entry, meta)),
    ]
    if meta.get("_base"):
        facts.append(("Upstream base", f"<code>{esc(meta['_base'])}</code>"))
    if meta.get("pinned"):
        facts.append(("Pinned", esc(meta["pinned"])))
    if meta.get("upstream"):
        facts.append(("Upstream", link(meta["upstream"])))
    if entry.get("URL"):
        facts.append(("Source", link(entry["URL"])))
    facts += [
        ("Provides", listing(entry.get("PROVIDES"))),
        ("Conflicts", listing(entry.get("CONFLICTS"))),
        ("Depends", listing(entry.get("DEPENDS"))),
    ]
    if meta.get("retire_when"):
        facts.append(("Retire when", esc(meta["retire_when"])))
    rows = "\n".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in facts)
    summary = meta.get("summary") or entry.get("DESC", "")
    return render("package.html", name=esc(name), summary=inline(summary),
                  meta_summary=esc(summary.replace("`", "")), facts=rows,
                  install=esc(f"sudo pacman -S {REPO_SECTION}/{name}"),
                  body=md.render(body) if body else f"<p>{esc(entry.get('DESC', ''))}</p>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--descriptors", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pkgs = read_db(args.db)
    if not pkgs:
        sys.exit("render: the database lists no packages; refusing to publish an empty page")
    descriptors = load_descriptors(args.descriptors)
    for orphan in sorted(set(descriptors) - set(pkgs)):
        warn(f"descriptor for {orphan} but no such package in the index")

    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copy(HERE / "static" / "style.css", out / "style.css")

    cards = []
    for name in sorted(pkgs):
        meta, body = descriptors.get(name, ({}, ""))
        cards.append(card(name, pkgs[name], meta))
        (out / name).mkdir()
        (out / name / "index.html").write_text(package_page(name, pkgs[name], meta, body))

    conf = f"[{REPO_SECTION}]\nSigLevel = Required\nServer = {SERVER}"
    keys = f"sudo pacman-key --recv-keys {KEY}\nsudo pacman-key --lsign-key {KEY}\nsudo pacman -Sy"
    (out / "index.html").write_text(render(
        "index.html", conf=esc(conf), keys=esc(keys), key=esc(KEY), cards="\n".join(cards),
        count=len(pkgs), repo=esc(REPO_URL)))
    print(f"render: wrote {len(pkgs)} package page(s) to {out}")


if __name__ == "__main__":
    main()
