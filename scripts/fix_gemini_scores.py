#!/usr/bin/env python3
"""One-time migration script to fix inflated gemini_score values.

The gemini_score was being multiplied by 100 twice (once in gemini_client.py
and once in search.py), causing values like 7700 instead of 77.

This script divides all gemini_score values > 100 by 100 to correct them.

Run with: python scripts/fix_gemini_scores.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.database.db import SessionLocal


def fix_gemini_scores():
    """Fix inflated gemini_score values in the database."""
    db = SessionLocal()
    
    try:
        # First, let's see what we're working with
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN gemini_score > 100 THEN 1 END) as inflated,
                MIN(gemini_score) as min_score,
                MAX(gemini_score) as max_score
            FROM match_results
            WHERE gemini_score IS NOT NULL
        """))
        row = result.fetchone()
        
        print(f"Total records with gemini_score: {row[0]}")
        print(f"Records with inflated scores (>100): {row[1]}")
        print(f"Score range: {row[2]} - {row[3]}")
        
        if row[1] == 0:
            print("\nNo inflated scores found. Nothing to fix.")
            return
        
        # Show sample of inflated scores before fix
        print("\nSample of inflated scores (before fix):")
        samples = db.execute(text("""
            SELECT id, gemini_score 
            FROM match_results 
            WHERE gemini_score > 100 
            ORDER BY gemini_score DESC 
            LIMIT 5
        """))
        for sample in samples:
            print(f"  ID {sample[0]}: {sample[1]} -> {sample[1] / 100}")
        
        # Fix the inflated scores
        print(f"\nFixing {row[1]} inflated gemini_score values...")
        
        db.execute(text("""
            UPDATE match_results 
            SET gemini_score = gemini_score / 100 
            WHERE gemini_score > 100
        """))
        
        db.commit()
        
        # Verify the fix
        verify = db.execute(text("""
            SELECT 
                COUNT(CASE WHEN gemini_score > 100 THEN 1 END) as still_inflated,
                MIN(gemini_score) as min_score,
                MAX(gemini_score) as max_score
            FROM match_results
            WHERE gemini_score IS NOT NULL
        """))
        verify_row = verify.fetchone()
        
        print(f"\nAfter fix:")
        print(f"  Still inflated: {verify_row[0]}")
        print(f"  Score range: {verify_row[1]} - {verify_row[2]}")
        
        if verify_row[0] == 0:
            print("\n✅ All gemini_score values have been corrected!")
        else:
            print(f"\n⚠️  {verify_row[0]} records still have scores > 100")
            
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 50)
    print("Gemini Score Fix Migration")
    print("=" * 50)
    fix_gemini_scores()
