import os
import json
import base64
import logging
import uuid
import secrets
import string

from datetime import datetime

import requests
import azure.functions as func

from azure.identity import DefaultAzureCredential

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from cryptography.hazmat.primitives.serialization import (
    pkcs12,
    Encoding,
    BestAvailableEncryption
)
from cryptography.hazmat.primitives import hashes

# For GitHub secret encryption
import nacl.encoding
import nacl.public

app = func.FunctionApp()

def generate_password(length=32):
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def set_github_secret(secret_name, secret_value, repo, github_token):
    # 1. Get repo public key
    url = f"https://api.github.com/repos/{repo}/actions/secrets/public-key"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    resp = requests.get(url, headers=headers)
    if not resp.ok:
        raise Exception(f"Failed to get public key: {resp.text}")
    public_key = resp.json()["key"]
    key_id = resp.json()["key_id"]

    # 2. Encrypt the secret with the public key (Libsodium)
    public_key = nacl.public.PublicKey(public_key.encode("utf-8"), nacl.encoding.Base64Encoder())
    sealed_box = nacl.public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    encrypted_value = base64.b64encode(encrypted).decode("utf-8")

    # 3. Set the secret
    api_url = f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}"
    payload = {"encrypted_value": encrypted_value, "key_id": key_id}
    resp = requests.put(api_url, headers=headers, json=payload)
    if not resp.ok:
        raise Exception(f"Failed to set secret {secret_name}: {resp.text}")

# --- Utility function to support both PEM and PFX ---
from cryptography.hazmat.primitives import serialization

def load_cert_and_key_from_secret(secret_value, content_type):
    """
    Supports both PFX (base64-encoded PKCS#12) and PEM formats.
    Returns: private_key, cert, ca_chain
    """
    if content_type == "application/x-pem-file":
        pem_data = secret_value.encode()
        private_key = None
        cert = None
        ca_chain = []
        # Split PEM blocks
        blocks = []
        current_block = []
        in_block = False
        for line in pem_data.splitlines():
            if line.startswith(b"-----BEGIN "):
                in_block = True
                current_block = [line]
            elif line.startswith(b"-----END "):
                current_block.append(line)
                in_block = False
                blocks.append(b"\n".join(current_block) + b"\n")
            elif in_block:
                current_block.append(line)
        for block in blocks:
            if b'PRIVATE KEY-----' in block:
                try:
                    private_key = serialization.load_pem_private_key(
                        block,
                        password=None,
                        backend=default_backend()
                    )
                except Exception as e:
                    continue
            elif b'CERTIFICATE-----' in block:
                try:
                    cert_obj = x509.load_pem_x509_certificate(
                        block,
                        backend=default_backend()
                    )
                    if cert is None:
                        cert = cert_obj
                    else:
                        ca_chain.append(cert_obj)
                except Exception as e:
                    continue
        if cert is None or private_key is None:
            raise Exception("Failed to extract certificate or private key from PEM")
        return private_key, cert, ca_chain if ca_chain else None

    elif content_type.startswith("application/x-pkcs12"):  # PFX
        cert_bytes = base64.b64decode(secret_value)
        private_key, cert, ca_chain = pkcs12.load_key_and_certificates(cert_bytes, password=None)
        if cert is None or private_key is None:
            raise Exception("Failed to load certificate or private key from PFX")
        return private_key, cert, ca_chain
    else:
        raise Exception(f"Unsupported contentType: {content_type}")

