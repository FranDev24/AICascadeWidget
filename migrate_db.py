#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AICascade Widget - Supabase Schema Auto-Migration
Automatically applies database schema to Supabase.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

# Load environment
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("[ERR] Supabase credentials not configured in .env")
    print("   Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
    sys.exit(1)

print(f"[DB] Connecting to Supabase: {SUPABASE_URL}")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Read schema file
schema_path = Path(__file__).parent / "supabase_schema.sql"
if not schema_path.exists():
    print(f"[ERR] Schema file not found: {schema_path}")
    sys.exit(1)

schema_sql = schema_path.read_text(encoding="utf-8")

# Split into individual statements
statements = [s.strip() for s in schema_sql.split(";") if s.strip() and not s.strip().startswith("--")]

print(f"[DB] Found {len(statements)} SQL statements to execute")
print("[DB] Applying schema...")

success_count = 0
error_count = 0

for i, stmt in enumerate(statements, 1):
    try:
        # Use rpc to execute raw SQL
        result = supabase.rpc("exec_sql", {"sql": stmt}).execute()
        print(f"  [OK] Statement {i}/{len(statements)} executed")
        success_count += 1
    except Exception as e:
        # Some statements might fail if they already exist (IF NOT EXISTS)
        error_msg = str(e).lower()
        if "already exists" in error_msg or "duplicate" in error_msg or "exists" in error_msg:
            print(f"  [SKIP] Statement {i}/{len(statements)} skipped (already exists)")
            success_count += 1
        else:
            print(f"  [ERR] Statement {i}/{len(statements)} failed: {e}")
            error_count += 1

print(f"\n[DB] Migration complete:")
print(f"   [OK] Successful: {success_count}")
print(f"   [ERR] Errors: {error_count}")

if error_count == 0:
    print("\n[OK] Schema applied successfully!")
    print("   You can now start the backend with: python main.py")
else:
    print("\n[WARN] Some statements had errors. Check Supabase Dashboard SQL Editor for manual execution.")
    sys.exit(1)