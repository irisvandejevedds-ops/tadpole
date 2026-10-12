"""Builds the static site for Cloudflare Pages into site/dist:
   index.html + demo/ (sample data) + app/ (real, empty, stored in the browser) + downloads/ (the phone app and the desktop package).
    python site/build.py            (build the phone app first: android/publish.sh or build.sh)"""
import hashlib
import pathlib
import shutil
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SITE, DIST, WEB = ROOT / "site", ROOT / "site/dist", ROOT / "web"
APK = ROOT / "release/tadpole.apk"      # the signed build, kept in the repo by android/publish.sh
WEB_FILES = ["index.html", "app.js", "app.css", "assets.js", "core.js", "md.js", "store.js", "manifest.webmanifest", "icon-192.png", "icon-512.png", "icon-maskable-512.png"]
SKIP_PY = {"importer.py", "vaultimport.py"}      # the author's own vault import tool; not part of the product


def copy_web(dest, config):
    dest.mkdir(parents=True, exist_ok=True)
    for f in WEB_FILES:
        shutil.copyfile(WEB / f, dest / f)
    (dest / "fonts").mkdir(exist_ok=True)
    shutil.copyfile(WEB / "fonts/pixel-console.woff2", dest / "fonts/pixel-console.woff2")
    (dest / "config.js").write_text(config)


def size(p):
    return f"{p.stat().st_size / 1024:.0f} KB"


def main():
    if not APK.exists():
        raise SystemExit("release/tadpole.apk is missing: run android/publish.sh to build and sign it.")
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    copy_web(DIST / "demo", "window.TADPOLE_CONFIG = { demo: true, downloadUrl: '../' };\n")
    copy_web(DIST / "app", "window.TADPOLE_CONFIG = { downloadUrl: '../' };\n")
    (DIST / "downloads").mkdir()
    shutil.copyfile(APK, DIST / "downloads/tadpole.apk")
    # the desktop package
    pkg = DIST / "downloads/tadpole-desktop.zip"
    with zipfile.ZipFile(pkg, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ("start.py", "requirements.txt", "README.txt"):
            z.write(ROOT / "desktop" / f, f"tadpole-desktop/{f}")
        for p in sorted((ROOT / "app/tadpole").rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc" and p.name not in SKIP_PY:
                z.write(p, f"tadpole-desktop/tadpole/{p.relative_to(ROOT / 'app/tadpole')}")
        z.write(APK, "tadpole-desktop/data/apk/tadpole-widget.apk")
    # the landing page
    html = (SITE / "src/index.html").read_text().replace("__APK_INFO__", f"Android 8 or newer, {size(APK)}").replace("__DESKTOP_INFO__", f"Python 3.10+, {size(pkg)}")
    (DIST / "index.html").write_text(html)
    for f in ("site.css", "site.js"):
        shutil.copyfile(SITE / "src" / f, DIST / f)
    for f in ("app.css", "assets.js", "icon-192.png", "icon-512.png"):
        shutil.copyfile(WEB / f, DIST / f)
    (DIST / "fonts").mkdir()
    shutil.copyfile(WEB / "fonts/pixel-console.woff2", DIST / "fonts/pixel-console.woff2")
    csp = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    (DIST / "_headers").write_text(
        f"/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: no-referrer\n  Content-Security-Policy: {csp}\n"
        "/downloads/*.apk\n  Content-Type: application/vnd.android.package-archive\n  Content-Disposition: attachment\n"
        "/downloads/*.zip\n  Content-Disposition: attachment\n")
    sums = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in sorted((DIST / "downloads").iterdir()))
    (DIST / "downloads/SHA256SUMS").write_text(sums)
    print("site built:", DIST)
    for p in sorted(DIST.rglob("*")):
        if p.is_file():
            print(f"  {str(p.relative_to(DIST)):42s}{size(p):>9}")


if __name__ == "__main__":
    main()
