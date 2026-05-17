"""
Loads and computes metrics from result CSVs.
"""
import pandas as pd
import numpy as np


class MetricsRecorder:
    def __init__(self, csv_path: str):
        self.df = pd.read_csv(csv_path)
        # Convert numeric columns
        for col in ['mttd_seconds', 'mttr_seconds']:
            self.df[col] = pd.to_numeric(self.df[col], errors='coerce')

    def precision(self) -> float:
        tp = self.df['true_positive'].sum()
        fp = self.df['false_positive'].sum()
        if tp + fp == 0:
            return 0.0
        return tp / (tp + fp)

    def recall(self) -> float:
        tp = self.df['true_positive'].sum()
        total = len(self.df)
        if total == 0:
            return 0.0
        return tp / total

    def f1(self) -> float:
        p = self.precision()
        r = self.recall()
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)

    def mttd_stats(self) -> dict:
        vals = self.df['mttd_seconds'].dropna()
        return {
            'mean': vals.mean(),
            'median': vals.median(),
            'std': vals.std(),
            'p95': vals.quantile(0.95)
        }

    def mttr_stats(self) -> dict:
        vals = self.df['mttr_seconds'].dropna()
        return {
            'mean': vals.mean(),
            'median': vals.median(),
            'std': vals.std(),
            'p95': vals.quantile(0.95)
        }

    def summary(self) -> dict:
        return {
            'total_scenarios': len(self.df),
            'precision': round(self.precision(), 3),
            'recall': round(self.recall(), 3),
            'f1': round(self.f1(), 3),
            'mttd': self.mttd_stats(),
            'mttr': self.mttr_stats()
        }