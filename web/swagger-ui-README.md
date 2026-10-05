# Vendored Swagger UI assets

These browser assets are copied from the official `swagger-api/swagger-ui`
repository at tag `v5.33.1` (released 2026-10-01). They are served locally;
the panel does not load documentation scripts or styles from a CDN.

Source: <https://github.com/swagger-api/swagger-ui/tree/v5.33.1/dist>
License: Apache-2.0, reproduced in `swagger-ui-LICENSE.txt`.

SHA-256:

| File | SHA-256 |
|---|---|
| `swagger-ui-bundle.js` | `050bc415ee7048dcd881682678f720264e7da5e373f7461d7c58c755305255f7` |
| `swagger-ui-standalone-preset.js` | `5243d492e14505e0cab87ac8b0195d0e615943e651743b2b698450a46eb470be` |
| `swagger-ui.css` | `1ac324f7dcd27e4b9386b4bd6421271ec147e922a22c05ba24b115e9aa6321` |

The local `api-docs.js` initializer disables “Try it out”; the interface is
for viewing the contract and cannot submit API operations.
