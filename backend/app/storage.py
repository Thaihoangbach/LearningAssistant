"""Lưu file gốc đã tải lên (PDF/DOCX) trên một dịch vụ object storage
S3-compatible (Backblaze B2, hoặc bất kỳ dịch vụ S3-compatible nào khác) qua
boto3. Thay cho lưu trên đĩa local (./data/uploads/, xem lịch sử
app/routers/documents.py) — đĩa local không sống sót qua việc host khởi
động lại container với đĩa TẠM (Render free tier không có đĩa bền vững, xem
README mục Deploy).

Không gắn cứng vào MỘT nhà cung cấp cụ thể (biến môi trường đặt tên
`STORAGE_*`, không phải `R2_*`/`B2_*`) — dự án đã đổi provider một lần
(Cloudflare R2 -> Backblaze B2, vì R2 bắt nhập thẻ tín dụng để bật dù dùng
trong hạn mức free) mà không phải sửa dòng code nào, chỉ đổi
`STORAGE_ENDPOINT_URL`/key. Endpoint của Backblaze B2 tự mang theo region
(dạng `s3.<region>.backblazeb2.com`) — parse ra để ký request đúng chuẩn
SigV4, mặc định "auto" cho các dịch vụ không quan tâm region (Cloudflare R2,
MinIO)."""

import os
import re
from functools import lru_cache

BUCKET_NAME = os.environ.get("STORAGE_BUCKET_NAME", "edututor-uploads")

_B2_ENDPOINT_RE = re.compile(r"^https?://s3\.([a-z0-9-]+)\.backblazeb2\.com$")


def _endpoint_url() -> str:
    endpoint = os.environ.get("STORAGE_ENDPOINT_URL")
    if not endpoint:
        raise ValueError(
            "Thiếu STORAGE_ENDPOINT_URL — endpoint S3-compatible của bucket "
            "(Backblaze B2: dạng https://s3.<region>.backblazeb2.com, xem trang "
            "bucket trên dashboard)."
        )
    return endpoint if endpoint.startswith("http") else f"https://{endpoint}"


def _region_name() -> str:
    match = _B2_ENDPOINT_RE.match(_endpoint_url())
    return match.group(1) if match else "auto"


@lru_cache(maxsize=1)
def _get_client():
    import boto3

    access_key = os.environ.get("STORAGE_ACCESS_KEY_ID")
    secret_key = os.environ.get("STORAGE_SECRET_ACCESS_KEY")
    if not (access_key and secret_key):
        raise ValueError(
            "Thiếu STORAGE_ACCESS_KEY_ID/STORAGE_SECRET_ACCESS_KEY. Tạo Application "
            "Key tại Backblaze dashboard -> App Keys, giới hạn quyền vào đúng bucket."
        )
    return boto3.client(
        "s3",
        endpoint_url=_endpoint_url(),
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=_region_name(),
    )


def clear_client_cache() -> None:
    """Chỉ dùng trong test — dọn cache client giữa các trường hợp kiểm thử."""
    _get_client.cache_clear()


def save_file(key: str, data: bytes) -> None:
    _get_client().put_object(Bucket=BUCKET_NAME, Key=key, Body=data)


def read_file(key: str) -> bytes:
    response = _get_client().get_object(Bucket=BUCKET_NAME, Key=key)
    return response["Body"].read()


def delete_file(key: str) -> None:
    _get_client().delete_object(Bucket=BUCKET_NAME, Key=key)


def file_exists(key: str) -> bool:
    from botocore.exceptions import ClientError

    try:
        _get_client().head_object(Bucket=BUCKET_NAME, Key=key)
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
            return False
        raise