@app.function_name(name="KeyVaultCertEventHandler")
@app.event_grid_trigger(arg_name="event")
def main(event: func.EventGridEvent):

    logging.info("==== SPN CERT ROTATION START ====")

    # 1. Parse Event Grid payload
    event_data = event.get_json()
    logging.info(f"EVENT: {json.dumps(event_data, indent=2)}")

    cert_name = event_data.get("ObjectName")
    vault_name = event_data.get("VaultName")
    if not cert_name or not vault_name:
        raise Exception("Missing cert_name or vault_name")

    # 2. Target App Registration
    app_object_id = os.environ.get("APP_OBJECT_ID")
    if not app_object_id:
        raise Exception("APP_OBJECT_ID missing")

    # 2b. GitHub info
    github_token = os.environ.get("GITHUB_TOKEN")
    github_repo = os.environ.get("GITHUB_REPO")
    if not github_token or not github_repo:
        raise Exception("GITHUB_TOKEN or GITHUB_REPO missing")

    credential = DefaultAzureCredential()

    # 3. Get Key Vault secret (the certificate as PFX or PEM)
    kv_token = credential.get_token("https://vault.azure.net/.default").token
    kv_url = f"https://{vault_name}.vault.azure.net/secrets/{cert_name}?api-version=7.4"
    kv_resp = requests.get(kv_url, headers={"Authorization": f"Bearer {kv_token}"})
    kv_resp.raise_for_status()
    kv_json = kv_resp.json()
    secret_value = kv_json["value"]
    content_type = kv_json.get("contentType", "")

    logging.info(f"Key Vault contentType: {content_type}")

    # 4. Load cert and keys/cert chain (PFX or PEM)
    private_key, cert, ca_chain = load_cert_and_key_from_secret(secret_value, content_type)

    # --- Part A: Update App Registration with new public cert ---
    # 5. Extract public cert
    public_cert_base64 = base64.b64encode(
        cert.public_bytes(Encoding.DER)
    ).decode()

    thumbprint = base64.b64encode(
        cert.fingerprint(hashes.SHA1())
    ).decode()

    not_after = cert.not_valid_after
    start_time = datetime.utcnow().replace(microsecond=0)
    end_time = not_after.replace(microsecond=0)

    if end_time <= start_time:
        raise Exception("Key Vault cert is already expired")

    iso_format = "%Y-%m-%dT%H:%M:%SZ"

    new_key = {
        "customKeyIdentifier": thumbprint,
        "displayName": f"KV-Rotated-{cert_name}",
        "startDateTime": start_time.strftime(iso_format),
        "endDateTime": end_time.strftime(iso_format),
        "key": public_cert_base64,
        "keyId": str(uuid.uuid4()),
        "type": "AsymmetricX509Cert",
        "usage": "Verify"
    }

    # 6. Graph auth
    graph_token = credential.get_token(
        "https://graph.microsoft.com/.default"
    ).token

    headers = {
        "Authorization": f"Bearer {graph_token}",
        "Content-Type": "application/json"
    }

    app_url = (
        f"https://graph.microsoft.com/v1.0/"
        f"applications/{app_object_id}"
    )

    patch_body = {
        "keyCredentials": [new_key]
    }

    logging.info("Adding certificate to App Registration")
    logging.info(json.dumps(patch_body, indent=2))

    resp = requests.patch(
        app_url,
        headers=headers,
        json=patch_body
    )

    if resp.status_code >= 400:
        logging.error("Graph PATCH FAILED")
        logging.error(resp.text)
        resp.raise_for_status()

    logging.info("Certificate successfully added to App Registration")

    # --- Part B: Export PFX for GitHub Actions secrets ---
    # 7. Generate a random password
    pfx_password = generate_password()

    # 8. Export password-protected PFX (base64)
    new_pfx = pkcs12.serialize_key_and_certificates(
        name=cert.subject.rfc4514_string().encode(),
        key=private_key,
        cert=cert,
        cas=ca_chain,
        encryption_algorithm=BestAvailableEncryption(pfx_password.encode())
    )
    pfx_base64 = base64.b64encode(new_pfx).decode()

    # 9. Push PFX and password to GitHub Actions secrets
    set_github_secret("CERT_BASE64", pfx_base64, github_repo, github_token)
    set_github_secret("CERT_PASSWORD", pfx_password, github_repo, github_token)

    # 10. Push CERT_THUMBPRINT as a GitHub secret
    set_github_secret("CERT_THUMBPRINT", thumbprint, github_repo, github_token)

    # 11. Fetch and push AZURE_CLIENT_ID as a GitHub secret
    client_id_url = f"https://graph.microsoft.com/v1.0/applications/{app_object_id}?$select=appId"
    client_id_resp = requests.get(client_id_url, headers=headers)
    client_id_resp.raise_for_status()
    azure_client_id = client_id_resp.json()["appId"]
    set_github_secret("AZURE_CLIENT_ID", azure_client_id, github_repo, github_token)

    # # 12. TESTING: Log the values (remove or comment out in production!)
    # logging.info("=== TEST VALUES ===")
    # logging.info(f"CERT_BASE64: {pfx_base64[:80]}...")  # Print only first 80 chars
    # logging.info(f"CERT_PASSWORD: {pfx_password}")
    # logging.info(f"CERT_THUMBPRINT: {thumbprint}")
    # logging.info(f"AZURE_CLIENT_ID: {azure_client_id}")
    # logging.info("===================")

    logging.info("CERT_BASE64, CERT_PASSWORD, CERT_THUMBPRINT, and AZURE_CLIENT_ID updated as GitHub secrets.")

    logging.info("==== SPN CERT ROTATION COMPLETE ====")
