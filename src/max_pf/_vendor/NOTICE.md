# Vendored dependencies

Third-party code bundled into `max_pf` to keep PyPI installs free of direct
VCS/URL references. Each package keeps its original license alongside its source.

## fantraxapi

- **Source:** https://github.com/riders994/FantraxAPI (the `@stable` fork)
- **Upstream:** https://github.com/meisnate12/FantraxAPI
- **Pinned commit:** `4f98fa66b2c28505de3f0fa4b274d14feccc7577` (tag `stable`)
- **Version:** 1.0.1 (fork)
- **License:** MIT — see `fantraxapi/LICENSE`
- **Runtime deps:** `requests` (declared in `max_pf`'s dependencies)

Imported as `max_pf._vendor.fantraxapi`. To refresh: re-copy the package source
from the fork at the desired commit, drop `__pycache__`, keep `LICENSE`, and
update the commit hash above. The source is unmodified (all imports are already
package-relative, so no patching is required).
