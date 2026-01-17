"""
Thumbnail Service for Buun Curator.

Handles screenshot processing and upload to S3/MinIO.
"""

import io
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from aiobotocore.session import get_session
from PIL import Image

from buun_curator.config import Config, get_config
from buun_curator.logging import get_logger

if TYPE_CHECKING:
    from types_aiobotocore_s3 import S3Client

logger = get_logger(__name__)

# Thumbnail settings
THUMBNAIL_WIDTH = 640
THUMBNAIL_HEIGHT = 400
THUMBNAIL_QUALITY = 85


class ThumbnailService:
    """
    Service for processing and uploading thumbnails to S3 or S3-compatible storage.

    Supports AWS S3, MinIO, and other S3-compatible storage services.
    """

    def __init__(self, config: Config | None = None):
        """
        Initialize ThumbnailService.

        Parameters
        ----------
        config : Config | None, optional
            Application config. If None, uses global config.
        """
        self.config = config or get_config()

    @asynccontextmanager
    async def _get_client(self) -> AsyncIterator["S3Client"]:
        """
        Get an async S3 client context.

        Yields
        ------
        S3Client
            The aiobotocore S3 client.
        """
        session = get_session()

        # Use endpoint_url only for S3-compatible services (MinIO, etc.)
        # For AWS S3, leave endpoint_url as None
        endpoint_url = self.config.s3_endpoint if self.config.s3_endpoint else None

        # Use credentials if provided, otherwise rely on default AWS credential chain
        access_key = self.config.s3_access_key if self.config.s3_access_key else None
        secret_key = self.config.s3_secret_key if self.config.s3_secret_key else None

        async with session.create_client(
            "s3",
            region_name=self.config.s3_region,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        ) as client:
            yield client

    def _process_screenshot(self, screenshot_data: bytes) -> bytes:
        """
        Process screenshot: resize and optimize as JPEG.

        Parameters
        ----------
        screenshot_data : bytes
            Raw PNG screenshot data.

        Returns
        -------
        bytes
            Processed JPEG thumbnail data.
        """
        # Open the image
        img = Image.open(io.BytesIO(screenshot_data))

        # Convert to RGB if necessary (PNG might be RGBA)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Calculate crop area (top portion of page)
        original_width, original_height = img.size

        # Target aspect ratio
        target_ratio = THUMBNAIL_WIDTH / THUMBNAIL_HEIGHT

        # Calculate crop dimensions to match target aspect ratio
        if original_width / original_height > target_ratio:
            # Image is wider than target - crop width
            new_width = int(original_height * target_ratio)
            left = (original_width - new_width) // 2
            crop_box = (left, 0, left + new_width, original_height)
        else:
            # Image is taller than target - crop from top
            new_height = int(original_width / target_ratio)
            crop_box = (0, 0, original_width, new_height)

        img = img.crop(crop_box)

        # Resize to thumbnail size
        img = img.resize((THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT), Image.Resampling.LANCZOS)

        # Save as JPEG
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=THUMBNAIL_QUALITY, optimize=True)
        output.seek(0)

        return output.read()

    def _get_public_url(self, object_key: str) -> str:
        """
        Build the public URL for an uploaded object.

        Parameters
        ----------
        object_key : str
            The S3 object key.

        Returns
        -------
        str
            Public URL to the object.
        """
        if self.config.s3_public_url:
            # Custom public URL (e.g., CDN, MinIO public URL)
            return f"{self.config.s3_public_url.rstrip('/')}/{object_key}"
        else:
            # Default AWS S3 URL format
            return (
                f"https://{self.config.s3_bucket}.s3.{self.config.s3_region}"
                f".amazonaws.com/{object_key}"
            )

    async def upload_thumbnail(
        self,
        entry_id: str,
        screenshot_data: bytes,
    ) -> str:
        """
        Process and upload a thumbnail to S3.

        Parameters
        ----------
        entry_id : str
            The entry ID (used as filename).
        screenshot_data : bytes
            Raw PNG screenshot data from Crawl4AI.

        Returns
        -------
        str
            Public URL to the uploaded thumbnail.
        """
        # Process the screenshot
        thumbnail_data = self._process_screenshot(screenshot_data)

        # Generate object key with optional prefix
        # relative_key: path without prefix (for public URL)
        # object_key: full path in S3 (with prefix)
        relative_key = f"thumbnails/{entry_id}.jpg"
        prefix = self.config.s3_prefix.strip("/") if self.config.s3_prefix else ""
        object_key = f"{prefix}/{relative_key}" if prefix else relative_key

        # Upload to S3
        async with self._get_client() as client:
            await client.put_object(
                Bucket=self.config.s3_bucket,
                Key=object_key,
                Body=thumbnail_data,
                ContentType="image/jpeg",
            )

        # Build public URL (use relative_key since S3_PUBLIC_URL already includes prefix)
        public_url = self._get_public_url(relative_key)

        logger.info(
            "Uploaded thumbnail",
            entry_id=entry_id,
            bytes=len(thumbnail_data),
            url=public_url,
        )

        return public_url

    async def ensure_bucket_exists(self) -> None:
        """
        Ensure the S3 bucket exists, create if not.
        """
        async with self._get_client() as client:
            try:
                await client.head_bucket(Bucket=self.config.s3_bucket)
                logger.debug("Bucket exists", bucket=self.config.s3_bucket)
            except client.exceptions.ClientError:
                await client.create_bucket(Bucket=self.config.s3_bucket)
                logger.info("Created bucket", bucket=self.config.s3_bucket)
