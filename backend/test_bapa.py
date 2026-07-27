import asyncio
import sys
from api import analyze_stock

def test_bapa():
    print("Menganalisis BAPA...")
    try:
        result = analyze_stock("BAPA", 1000000)
        
        gor = result.get("gorengan")
        if not gor:
            print("Gorengan score tidak tersedia. Mungkin data tidak lengkap.")
            return

        print("\n--- HASIL GORENGAN SCORE BAPA ---")
        print(f"Total Score: {gor['score']} ({gor['level']})")
        print("Faktor:")
        for k, v in gor['factors'].items():
            print(f"  - {k}: {v}")
        
        print("\nPeringatan:")
        for w in gor['warnings']:
            print(f"  - {w}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_bapa()
