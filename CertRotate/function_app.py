import os
import json
import base64
import logging
import uuid

from datetime import datetime

import requests
import azure.functions as func

from azure.identity import DefaultAzureCredential

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from cryptography.hazmat.primitives.serialization import (
    pkcs12,
    Encoding
)

from cryptography.hazmat.primitives import hashes


app = func.FunctionApp()


@app.function_name(name="KeyVaultCertEventHandler")
@app.event_grid_trigger(arg_name="event")
def main(event: func.EventGridEvent):

    logging.info("==== SPN CERT ROTATION START ====")

    # -------------------------------------------------
    # 1. Parse Event Grid payload
    # -------------------------------------------------
    event_data = event.get_json()

    logging.info(f"EVENT: {json.dumps(event_data, indent=2)}")

    cert_name = event_data.get("ObjectName")
    vault_name = event_data.get("VaultName")

    if not cert_name or not vault_name:
        raise Exception("Missing cert_name or vault_name")

    # -------------------------------------------------
    # 2. Target App Registration
    # -------------------------------------------------
    app_object_id = os.environ.get("APP_OBJECT_ID")

    if not app_object_id:
        raise Exception("APP_OBJECT_ID missing")

    logging.info(f"Target SPN: {app_object_id}")

    credential = DefaultAzureCredential()

    # -------------------------------------------------
    # 3. Get Key Vault secret
    # -------------------------------------------------
    kv_token = credential.get_token(
        "https://vault.azure.net/.default"
    ).token

    kv_url = (
        f"https://{vault_name}.vault.azure.net/"
        f"secrets/{cert_name}?api-version=7.4"
    )

    kv_resp = requests.get(
        kv_url,
        headers={"Authorization": f"Bearer {kv_token}"}
    )

    kv_resp.raise_for_status()

    kv_json = kv_resp.json()
    secret_value = kv_json["value"]

    logging.info(
        f"Key Vault contentType: {kv_json.get('contentType')}"
    )

    # -------------------------------------------------
    # 4. Parse certificate
    # -------------------------------------------------
    cert = None

    if "BEGIN CERTIFICATE" in secret_value:

        logging.info("PEM certificate detected")

        cert = x509.load_pem_x509_certificate(
            secret_value.encode(),
            default_backend()
        )

    else:

        logging.info("PFX certificate detected")

        cert_bytes = base64.b64decode(secret_value)

        _, cert, _ = pkcs12.load_key_and_certificates(
            cert_bytes,
            password=None
        )

    if cert is None:
        raise Exception("Failed to load certificate")

    # -------------------------------------------------
    # 5. Extract public cert
    # -------------------------------------------------
    public_cert_base64 = base64.b64encode(
        cert.public_bytes(Encoding.DER)
    ).decode()

    thumbprint = base64.b64encode(
        cert.fingerprint(hashes.SHA1())
    ).decode()

    # -------------------------------------------------
    # 6. Use Key Vault certificate expiry
    # -------------------------------------------------
    not_after = cert.not_valid_after

    start_time = datetime.utcnow().replace(microsecond=0)

    end_time = not_after.replace(microsecond=0)

    if end_time <= start_time:
        raise Exception("Key Vault cert is already expired")

    iso_format = "%Y-%m-%dT%H:%M:%SZ"

    # -------------------------------------------------
    # 7. Build new keyCredential
    # -------------------------------------------------
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

    # -------------------------------------------------
    # 8. Graph auth
    # -------------------------------------------------
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

    # -------------------------------------------------
    # 9. SIMPLE APPEND MODE (NO SANITIZATION)
    # -------------------------------------------------
    patch_body = {
        "keyCredentials": [new_key]
    }

    logging.info("Adding certificate to App Registration")

    logging.info(json.dumps(patch_body, indent=2))

    # -------------------------------------------------
    # 10. PATCH (append operation)
    # -------------------------------------------------
    resp = requests.patch(
        app_url,
        headers=headers,
        json=patch_body
    )

    if resp.status_code >= 400:
        logging.error("Graph PATCH FAILED")
        logging.error(resp.text)
        resp.raise_for_status()

    logging.info("Certificate successfully added")
    logging.info("==== SPN CERT ROTATION COMPLETE ====")