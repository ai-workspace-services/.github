#!/usr/bin/env bash
set -euo pipefail

# Public self-hosted control-plane contract only: deployment is performed by the reviewed
# SSH -> Playbook -> fixed GitOps -> Doco-CD path.
# This script does not create DNS, expose PostgreSQL, or accept secrets.

ENVIRONMENT="${ENV:-sit}"
DEPLOYMENT_ID="${DEPLOYMENT_ID:-v4}"
DOMAIN_BASE="${DOMAIN_BASE:?DOMAIN_BASE is required, for example svc.plus}"

case "$ENVIRONMENT" in
  sit|uat) ;;
  *) echo "ENV must be sit or uat" >&2; exit 2 ;;
esac

valid_label='^[a-z0-9]+([.-][a-z0-9]+)*$'
valid_id='^[a-z0-9]+(-[a-z0-9]+)*$'
[[ "$DEPLOYMENT_ID" =~ $valid_id ]] || { echo "DEPLOYMENT_ID is invalid" >&2; exit 2; }
[[ "$DOMAIN_BASE" =~ $valid_label ]] || { echo "DOMAIN_BASE is invalid" >&2; exit 2; }

for service in console accounts billing postgresql; do
  printf '%s-%s-%s.%s\n' "$service" "$ENVIRONMENT" "$DEPLOYMENT_ID" "$DOMAIN_BASE"
done

cat <<'EOF'

Next steps are intentionally explicit:
  1. Review the fixed IaC/GitOps manifest and SSH identity.
  2. Run the reviewed Playbook in check mode.
  3. Apply through SSH -> Playbook -> fixed GitOps -> Doco-CD.
  4. Keep PostgreSQL tunnel-only; do not create a public database listener.

This entrypoint does not deploy a proxy node. For a proxy node use setup-proxy.sh
with a fixed reviewed release and the node-specific credential contract.
EOF
