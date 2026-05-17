"""
Statistical significance testing for results.
"""
import pandas as pd
import numpy as np
from scipy import stats


def load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df['mttd_seconds'] = pd.to_numeric(df['mttd_seconds'], errors='coerce')
    df['mttr_seconds'] = pd.to_numeric(df['mttr_seconds'], errors='coerce')
    return df


def wilcoxon_compare(a: pd.Series, b: pd.Series, label: str):
    a = a.dropna()
    b = b.dropna()

    # Align lengths
    min_len = min(len(a), len(b))
    a = a.iloc[:min_len]
    b = b.iloc[:min_len]

    if len(a) < 5:
        print(f"{label}: insufficient data (n={len(a)})")
        return

    stat, p = stats.wilcoxon(a, b, alternative='greater')

    # Effect size: rank-biserial correlation
    n = len(a)
    r = 1 - (2 * stat) / (n * (n + 1))

    significant = p < 0.05
    print(f"\n{label}")
    print(f"  W={stat:.1f}  p={p:.4f}  effect_size={r:.3f}")
    print(f"  {'SIGNIFICANT' if significant else 'NOT SIGNIFICANT'} at p<0.05")
    print(f"  Mean A: {a.mean():.1f}s  Mean B: {b.mean():.1f}s")
    if a.mean() > 0:
        improvement = (b.mean() - a.mean()) / a.mean() * 100
        print(f"  Improvement: {improvement:.1f}%")


def run(our_path: str, no_auto_path: str, rule_path: str):
    our = load(our_path)
    no_auto = load(no_auto_path)
    rule = load(rule_path)

    print("=" * 50)
    print("WILCOXON SIGNED-RANK TEST RESULTS")
    print("=" * 50)

    print("\n--- MTTD (Mean Time To Detect) ---")
    wilcoxon_compare(no_auto['mttd_seconds'], our['mttd_seconds'],
                     "Our System vs No Automation")
    wilcoxon_compare(rule['mttd_seconds'], our['mttd_seconds'],
                     "Our System vs Rule-Based")

    print("\n--- MTTR (Mean Time To Resolve) ---")
    wilcoxon_compare(no_auto['mttr_seconds'], our['mttr_seconds'],
                     "Our System vs No Automation")
    wilcoxon_compare(rule['mttr_seconds'], our['mttr_seconds'],
                     "Our System vs Rule-Based")

    print("\n--- DETECTION RATES ---")
    for label, df in [('Our System', our), ('No Automation', no_auto), ('Rule-Based', rule)]:
        tp = df['true_positive'].sum()
        total = len(df)
        print(f"  {label}: {tp}/{total} detected ({tp/total*100:.1f}%)")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--our', required=True)
    parser.add_argument('--no_auto', required=True)
    parser.add_argument('--rule', required=True)
    args = parser.parse_args()
    run(args.our, args.no_auto, args.rule)