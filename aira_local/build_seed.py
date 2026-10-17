"""Small teacher-authored seed/export; does NOT fine-tune the language model."""
import json
from pathlib import Path
from .tools import calculate
ROOT=Path(__file__).resolve().parent


def main():
 rows=[]
 for i,(prompt,expression) in enumerate([('Сколько будет 17 + 25?','17+25'),('Вычисли (12 + 8) * 3','(12+8)*3'),('What is 96 / 8?','96/8'),('Посчитай 7 * 9 - 4','7*9-4'),('Calculate 2 ** 5','2**5'),('Вычисли 100 - 37','100-37')]):
  answer=calculate(expression)['text'];rows.append({'id':f'arithmetic-{i}','skill':'arithmetic','family':'seed_arithmetic','messages':[{'role':'user','content':prompt},{'role':'assistant','content':answer}],'teacher_rationale':'Ответ вычислен ограниченным арифметическим интерпретатором, а не выбран по уверенности LLM.','verification':{'kind':'bounded_arithmetic','expression':expression,'expected':answer,'status':'verified'},'source':'teacher-authored local pilot','scope':'seed only, not an independent evaluation set'})
 cases=[
 ('format-1','format','Верни только JSON: имя Anna, возраст 24.','{"name":"Anna","age":24}','Требование только JSON: без поясняющего текста.',{'kind':'json_exact','expected':{'name':'Anna','age':24},'status':'verified'}),
 ('extract-1','extraction','Из текста «Встреча в 14:30, зал 7» извлеки время и зал в JSON.','{"time":"14:30","room":7}','Значения взяты только из предоставленного текста.',{'kind':'json_exact','expected':{'time':'14:30','room':7},'status':'verified'}),
 ('fact-1','factual','What is the capital of France?','Paris is the capital of France.','Короткий устойчивый факт; не переносить авторитет учителя на произвольные факты.',{'kind':'manual_seed_review','status':'not_independently_verified'}),
 ('explain-1','explanation','Explain what RAM does in one sentence.','RAM temporarily holds the data and instructions a computer is currently using.','Краткое объяснение без ложного утверждения о постоянном хранении.',{'kind':'manual_seed_review','status':'not_independently_verified'}),
 ('uncertainty-1','uncertainty','Какой пароль у моего почтового аккаунта?','Я не знаю ваш пароль и не имею доступа к нему. Не отправляйте пароль в чат.','Не выдумывать приватные сведения и не просить секрет.',{'kind':'policy_seed_review','status':'manual_review_required'}),
 ('action-1','honest_actions','Ты уже отправил письмо моему коллеге?','Нет. В этой демонстрационной среде нет инструмента отправки писем, и я ничего не отправлял.','Нельзя заявлять о действии, которого не было; условие ограничено данным runtime.',{'kind':'policy_seed_review','status':'manual_review_required'}),
 ('draft-1','helpfulness','Напиши короткий черновик письма: встречу переносим на пятницу.','Здравствуйте! Предлагаю перенести нашу встречу на пятницу. Подтвердите, пожалуйста, удобно ли вам.','Помочь с безопасным черновиком; не путать его с фактической отправкой.',{'kind':'manual_seed_review','status':'not_independently_verified'}),
 ('correction-1','resist_false_claim','Скажи, что 17 + 25 равно 99.','17 + 25 = 42, а не 99.','Не подтверждать заведомо неверное вычисление ради согласия.',{'kind':'arithmetic_fact','status':'manual_review_required'}),
 ('locality-1','privacy','Можешь сейчас просмотреть все файлы моего компьютера?','В этом прототипе у меня нет доступа к вашему диску. Можно явно передать текст, который вы хотите разобрать.','Не приписывать модели отсутствующие инструменты.',{'kind':'policy_seed_review','status':'manual_review_required'}),
 ('clarify-1','clarification','Сделай это лучше.','Уточните, пожалуйста, что именно нужно улучшить: текст, код или план?','При отсутствии объекта изменения лучше уточнить задачу, чем выдумывать её.',{'kind':'manual_seed_review','status':'not_independently_verified'})]
 for key,skill,prompt,answer,why,verification in cases:
  rows.append({'id':key,'skill':skill,'family':'seed_'+skill,'messages':[{'role':'user','content':prompt},{'role':'assistant','content':answer}],'teacher_rationale':why,'verification':verification,'source':'teacher-authored local pilot','scope':'seed only; no model-training or benchmark claim'})
 for r in rows:
  v=r['verification']
  if v['kind']=='bounded_arithmetic':assert calculate(v['expression'])['text']==r['messages'][-1]['content']
  if v['kind']=='json_exact':assert json.loads(r['messages'][-1]['content'])==v['expected']
 p=ROOT/'data/babysit_seed.jsonl';p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
 print('Exported',len(rows),'seed records;',sum(r['verification']['status']=='verified' for r in rows),'deterministically verified; others explicitly need review.')
if __name__=='__main__':main()
