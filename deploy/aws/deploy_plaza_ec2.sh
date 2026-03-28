#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-$(aws configure get region 2>/dev/null || true)}}"
REGION="${REGION:-us-east-1}"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"

APP_NAME="${PLAZA_APP_NAME:-finmas-plaza}"
INSTANCE_NAME="${PLAZA_INSTANCE_NAME:-finmas-plaza}"
INSTANCE_TYPE="${PLAZA_INSTANCE_TYPE:-t3.micro}"
APP_PORT="${PLAZA_PORT:-8000}"
S3_BUCKET="${PLAZA_BUNDLE_BUCKET:-${APP_NAME}-deploy-${ACCOUNT_ID}-${REGION}}"
SECURITY_GROUP_NAME="${PLAZA_SECURITY_GROUP_NAME:-${APP_NAME}-sg}"

ENV_FILE="${ROOT_DIR}/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}" >&2
  exit 1
fi

read_env_value() {
  local key="$1"
  awk -F= -v lookup_key="${key}" '$1 == lookup_key {sub(/^[^=]*=/,""); print; exit}' "${ENV_FILE}"
}

SUPABASE_URL="${PLAZA_SUPABASE_URL:-$(read_env_value PLAZA_SUPABASE_URL)}"
SUPABASE_URL="${SUPABASE_URL:-$(read_env_value SUPABASE_URL)}"

SUPABASE_SERVICE_ROLE_KEY="${PLAZA_SUPABASE_SERVICE_ROLE_KEY:-$(read_env_value PLAZA_SUPABASE_SERVICE_ROLE_KEY)}"
SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-$(read_env_value SUPABASE_SERVICE_ROLE_KEY)}"
if [[ -z "${SUPABASE_SERVICE_ROLE_KEY}" ]]; then
  echo "SUPABASE_SERVICE_ROLE_KEY is missing from ${ENV_FILE}" >&2
  exit 1
fi

SUPABASE_PUBLISHABLE_KEY="${PLAZA_SUPABASE_PUBLISHABLE_KEY:-$(read_env_value PLAZA_SUPABASE_PUBLISHABLE_KEY)}"
SUPABASE_PUBLISHABLE_KEY="${SUPABASE_PUBLISHABLE_KEY:-$(read_env_value SUPABASE_PUBLISHABLE_KEY)}"

AMI_ID="$(aws ssm get-parameter \
  --region "${REGION}" \
  --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --query 'Parameter.Value' \
  --output text)"

echo "Using region ${REGION}, account ${ACCOUNT_ID}, and AMI ${AMI_ID}"

VPC_ID="$(aws ec2 describe-vpcs \
  --region "${REGION}" \
  --filters Name=isDefault,Values=true \
  --query 'Vpcs[0].VpcId' \
  --output text)"

if [[ -z "${VPC_ID}" || "${VPC_ID}" == "None" ]]; then
  echo "No default VPC found in ${REGION}" >&2
  exit 1
fi

SUBNET_ID="$(aws ec2 describe-subnets \
  --region "${REGION}" \
  --filters Name=default-for-az,Values=true Name=vpc-id,Values="${VPC_ID}" \
  --query 'Subnets[0].SubnetId' \
  --output text)"

if [[ -z "${SUBNET_ID}" || "${SUBNET_ID}" == "None" ]]; then
  echo "No default subnet found in ${REGION}" >&2
  exit 1
fi

echo "Using VPC ${VPC_ID} and subnet ${SUBNET_ID}"

STAGING_DIR="$(mktemp -d)"
BUNDLE_ZIP="/tmp/${APP_NAME}-$(date +%Y%m%d%H%M%S).zip"
cleanup() {
  rm -rf "${STAGING_DIR}"
  rm -f "${BUNDLE_ZIP}" /tmp/"${APP_NAME}"-user-data.sh
}
trap cleanup EXIT

