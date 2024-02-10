#!/bin/env python3

# https://github.com/Azure-Samples/AzureStorageSnippets/blob/master/blobs/howto/python/blob-devguide-py/blob_devguide_upload.py

from azure.storage.blob import BlobServiceClient
from azure.storage.blob import BlobClient
from azure.storage.blob import ContainerClient

subscription_id = '3f2fc2c5-8446-4cd5-af2f-a6af7f85ea75'
tenant_id = "c8d65d6a-d488-4dd9-9399-68f868316782"
app_id = "8f36c40b-cd9e-4c4e-91cf-22817d8604c3"  # devSP2

cert_path = "/home/taras/.swm/cert.pem"
key_path = "/home/taras/.swm/key.pem"

with open(key_path, 'rb') as file:
    key_content = file.read()
with open(cert_path , 'rb') as file:
    cert_content = file.read()
cert_data = key_content + cert_content

def upload_image(self, blob_service_client: BlobServiceClient, image_name: str, image_path: str):
    container_client = blob_service_client.get_container_client(container=image_name)
    sample_tags = {"Content": "image", "Date": "2022-01-01"}
    with open(file=image_path, mode="rb") as data:
        blob_client = container_client.upload_blob(name=image_name, data=data, tags=sample_tags)

if __name__ == '__main__':
    account_url = "https://swmstorage.blob.core.windows.net"
    credential = CertificateCredential(
        tenant_id=tenant_id,
        client_id=app_id,
        certificate_data=cert_data,
    )
    blob_service_client = BlobServiceClient(account_url, credential=credential)
    upload_image(blob_service_client, "Test Image 1", "/home/taras/projects/openstack-box/livecd.ubuntu-cpc.azure.vhd")
