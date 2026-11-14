# Third-party material

This project analyzes data and code from **ComposioHQ/composio** (MIT License,
Copyright (c) 2025 Sampark Inc.). It is an independent project and is not
affiliated with or endorsed by Composio.

- Source analyzed: https://github.com/ComposioHQ/composio at commit
  `6aa3f31ecf38fc5f9ea10d67e31a43ede2e2c693` (branch `next`, 2026-11-13).
- Fixtures used as input (read-only, not redistributed here; fetch them from the commit above):
  - `ts/packages/cli/test/__mocks__/tools.json` (git blob `b28f3c96499276f5ee0bfde7fc2c8e8021fb45a3`)
  - `docs/public/data/toolkits.json` (git blob `6a81b753b2679cddae499cdd0019a4c89c4afbe6`)
- Saved evidence under `tool-schema-doctor/out/` contains short excerpts of that data
  (tool names, descriptions and schema fragments) produced by running this project's CLI.
- The CLI imports the installed Composio provider packages and calls their own `wrap_tool`;
  it does not copy their code.

Composio's license text: https://github.com/ComposioHQ/composio/blob/next/LICENSE
