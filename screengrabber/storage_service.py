from typing import Optional, Union, BinaryIO
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
import logging


class StorageService:
    """A service class for handling S3 storage operations."""

    def __init__(
        self,
        bucket_name: str,
        endpoint_url: str,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: Optional[str] = "auto",
    ) -> None:
        """
        Initialize the StorageService with S3 credentials.

        Args:
            bucket_name: Name of the S3 bucket
            aws_access_key_id: AWS access key ID (optional if using AWS CLI credentials)
            aws_secret_access_key: AWS secret access key (optional if using AWS CLI credentials)
            region_name: AWS region name (optional, defaults to AWS CLI configuration)
        """
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )
        self.logger = logging.getLogger(__name__)

    def upload_file(
        self,
        file: Union[str, Path, BinaryIO],
        key: str,
        content_type: Optional[str] = None,
    ) -> bool:
        """
        Upload a file to S3.

        Args:
            file: File path or file-like object to upload
            key: S3 object key (path in bucket)
            content_type: MIME type of the file (optional)

        Returns:
            bool: True if upload was successful, False otherwise
        """
        try:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type

            if isinstance(file, (str, Path)):
                self.s3_client.upload_file(
                    str(file), self.bucket_name, key, ExtraArgs=extra_args
                )
            else:
                self.s3_client.upload_fileobj(
                    file, self.bucket_name, key, ExtraArgs=extra_args
                )

            self.logger.info(
                f"Successfully uploaded file to s3://{self.bucket_name}/{key}"
            )
            return True

        except ClientError as e:
            self.logger.error(f"Failed to upload file to S3: {str(e)}")
            return False

    def download_file(self, key: str, destination: Union[str, Path, BinaryIO]) -> bool:
        """
        Download a file from S3.

        Args:
            key: S3 object key to download
            destination: Local file path or file-like object to save to

        Returns:
            bool: True if download was successful, False otherwise
        """
        try:
            if isinstance(destination, (str, Path)):
                self.s3_client.download_file(self.bucket_name, key, str(destination))
            else:
                self.s3_client.download_fileobj(self.bucket_name, key, destination)

            self.logger.info(f"Successfully downloaded s3://{self.bucket_name}/{key}")
            return True

        except ClientError as e:
            self.logger.error(f"Failed to download file from S3: {str(e)}")
            return False

    def generate_presigned_url(self, key: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for temporary access to an S3 object.

        Args:
            key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Optional[str]: Presigned URL if successful, None otherwise
        """
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expiration,
            )
            return url

        except ClientError as e:
            self.logger.error(f"Failed to generate presigned URL: {str(e)}")
            return None

    def file_exists(self, key: str) -> bool:
        """
        Efficiently check if a file exists in the S3 bucket.
        This method uses head_object which only retrieves metadata,
        making it more efficient than downloading the object.

        Args:
            key: S3 object key to check

        Returns:
            bool: True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            self.logger.error(f"Error checking file existence: {str(e)}")
            raise

    def file_exists_with_prefix(self, prefix: str, use_delimiter: bool = True) -> bool:
        """
        Efficiently check if any file exists with the given prefix in the S3 bucket.
        Uses list_objects_v2 with MaxKeys=1 for optimal performance.

        Args:
            prefix: The prefix to check for

        Returns:
            bool: True if any file with prefix exists, False otherwise
        """
        try:
            # Build the request parameters
            params = {"Bucket": self.bucket_name, "Prefix": prefix, "MaxKeys": 1}

            # If using delimiter, add it to narrow down the search space
            if use_delimiter and "/" in prefix:
                params["Delimiter"] = "/"
                # Extract the directory part of the prefix
                last_slash = prefix.rindex("/")
                if last_slash > 0:
                    params["Prefix"] = prefix[: last_slash + 1]

            response = self.s3_client.list_objects_v2(**params)
            return "Contents" in response and len(response["Contents"]) > 0
        except ClientError as e:
            self.logger.error(f"Error checking file prefix existence: {str(e)}")
            raise
