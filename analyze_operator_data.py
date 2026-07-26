#!/usr/bin/env python3
"""
Analyze operator data from quality history.
Generates reports for P0 gaps.
"""

import json
from pathlib import Path
from collections import Counter

def load_quality_history():
    with open('sat_poi_quality_history.json', 'r') as f:
        return json.load(f)

def generate_reports():
    history = load_quality_history()
    latest = history['versions'][-1]
    
    print("\n" + "="*70)
    print("🎯 P0 OPERATOR DATA ANALYSIS")
    print("="*70 + "\n")
    
    # 1. Operator Distribution
    print("📊 1. OPERATOR DISTRIBUTION (Top 20)")
    print("-" * 70)
    if 'operatorDistribution' in latest:
        total_with_ops = latest['linkCoverage']['operator']['count']
        for i, item in enumerate(latest['operatorDistribution'], 1):
            op = item['operator']
            count = item['count']
            pct = (count / total_with_ops * 100) if total_with_ops else 0
            print(f"  {i:2d}. {op:40s} {count:3d} POIs ({pct:5.1f}%)")
    print()
    
    # 2. Coverage by Section
    print("📍 2. OPERATOR COVERAGE BY SECTION (21 sections)")
    print("-" * 70)
    sections = latest.get('sectionCoverage', [])
    
    red_flag = []
    green = []
    yellow = []
    
    for sec in sections:
        name = sec['section']
        total = sec['totalPoi']
        op_count = sec['linkCoverage']['operator']['count']
        pct = sec['linkCoverage']['operator']['percent']
        
        status = "🔴" if pct == 0 else "🟡" if pct < 20 else "🟢"
        print(f"  {status} {name:20s}: {op_count:3d}/{total:3d} ({pct:5.1f}%)")
        
        if pct == 0:
            red_flag.append((name, total))
        elif pct < 20:
            yellow.append((name, total, pct))
        else:
            green.append((name, total, pct))
    print()
    
    # 3. Summary Statistics
    print("📈 3. SUMMARY STATISTICS")
    print("-" * 70)
    total_pois = latest['totalPoi']
    with_operator = latest['linkCoverage']['operator']['count']
    total_pct = latest['linkCoverage']['operator']['percent']
    
    print(f"  Total POIs:             {total_pois}")
    print(f"  With operator data:     {with_operator} ({total_pct:.1f}%)")
    print(f"  Missing operator data:  {total_pois - with_operator} ({100-total_pct:.1f}%)")
    print()
    print(f"  Red flag sections (0%):       {len(red_flag)}")
    print(f"  Yellow flag sections (<20%):  {len(yellow)}")
    print(f"  Green sections (20%+):        {len(green)}")
    print()
    
    # 4. Red Flag Sections
    if red_flag:
        print("🚨 4. RED FLAG SECTIONS (0% coverage - HIGH PRIORITY)")
        print("-" * 70)
        for name, total in sorted(red_flag, key=lambda x: -x[1])[:10]:
            print(f"  ⚠️  {name:20s}: {total:3d} POIs need operators")
        print()
    
    # 5. Green Model Sections
    if green:
        print("✅ 5. GOOD MODEL SECTIONS (20%+ coverage)")
        print("-" * 70)
        for name, total, pct in sorted(green, key=lambda x: -x[2])[:5]:
            print(f"  ✓ {name:20s}: {total:3d} POIs ({pct:5.1f}%)")
        print()
    
    # 6. Next Actions
    print("🎯 6. RECOMMENDED NEXT ACTIONS")
    print("-" * 70)
    print("  1. Target red-flag sections for crowdsourcing (0% coverage)")
    print("  2. Validate top 5 operators have Wikidata Q-numbers")
    print("  3. Check if top operators already in 'known organisations' list")
    print("  4. Create GitHub issues for each red-flag section")
    print(f"  5. Goal: Increase from {total_pct:.1f}% to 30% coverage this sprint")
    print()

if __name__ == '__main__':
    generate_reports()
