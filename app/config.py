import os
from dotenv import load_dotenv
from supabase import create_client, Client
 
load_dotenv()
 
SUPABASE_URL      = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
SECRET_KEY        = os.getenv("SECRET_KEY", "changez-moi")
 
if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("SUPABASE_URL et SUPABASE_ANON_KEY sont requis dans .env")
 
# Client Supabase global
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)