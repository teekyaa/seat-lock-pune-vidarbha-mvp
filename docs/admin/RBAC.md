# Admin permission matrix

Generated from `api/apps/admin_dashboard/permissions.py`. A permission does not imply the feature is implemented.

| Permission | SUPER_ADMIN | OPS_ADMIN | SUPPORT_AGENT | FINANCE_ADMIN | TRUST_SAFETY | VIEWER |
| --- | --- | --- | --- | --- | --- | --- |
| `session:read` | yes | yes | yes | yes | yes | yes |
| `session:logout` | yes | yes | yes | yes | yes | yes |
| `session:reauthenticate` | yes | yes | yes | yes | yes | yes |
| `overview:read` | yes | yes | yes | yes | yes | yes |
| `users:read` | yes | yes | yes | — | yes | yes |
| `users:reveal_pii` | yes | — | — | — | — | — |
| `users:warn` | yes | — | yes | — | yes | — |
| `users:notes` | yes | — | yes | — | yes | — |
| `users:suspend` | yes | — | — | — | yes | — |
| `users:ban` | yes | — | — | — | yes | — |
| `users:verify` | yes | yes | — | — | — | — |
| `rides:read` | yes | yes | yes | — | — | yes |
| `rides:cancel` | yes | yes | — | — | — | — |
| `seat_locks:read` | yes | yes | yes | — | — | yes |
| `seat_locks:release` | yes | yes | — | — | — | — |
| `seat_locks:extend` | yes | yes | — | — | — | — |
| `payments:read` | yes | yes | — | yes | — | yes |
| `refunds:create` | yes | — | — | yes | — | — |
| `payouts:hold` | yes | — | — | yes | — | — |
| `reconciliation:run` | yes | — | — | yes | — | — |
| `tickets:read` | yes | yes | yes | — | yes | yes |
| `tickets:assign` | yes | yes | yes | — | yes | — |
| `tickets:resolve` | yes | yes | yes | — | — | — |
| `tickets:escalate` | yes | yes | yes | — | yes | — |
| `tickets:reply` | yes | yes | yes | — | — | — |
| `tickets:note` | yes | yes | yes | — | — | — |
| `flags:read` | yes | yes | — | — | yes | yes |
| `flags:review` | yes | — | — | — | yes | — |
| `risk_rules:manage` | yes | — | — | — | yes | — |
| `feature_flags:read` | yes | yes | yes | yes | yes | yes |
| `feature_flags:toggle` | yes | yes | — | — | — | — |
| `feature_flags:toggle_critical` | yes | — | — | — | — | — |
| `audit_logs:read` | yes | — | — | — | — | — |
| `system_logs:read` | yes | — | — | — | — | — |
| `admins:manage` | yes | — | — | — | — | — |
| `settings:manage` | yes | — | — | — | — | — |
| `exports:create` | yes | — | — | — | — | — |
| `alerts:acknowledge` | yes | yes | — | — | — | — |
