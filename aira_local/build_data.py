"""Authored synthetic pilot only; templates assigned to splits BEFORE training."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parent


def build():
 rows=[]
 def add(split,target,family,prompts):
  for text in prompts:rows.append({'prompt':text,'target':target,'split':split,'family':family,'source':'offline authored pilot by Arena agent','why':{'calculator':'Явный запрос вычислить арифметическое выражение; ответ проверяет ограниченный калькулятор.','notes':'Явный поиск в предоставленных заметках; не общий вопрос о памяти.','chat':'Не поддерживаемая команда инструмента: нужен языковой ответ, а не выдуманный результат действия.'}[target]})
 expr=['17 + 25','(12 + 8) * 3','144 / 12','9 * 7 - 4','2 ** 5','100 - 37']
 for i,t in enumerate(['Посчитай {x}','Вычисли {x}','Сколько будет {x}?','Дай результат: {x}','Calculate {x}','Evaluate {x}','Compute {x}','What is {x}?']):add('train','calculator',f'calc_train_{i}',[t.format(x=x) for x in expr])
 for i,t in enumerate(['Пожалуйста, посчитай: {x}','I need the value of {x}']):add('development','calculator',f'calc_dev_{i}',[t.format(x=x) for x in ['31+19','7*8','(18-6)/3','2**4','17-29','80/5']])
 for i,t in enumerate(['Мне нужен результат выражения {x}','Please work out {x}']):add('holdout','calculator',f'calc_test_{i}',[t.format(x=x) for x in ['46+18','11*9','(32+8)/5','3**3','72-89','81/9']])
 topics=['план проекта','лимит памяти','обучение','железо','датасет','цель AIra']
 for i,t in enumerate(['Найди в моих заметках {q}','Поищи в заметках {q}','Что написано в моей записи про {q}?','Открой заметку про {q}']):add('train','notes',f'notes_train_ru_{i}',[t.format(q=q) for q in topics])
 en=['project plan','RAM budget','training','hardware','dataset','AIra goals']
 for i,t in enumerate(['Search my notes for {q}','Find my note about {q}','Look up {q} in my notes','What do my notes say about {q}?']):add('train','notes',f'notes_train_en_{i}',[t.format(q=q) for q in en])
 for i,t in enumerate(['Поищи запись о {q}','Look in my notebook for {q}']):add('development','notes',f'notes_dev_{i}',[t.format(q=q) for q in (topics if i==0 else en)])
 for i,t in enumerate(['Сверься с моими заметками: {q}','Search the local notebook for {q}']):add('holdout','notes',f'notes_test_{i}',[t.format(q=q) for q in (topics if i==0 else en)])
 chats={
 'train':[
 ['Привет','Добрый вечер','Как дела?','Hello','Hi there','Good morning','Спасибо за помощь','Thank you','Кто ты?','What can you do?','Расскажи о себе','Как тебя зовут?'],
 ['Что такое оперативная память?','Почему небо голубое?','Объясни, как работает калькулятор','Зачем людям нужны заметки?','Что такое нейросеть?','Что такое обучение модели?','Explain what RAM is','What is a calculator?','How does human memory work?','Why do people take notes?','Explain machine learning','What is a CPU?'],
 ['Напиши короткое письмо','Придумай название проекта','Дай три идеи для прогулки','Составь список продуктов','Расскажи шутку','Переведи слово hello','Write a short email','Suggest a name for a project','Tell me a joke','Translate hello into French','List three colors','Explain this sentence'],
 ['Не вычисляй 2+2, расскажи про числа','Мне не нужен поиск в заметках, объясни память','Запомни мое имя','Удалишь файлы с моего компьютера?','Сколько слов в этом предложении?','Расскажи про число 42','Do not calculate: explain addition','What does the word compute mean?','Write a note about learning','Remember my favorite color','How many people live on Earth?','Tell me about project management']],
 'development':[
 ['Рад тебя видеть','Поздоровайся со мной','Можешь объяснить фотосинтез?','Что означает слово inference?','Предложи тему рассказа','Чем процессор отличается от памяти?'],
 ['Can you help me write a message?','Explain photosynthesis briefly','Say hello to me','What is the difference between CPU and RAM?','Suggest a story idea','Why are computers useful?']],
 'holdout':[
 ['Здравствуй, помощник','Хочу поговорить о музыке','Объясни слово квантизация','Сочини маленькое поздравление','Почему у компьютера шумит вентилятор?','Не ищи заметку, объясни что такое память'],
 ['Nice to meet you','Tell me something about music','Explain quantization simply','Write a birthday greeting','Why does a computer fan get loud?','Do not search notes; explain computer memory']]
 }
 for split,groups in chats.items():
  for i,prompts in enumerate(groups):add(split,'chat',f'chat_{split}_{i}',prompts)
 out=ROOT/'data/router_pilot.jsonl';out.parent.mkdir(exist_ok=True)
 out.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
 assert len({r['prompt'] for r in rows})==len(rows)
 counts={s:sum(r['split']==s for r in rows) for s in ('train','development','holdout')}
 manifest={'scope':'small authored synthetic intent-routing pilot, not language capability or real user distribution','split_unit':'prompt template/family','counts':counts,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'holdout_used_for_training':False}
 (ROOT/'data/router_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps(manifest,indent=2))
if __name__=='__main__':build()
