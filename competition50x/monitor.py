"""Scheduled checkpoint monitor; waits while numerical research runs separately."""
import json,time
from datetime import datetime,timezone
from .clock import ROOT,elapsed,snapshot

def main():
 p=ROOT/'checkpoints.md'
 if p.exists():raise FileExistsError(p)
 p.write_text('# Контрольные точки нового 90-минутного исследования\n\nЗдесь нет результатов прошлой задачи. Вероятности — ПРЕДПОЛОЖЕНО: субъективная оценка верифицируемости текущего локального утверждения, не статистическая вероятность победы/50× и не внешняя сертификация.\n')
 for minute in (30,60,85):
  time.sleep(max(0,minute*60-elapsed()))
  clock=snapshot(f'Checkpoint {minute} min','Scheduled real-clock observation; numerical work continues in a separate controlled process, no fabricated timestamps.')
  status_path=ROOT/'results/status.json'
  s=json.loads(status_path.read_text()) if status_path.exists() else {}
  speed=s.get('measured_speedup');quality=s.get('quality')
  with p.open('a') as f:
   f.write(f'\n## {minute} минут\n\n- ИЗМЕРЕНО время: {clock["utc"]}; elapsed {clock["elapsed_seconds"]:.6f} s.\n- Текущий этап: {s.get("stage","not recorded")}.\n- ИЗМЕРЕНО ускорение: {speed if speed is not None else "не определено; завершённого сравнения нет"}. Качество: {quality if quality is not None else "не проверено у метода"}.\n- РАССЧИТАНО: условные FLOPs/bandwidth оценки в brainstorm.md; они не засчитываются как speedup. ПРЕДПОЛОЖЕНО: переносимость за пределы этого dataset не доказана.\n- Главный риск: {s.get("main_risk","нет завершённого сравнения")}.\n- ПРЕДПОЛОЖЕНО вероятность независимой проверки текущего локального утверждения: {s.get("verification_probability_percent",0)}%.\n- Снимок состояния: `{json.dumps(s,ensure_ascii=False)}`\n')
  print('Checkpoint saved',minute,flush=True)
if __name__=='__main__':main()
