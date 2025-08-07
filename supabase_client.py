from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_to_supabase(bucket_name: str, file_path: str, file_name: str):
    with open(file_path, "rb") as f:
        file_data = f.read()

    # ✅ Convert bool to string in file_options
    res = supabase.storage.from_(bucket_name).upload(
        path=file_name,
        file=file_data,
        file_options={
            "upsert": "true",  # ✅ as string
            "content-type": "application/octet-stream"
        }
    )
    return res

def get_public_url(bucket_name: str, file_name: str):
    return f"{SUPABASE_URL}/storage/v1/object/public/{bucket_name}/{file_name}"
