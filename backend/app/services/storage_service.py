from typing import Any, Dict, List
from uuid import UUID

import boto3

from app.core.config import settings


def get_object_key(user_id: UUID, project_id: UUID, folder: str, filename: str) -> str:
    """Constructs the R2 object key."""
    return f"{str(user_id)}/projects/{str(project_id)}/{folder}/{filename}"


def generate_upload_url(s3_client: boto3.client, user_id: UUID, project_id: UUID, folder: str, filename: str, content_type: str = None) -> Dict[str, Any]:
    """
    Generates a presigned URL for uploading a file to Cloudflare R2.
    """
    key = get_object_key(user_id, project_id, folder, filename)
    params = {
        "Bucket": settings.R2_BUCKET_NAME,
        "Key": key,
    }
    if content_type:
        params["ContentType"] = content_type

    # 3600 seconds = 1 hour expiration
    expires_in = 3600

    url = s3_client.generate_presigned_url(
        "put_object",
        Params=params,
        ExpiresIn=expires_in
    )

    return {
        "upload_url": url,
        "r2_key": key,
        "expires_in": expires_in
    }


def generate_download_url(s3_client: boto3.client, r2_key: str) -> str:
    """
    Generates a presigned URL for downloading a file.
    """
    url = s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.R2_BUCKET_NAME,
            "Key": r2_key
        },
        ExpiresIn=3600
    )
    return url


def list_objects(s3_client: boto3.client, user_id: UUID, project_id: UUID, folder: str) -> List[Dict[str, Any]]:
    """
    Lists objects in a specific project folder.
    """
    prefix = f"{str(user_id)}/projects/{str(project_id)}/{folder}/"
    response = s3_client.list_objects_v2(
        Bucket=settings.R2_BUCKET_NAME,
        Prefix=prefix
    )

    contents = response.get("Contents", [])
    return [
        {
            "filename": obj["Key"].replace(prefix, ""),
            "r2_key": obj["Key"],
            "size": obj["Size"],
            "last_modified": obj["LastModified"]
        }
        for obj in contents if obj["Key"] != prefix
    ]


def delete_object(s3_client: boto3.client, r2_key: str) -> None:
    """
    Deletes an object from R2.
    """
    s3_client.delete_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=r2_key
    )


def delete_project_prefix(s3_client: boto3.client, user_id: UUID, project_id: UUID) -> None:
    """
    Deletes all objects associated with a project.
    """
    prefix = f"{str(user_id)}/projects/{str(project_id)}/"
    
    # List all objects with prefix
    paginator = s3_client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=settings.R2_BUCKET_NAME, Prefix=prefix)

    delete_us = dict(Objects=[])
    for item in pages.search('Contents'):
        if item:
            delete_us['Objects'].append(dict(Key=item['Key']))

            # Flush once aws limit reached
            if len(delete_us['Objects']) >= 1000:
                s3_client.delete_objects(Bucket=settings.R2_BUCKET_NAME, Delete=delete_us)
                delete_us = dict(Objects=[])

    # Flush rest
    if len(delete_us['Objects']):
        s3_client.delete_objects(Bucket=settings.R2_BUCKET_NAME, Delete=delete_us)
