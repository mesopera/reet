"""
Generates result charts for the paper.
"""
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns


def load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df['mttd_seconds'] = pd.to_numeric(df['mttd_seconds'], errors='coerce')
    df['mttr_seconds'] = pd.to_numeric(df['mttr_seconds'], errors='coerce')
    return df


def plot_all(our_path: str, no_auto_path: str, rule_path: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)

    our    = load(our_path);    our['condition']     = 'Our System'
    no_auto = load(no_auto_path); no_auto['condition'] = 'No Automation'
    rule   = load(rule_path);   rule['condition']    = 'Rule-Based'

    combined = pd.concat([our, no_auto, rule], ignore_index=True)

    colors = {
        'Our System':    '#00C2FF',
        'No Automation': '#F87171',
        'Rule-Based':    '#FBBF24'
    }

    # ── Plot 1: MTTD box plot ──────────────────────────
    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor('#0A1628')
    ax.set_facecolor('#0D2038')

    data_mttd = [
        our['mttd_seconds'].dropna().values,
        no_auto['mttd_seconds'].dropna().values,
        rule['mttd_seconds'].dropna().values
    ]
    labels = ['Our System', 'No Automation', 'Rule-Based']
    bp = ax.boxplot(data_mttd, patch_artist=True, labels=labels)

    for patch, color in zip(bp['boxes'], [colors[l] for l in labels]):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_title('Mean Time To Detect (MTTD) by Condition', color='white', fontsize=13)
    ax.set_ylabel('Seconds', color='white')
    ax.tick_params(colors='white')
    ax.spines[:].set_color('#1A4060')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'mttd_boxplot.png'), dpi=150, facecolor='#0A1628')
    plt.close()
    print("Saved mttd_boxplot.png")

    # ── Plot 2: MTTR box plot ──────────────────────────
    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor('#0A1628')
    ax.set_facecolor('#0D2038')

    data_mttr = [
        our['mttr_seconds'].dropna().values,
        no_auto['mttr_seconds'].dropna().values,
        rule['mttr_seconds'].dropna().values
    ]
    bp = ax.boxplot(data_mttr, patch_artist=True, labels=labels)
    for patch, color in zip(bp['boxes'], [colors[l] for l in labels]):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_title('Mean Time To Resolve (MTTR) by Condition', color='white', fontsize=13)
    ax.set_ylabel('Seconds', color='white')
    ax.tick_params(colors='white')
    ax.spines[:].set_color('#1A4060')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'mttr_boxplot.png'), dpi=150, facecolor='#0A1628')
    plt.close()
    print("Saved mttr_boxplot.png")

    # ── Plot 3: Precision / Recall / F1 bar chart ─────
    def metrics(df):
        tp = df['true_positive'].sum()
        fp = df['false_positive'].sum()
        total = len(df)
        p = tp / (tp + fp) if (tp + fp) > 0 else 0
        r = tp / total if total > 0 else 0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0
        return round(p, 3), round(r, 3), round(f, 3)

    our_m    = metrics(our)
    no_auto_m = metrics(no_auto)
    rule_m   = metrics(rule)

    x = range(3)
    metric_labels = ['Precision', 'Recall', 'F1']
    bar_width = 0.25

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor('#0A1628')
    ax.set_facecolor('#0D2038')

    ax.bar([i - bar_width for i in x], our_m,     width=bar_width, label='Our System',    color=colors['Our System'],    alpha=0.85)
    ax.bar([i             for i in x], no_auto_m,  width=bar_width, label='No Automation', color=colors['No Automation'], alpha=0.85)
    ax.bar([i + bar_width for i in x], rule_m,     width=bar_width, label='Rule-Based',    color=colors['Rule-Based'],    alpha=0.85)

    ax.set_xticks(list(x))
    ax.set_xticklabels(metric_labels, color='white')
    ax.set_ylim(0, 1.1)
    ax.set_title('Precision / Recall / F1 by Condition', color='white', fontsize=13)
    ax.tick_params(colors='white')
    ax.spines[:].set_color('#1A4060')
    ax.legend(facecolor='#0D2038', labelcolor='white')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'precision_recall_f1.png'), dpi=150, facecolor='#0A1628')
    plt.close()
    print("Saved precision_recall_f1.png")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--our',     required=True)
    parser.add_argument('--no_auto', required=True)
    parser.add_argument('--rule',    required=True)
    parser.add_argument('--output',  default='docs/figures/')
    args = parser.parse_args()
    plot_all(args.our, args.no_auto, args.rule, args.output)