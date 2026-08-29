"""
cleanup_backtest_files.py — Menghapus semua file script backtest temporary, log, dan json research BSJP
sehingga repositori bersih dan siap dipush ke GitHub.
"""
import os, sys

BACKEND = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND, "data")

FILES_TO_DELETE = [
    # Temporary test / research scripts in backend/
    os.path.join(BACKEND, "_bsjp_brute.py"),
    os.path.join(BACKEND, "_bsjp_close_sweep.py"),
    os.path.join(BACKEND, "_bsjp_godmode_research.py"),
    os.path.join(BACKEND, "_bsjp_oos_validate.py"),
    os.path.join(BACKEND, "_bsjp_stockbit_proxy_test.py"),
    os.path.join(BACKEND, "_bsjp_walkforward.py"),
    os.path.join(BACKEND, "_bsjp_winner_analysis.py"),
    os.path.join(BACKEND, "backtest_1y.py"),
    os.path.join(BACKEND, "backtest_1y_fast.py"),
    os.path.join(BACKEND, "backtest_3m.py"),
    os.path.join(BACKEND, "backtest_bsjp_golden.py"),
    os.path.join(BACKEND, "backtest_calibrate.py"),
    os.path.join(BACKEND, "bsjp_100pct_coverage_optimizer.py"),
    os.path.join(BACKEND, "bsjp_combo_test.py"),
    os.path.join(BACKEND, "bsjp_coverage_fix.py"),
    os.path.join(BACKEND, "bsjp_deep_sweep.py"),
    os.path.join(BACKEND, "bsjp_final_iteration.py"),
    os.path.join(BACKEND, "bsjp_final_v2.py"),
    os.path.join(BACKEND, "bsjp_refine_v6.py"),
    os.path.join(BACKEND, "bsjp_research_v1.py"),
    os.path.join(BACKEND, "bsjp_stockbit_final.py"),
    os.path.join(BACKEND, "bsjp_ultimate.py"),
    os.path.join(BACKEND, "check21.py"),
    os.path.join(BACKEND, "check21_full.py"),
    os.path.join(BACKEND, "check_all_bsjp_variations_aug10.py"),
    os.path.join(BACKEND, "check_aug10_signals.py"),
    os.path.join(BACKEND, "check_august_2026.py"),
    os.path.join(BACKEND, "check_january_2026.py"),
    os.path.join(BACKEND, "check_latest_date.py"),
    os.path.join(BACKEND, "diagnose_stockbit_filters.py"),
    os.path.join(BACKEND, "explain_aug10_exact.py"),
    os.path.join(BACKEND, "investigate_empty_days.py"),
    os.path.join(BACKEND, "map_top_gainers_11aug.py"),
    os.path.join(BACKEND, "pred28.py"),
    os.path.join(BACKEND, "scan_exact_10aug_bsjp.py"),
    os.path.join(BACKEND, "scrape_and_screen_28aug.py"),
    os.path.join(BACKEND, "test_bapa.py"),
    os.path.join(BACKEND, "test_bsjp_integration.py"),
    os.path.join(BACKEND, "test_idx_bei_live.py"),
    os.path.join(BACKEND, "test_idx_package.py"),
    os.path.join(BACKEND, "test_real_data.py"),
    os.path.join(BACKEND, "test_temporal_integrity.py"),
    os.path.join(BACKEND, "verify21_24.py"),
    os.path.join(BACKEND, "verify_exact_winrates.py"),
    
    # Temporary log and json files in backend/
    os.path.join(BACKEND, "bsjp_30min.log"),
    os.path.join(BACKEND, "bsjp_30min_REAL.log"),
    os.path.join(BACKEND, "bsjp_bandarmology.log"),
    os.path.join(BACKEND, "bsjp_bandarmology_real.json"),
    os.path.join(BACKEND, "bsjp_exhaustive_30min.json"),
    os.path.join(BACKEND, "bsjp_exhaustive_REAL.json"),
    
    # Temporary research json files in backend/data/
    os.path.join(DATA_DIR, "bsjp_brute_sweep.json"),
    os.path.join(DATA_DIR, "bsjp_close_sweep.json"),
    os.path.join(DATA_DIR, "bsjp_deep_sweep.json"),
    os.path.join(DATA_DIR, "bsjp_final_report.json"),
    os.path.join(DATA_DIR, "bsjp_final_results.json"),
    os.path.join(DATA_DIR, "bsjp_final_v2.json"),
    os.path.join(DATA_DIR, "bsjp_golden_backtest.json"),
    os.path.join(DATA_DIR, "bsjp_oos_top20.json"),
    os.path.join(DATA_DIR, "bsjp_refine_results.json"),
    os.path.join(DATA_DIR, "bsjp_research_v1.json"),
    os.path.join(DATA_DIR, "bsjp_walkforward.json"),
]

def cleanup():
    deleted_count = 0
    not_found_count = 0
    
    for fpath in FILES_TO_DELETE:
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
                print(f"[DELETED] {os.path.basename(fpath)}")
                deleted_count += 1
            except Exception as e:
                print(f"[ERROR] Gagal hapus {fpath}: {e}")
        else:
            not_found_count += 1
            
    print(f"\nSelesai! Total file dihapus: {deleted_count} file. (Tidak ditemukan/sudah bersih: {not_found_count})")

if __name__ == "__main__":
    cleanup()
