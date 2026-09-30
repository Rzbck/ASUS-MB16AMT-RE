"""Publish only aggregate power measurements from a private GaugeWatch campaign."""
import argparse
import json
import statistics
from pathlib import Path


def summarize(text):
    phases = {}
    for line in text.splitlines():
        if not line.startswith('GAUGE_WATCH '):
            continue
        parts = line.split()
        fields = dict(p.split('=', 1) for p in parts[2:] if '=' in p)
        phase = fields.get('phase')
        if not phase:
            continue
        h, m, s = map(float, parts[1].split(':'))
        row = {'seconds': h * 3600 + m * 60 + s}
        for key in ('V_mV', 'I_mA', 'VI_W', 'AP_W', 'TEMP_C'):
            row[key] = float(fields[key])
        phases.setdefault(phase, []).append(row)
    result = {}
    for phase, rows in phases.items():
        tail = [r for r in rows if r['seconds'] >= rows[-1]['seconds'] - 15]
        stats = {key: {'median': round(statistics.median(r[key] for r in tail), 4),
                       'min': min(r[key] for r in tail), 'max': max(r[key] for r in tail)}
                 for key in ('V_mV', 'I_mA', 'VI_W', 'AP_W', 'TEMP_C')}
        elapsed = tail[-1]['seconds'] - tail[0]['seconds']
        result[phase] = {'samples_total': len(rows), 'tail_samples': len(tail),
                         'tail_window_s': round(elapsed, 3), 'measurements': stats,
                         'tail_VI_change_W': round(tail[-1]['VI_W'] - tail[0]['VI_W'], 4)}
    if not result:
        raise ValueError('No campaign samples')
    return {'date': '2026-09-30', 'power_domain': 'battery, not USB input',
            'method': 'last 15 seconds of each phase; settling is not assumed',
            'native_restore_confirmed': 'RESTORE_CONFIRMED brightness=100 ED=0' in text,
            'phases': result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.write_text(json.dumps(summarize(args.log.read_text()), indent=2) + '\n')


if __name__ == '__main__':
    main()
