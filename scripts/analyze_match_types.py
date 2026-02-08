
import sys
import os
from pathlib import Path
from sqlalchemy import text, inspect

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.database.db import SessionLocal, engine

def analyze_matches():
    session = SessionLocal()
    try:
        # Inspect table to see what we actually have
        inspector = inspect(engine)
        columns = [c['name'] for c in inspector.get_columns('match_results')]
        print(f"DEBUG: Actual existing columns in match_results: {columns}")
        
        has_match_engine = 'match_engine' in columns
        has_gemini_score = 'gemini_score' in columns
        
        # Total matches
        total_matches = session.execute(text("SELECT count(*) FROM match_results")).scalar()
        
        print("\n" + "="*40)
        print("MATCHING ENGINE ANALYSIS (Raw SQL)")
        print("="*40)
        print(f"Total Matches Analyzed: {total_matches}")
        print("-" * 40)
        
        if has_match_engine:
            nlp_matches = session.execute(text("SELECT count(*) FROM match_results WHERE match_engine = 'nlp'")).scalar()
            gemini_matches = session.execute(text("SELECT count(*) FROM match_results WHERE match_engine = 'gemini'")).scalar()
            print(f"By 'match_engine' column:")
            print(f"  NLP Engine:           {nlp_matches} ({nlp_matches/total_matches*100:.1f}%)" if total_matches else "  NLP Engine:           0")
            print(f"  Gemini Engine:        {gemini_matches} ({gemini_matches/total_matches*100:.1f}%)" if total_matches else "  Gemini Engine:        0")
        else:
            print("  'match_engine' column NOT FOUND in database.")

        print("-" * 40)
        
        if has_gemini_score:
            gemini_scored_matches = session.execute(text("SELECT count(*) FROM match_results WHERE gemini_score IS NOT NULL")).scalar()
            pure_nlp_matches = session.execute(text("SELECT count(*) FROM match_results WHERE gemini_score IS NULL")).scalar()
            print(f"By 'gemini_score' presence (Actual AI usage):")
            print(f"  Matches with AI Score: {gemini_scored_matches} ({gemini_scored_matches/total_matches*100:.1f}%)" if total_matches else "  Matches with AI Score: 0")
            print(f"  Pure NLP Matches:      {pure_nlp_matches} ({pure_nlp_matches/total_matches*100:.1f}%)" if total_matches else "  Pure NLP Matches:      0")
        else:
            print("  'gemini_score' column NOT FOUND in database.")
            
        print("="*40 + "\n")
        
    except Exception as e:
        print(f"Error analyzing matches: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    analyze_matches()
