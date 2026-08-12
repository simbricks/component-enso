# Vendored Ensō behavioral model

The C++ sources in this directory are vendored, not written here. Keep this file
in sync whenever they are re-synced or patched.

## Origin

| | |
|---|---|
| Upstream | <https://github.com/hsadok/simbricks> |
| Branch | `enso_bm` (head of [simbricks/simbricks#138](https://github.com/simbricks/simbricks/pull/138)) |
| Commit | `c53364fb6` — *"Update to new simbricks"*, 2025-08-06 |
| Path | `sims/nic/enso_bm/` |
| Author | Hugo Sadok |

Vendored files: `enso_bm.cc`, `enso_bm.h`, `enso_config.h`, `enso_helpers.h`,
`headers.h`, `logger.cc`. Their original copyright headers are kept verbatim.

`CPPLINT.cfg` and `Makefile` are ours; upstream's `rules.mk` was dropped along
with the monorepo build system it belonged to.


## Local modifications

Only the include paths, so re-syncing stays mechanical. Upstream compiled from
the monorepo root, so its quoted includes were repo-relative (8 lines):

- `"sims/nic/enso_bm/<x>.h"` → `"<x>.h"` in `enso_bm.h` (×2), `enso_bm.cc` (×3)
  and `logger.cc` (×1) — they are now siblings.
- `"lib/simbricks/nicbm/multinic.h"` → `<simbricks/nicbm/multinic.h>` in
  `enso_bm.cc`. Angle brackets are required: the header is consumed from
  `$SIMBRICKS_INC_DIR/simbricks/nicbm/` and itself includes
  `<simbricks/nicbm/nicbm.h>`.

`<simbricks/pcie/proto.h>` and `<simbricks/nicbm/nicbm.h>` already used the
installed-header form and are unchanged.

No changes were made to the device model's behaviour.