mkdir -p "${STAGING_DIR}"
cp -R "${ROOT_DIR}/attas" "${STAGING_DIR}/attas"
cp -R "${ROOT_DIR}/prompits" "${STAGING_DIR}/prompits"
cp -R "${ROOT_DIR}/phemacast" "${STAGING_DIR}/phemacast"
cp "${ROOT_DIR}/requirements.txt" "${STAGING_DIR}/requirements.txt"

(
  cd "${STAGING_DIR}"
  zip -qr "${BUNDLE_ZIP}" .
)

echo "Created deployment bundle ${BUNDLE_ZIP}"

if ! aws s3api head-bucket --region "${REGION}" --bucket "${S3_BUCKET}" >/dev/null 2>&1; then
  if [[ "${REGION}" == "us-east-1" ]]; then
    aws s3api create-bucket --region "${REGION}" --bucket "${S3_BUCKET}" >/dev/null
  else
    aws s3api create-bucket \
      --region "${REGION}" \
      --bucket "${S3_BUCKET}" \
      --create-bucket-configuration "LocationConstraint=${REGION}" >/dev/null
  fi
fi

BUNDLE_KEY="plaza/${INSTANCE_NAME}/bundle-$(date +%Y%m%d%H%M%S).zip"
aws s3 cp "${BUNDLE_ZIP}" "s3://${S3_BUCKET}/${BUNDLE_KEY}" --region "${REGION}" >/dev/null

PRESIGNED_URL="$(aws s3 presign "s3://${S3_BUCKET}/${BUNDLE_KEY}" --region "${REGION}" --expires-in 86400)"

echo "Uploaded bundle to s3://${S3_BUCKET}/${BUNDLE_KEY}"

SECURITY_GROUP_ID="$(aws ec2 describe-security-groups \
  --region "${REGION}" \
  --filters Name=group-name,Values="${SECURITY_GROUP_NAME}" Name=vpc-id,Values="${VPC_ID}" \
  --query 'SecurityGroups[0].GroupId' \
  --output text)"

if [[ -z "${SECURITY_GROUP_ID}" || "${SECURITY_GROUP_ID}" == "None" ]]; then
  SECURITY_GROUP_ID="$(aws ec2 create-security-group \
    --region "${REGION}" \
    --group-name "${SECURITY_GROUP_NAME}" \
    --description "Public access for ${INSTANCE_NAME}" \
    --vpc-id "${VPC_ID}" \
    --query 'GroupId' \
    --output text)"
fi

echo "Using security group ${SECURITY_GROUP_ID}"

aws ec2 authorize-security-group-ingress \
  --region "${REGION}" \
  --group-id "${SECURITY_GROUP_ID}" \
  --ip-permissions "[{\"IpProtocol\":\"tcp\",\"FromPort\":${APP_PORT},\"ToPort\":${APP_PORT},\"IpRanges\":[{\"CidrIp\":\"0.0.0.0/0\",\"Description\":\"Public Plaza HTTP\"}]}]" \
  >/dev/null 2>&1 || true

read -r ALLOCATION_ID PUBLIC_IP <<<"$(aws ec2 allocate-address \
  --region "${REGION}" \
  --domain vpc \
  --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=${INSTANCE_NAME}-eip}]" \
  --query '[AllocationId,PublicIp]' \
  --output text)"

PUBLIC_URL="http://${PUBLIC_IP}:${APP_PORT}"
SECRET_B64="$(printf '%s' "${SUPABASE_SERVICE_ROLE_KEY}" | base64 | tr -d '\n')"
PUBLISHABLE_B64="$(printf '%s' "${SUPABASE_PUBLISHABLE_KEY}" | base64 | tr -d '\n')"

echo "Allocated Elastic IP ${PUBLIC_IP}"

USER_DATA_FILE="/tmp/${APP_NAME}-user-data.sh"
cat >"${USER_DATA_FILE}" <<EOF
#!/bin/bash
set -euo pipefail

dnf update -y
dnf install -y python3.11 python3.11-pip unzip

