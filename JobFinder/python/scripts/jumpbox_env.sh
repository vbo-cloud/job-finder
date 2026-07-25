#!/usr/bin/env bash
# Source this file each time you start a new jumpbox session, to load the environment variables
# the diagnostic scripts in this directory need:
#
#   source jumpbox_env.sh
#   # or:
#   . jumpbox_env.sh
#
# Do NOT run it as ./jumpbox_env.sh or bash jumpbox_env.sh — the exported variables would only
# exist in that throwaway subshell and vanish the instant the script exits. `source`/`.` runs it
# in your CURRENT shell instead of a subshell, which is what makes the exports stick around for
# the commands you type next.
#
# Requires: already logged in via `az login` on the jumpbox (or the VM's managed identity has Key
# Vault read access) with permission to read secrets from kv-jf-dev-frc. No API key secret to
# fetch here anymore (Managed Identity flip) — any future script that calls Azure OpenAI directly
# from this shell would authenticate via that same `az login` identity through
# DefaultAzureCredential, and would need the "Cognitive Services OpenAI User" role on the account.
# Not currently granted to any interactive user principal (only to the caj UAMI used by the
# Container App Jobs/webapp) — no jumpbox script calls Azure OpenAI today, so this is a known gap
# to close if/when one does, not a regression from this change.

KEY_VAULT_NAME="kv-jf-dev-frc"

_jf_secret() {
    az keyvault secret show --vault-name "$KEY_VAULT_NAME" --name "$1" --query value -o tsv
}

AZURE_OPENAI_ENDPOINT="$(_jf_secret openai-endpoint)"
DATABASE_URL="$(_jf_secret postgresql-connection-string)"

export AZURE_OPENAI_ENDPOINT
export DATABASE_URL

if [[ -z "$AZURE_OPENAI_ENDPOINT" || -z "$DATABASE_URL" ]]; then
    echo "jumpbox_env.sh: one or more secrets came back empty — check 'az login' and read access to Key Vault $KEY_VAULT_NAME." >&2
else
    echo "jumpbox_env.sh: AZURE_OPENAI_ENDPOINT, DATABASE_URL exported for this shell session."
fi

unset -f _jf_secret
