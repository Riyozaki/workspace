"""Real wall + monotonic timing; no synthetic elapsed-time values."""
from pathlib import Path
from datetime import datetime, timezone
import json,time,argparse
ROOT=Path(__file__).resolve().parent

def snapshot(stage,note=''):
 s=json.loads((ROOT/'start_time.json').read_text());wall=time.time()-s['start_unix'];mono=time.monotonic()-s['start_monotonic']
 r={'utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':wall,'elapsed_monotonic_seconds':mono,'stage':stage,'note':note,'remaining_seconds':max(0,5400-min(wall,mono))}
 with (ROOT/'work_log.md').open('a') as f:f.write(f'\n## {stage}\n\n- Tool clock: `{r["utc"]}`; wall `{wall:.6f}` s; monotonic `{mono:.6f}` s.\n- {note}\n')
 print(json.dumps(r,indent=2),flush=True);return r

def elapsed():
 s=json.loads((ROOT/'start_time.json').read_text());return min(time.time()-s['start_unix'],time.monotonic()-s['start_monotonic'])

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('stage');p.add_argument('--note',default='');p.add_argument('--require-deadline',action='store_true');a=p.parse_args()
 if a.require_deadline and elapsed()<5400:raise SystemExit('90-minute deadline not reached')
 snapshot(a.stage,a.note)