mkdir -p /opt/finmas /etc/finmas
curl -fsSL "${PRESIGNED_URL}" -o /opt/finmas/bundle.zip
rm -rf /opt/finmas/app
mkdir -p /opt/finmas/app
unzip -q /opt/finmas/bundle.zip -d /opt/finmas/app

python3.11 -m venv /opt/finmas/venv
/opt/finmas/venv/bin/pip install --upgrade pip
/opt/finmas/venv/bin/pip install -r /opt/finmas/app/requirements.txt

cat >/etc/finmas/plaza.env <<'ENVEOF'
PROMPITS_AGENT_CONFIG=/opt/finmas/app/attas/configs/plaza.agent
PROMPITS_BIND_HOST=0.0.0.0
PROMPITS_PORT=${APP_PORT}
PROMPITS_PUBLIC_URL=${PUBLIC_URL}
SUPABASE_URL=${SUPABASE_URL}
SUPABASE_SERVICE_ROLE_KEY_B64=${SECRET_B64}
SUPABASE_PUBLISHABLE_KEY_B64=${PUBLISHABLE_B64}
ENVEOF

cat >/usr/local/bin/finmas-plaza-start <<'STARTEOF'
#!/bin/bash
set -euo pipefail
source /etc/finmas/plaza.env
export PROMPITS_AGENT_CONFIG PROMPITS_BIND_HOST PROMPITS_PORT PROMPITS_PUBLIC_URL SUPABASE_URL
export SUPABASE_SERVICE_ROLE_KEY="\$(printf '%s' "\${SUPABASE_SERVICE_ROLE_KEY_B64}" | base64 -d)"
if [[ -n "\${SUPABASE_PUBLISHABLE_KEY_B64:-}" ]]; then
  export SUPABASE_PUBLISHABLE_KEY="\$(printf '%s' "\${SUPABASE_PUBLISHABLE_KEY_B64}" | base64 -d)"
fi
unset SUPABASE_SERVICE_ROLE_KEY_B64
unset SUPABASE_PUBLISHABLE_KEY_B64
cd /opt/finmas/app
exec /opt/finmas/venv/bin/gunicorn \
  -k uvicorn.workers.UvicornWorker \
  --workers 1 \
  --bind 0.0.0.0:${APP_PORT} \
  prompits.asgi:app
STARTEOF
chmod +x /usr/local/bin/finmas-plaza-start

cat >/etc/systemd/system/finmas-plaza.service <<'SERVICEEOF'
[Unit]
Description=FinMAS Plaza Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/finmas-plaza-start
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable --now finmas-plaza.service
EOF

INSTANCE_ID="$(aws ec2 run-instances \
  --region "${REGION}" \
  --image-id "${AMI_ID}" \
  --instance-type "${INSTANCE_TYPE}" \
  --subnet-id "${SUBNET_ID}" \
  --security-group-ids "${SECURITY_GROUP_ID}" \
  --associate-public-ip-address \
  --user-data "file://${USER_DATA_FILE}" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${INSTANCE_NAME}}]" \
  --query 'Instances[0].InstanceId' \
  --output text)"

aws ec2 wait instance-running --region "${REGION}" --instance-ids "${INSTANCE_ID}"

aws ec2 associate-address \
  --region "${REGION}" \
  --instance-id "${INSTANCE_ID}" \
  --allocation-id "${ALLOCATION_ID}" >/dev/null

echo "Launched instance ${INSTANCE_ID} with Plaza URL ${PUBLIC_URL}"

for attempt in $(seq 1 40); do
  if curl -fsS "${PUBLIC_URL}/health" >/dev/null 2>&1; then
    echo "Health check passed at ${PUBLIC_URL}/health"
    echo "INSTANCE_ID=${INSTANCE_ID}"
    echo "PUBLIC_IP=${PUBLIC_IP}"
    echo "PUBLIC_URL=${PUBLIC_URL}"
    exit 0
  fi
  sleep 15
done

echo "Plaza did not become healthy in time. Check instance ${INSTANCE_ID} in ${REGION}." >&2
echo "PUBLIC_URL=${PUBLIC_URL}" >&2
exit 1
