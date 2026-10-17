"""Narrow verified synthetic TRAINING curriculum. Not a general agent benchmark."""
import random
BOILERPLATE="That's a great way to start. I'm glad you enjoyed that! If you have any more questions, feel free to ask."


def make_tasks(count,seed,split):
 if split not in ('train','development','holdout'):raise ValueError(split)
 rng=random.Random(seed+{'train':0,'development':100000,'holdout':200000}[split]);rows=[]
 for i in range(count):
  kind=('arithmetic','json_extract','topic_shift')[i%3];a=rng.randint(2,80);b=rng.randint(2,50)
  if kind in ('arithmetic','topic_shift'):
   op=rng.choice(('+','-','*'));expected={'+':a+b,'-':a-b,'*':a*b}[op];expr=f'{a} {op} {b}'
   templates={'train':['Посчитай {e}. Ответь только числом.','Calculate {e}. Return only the number.'],'development':['Мне нужен только численный результат {e}.','Give just the numeric value of {e}.'],'holdout':['Вычисли значение выражения {e}; без пояснений.','Return one number: the result of {e}.']}[split]
   prompt=rng.choice(templates).format(e=expr);history=[]
   if kind=='topic_shift':
    history=[{'role':'user','content':'Hello. Let us start.'},{'role':'assistant','content':BOILERPLATE}]
   verification={'kind':'integer_exact','expected':str(expected)}
   target=str(expected);why='Целочисленный ответ независимо вычислен генератором по явной операции. Вежливая заготовка не отвечает на текущий вопрос.'
  else:
   name=rng.choice(['Anna','Boris','Mira','Leo','Nina']);age=rng.randint(18,70)
   templates={'train':['Return ONLY JSON with keys name and age. Source: {n}, age {a}.','Верни только JSON с ключами name и age: {n}, возраст {a}.'],'development':['Extract name and age as JSON, no other fields: {n}; {a} years old.','Извлеки name и age, только JSON: имя {n}; возраст {a}.'],'holdout':['Output exactly the JSON object for this record: name={n}, age={a}.','Запись: {n}, {a} лет. Нужен только объект JSON name/age.']}[split]
   prompt=rng.choice(templates).format(n=name,a=age);history=[];verification={'kind':'json_exact','expected':{'name':name,'age':age}}
   import json
   target=json.dumps(verification['expected'],ensure_ascii=False,separators=(',',':'));why='Ответ содержит только значения из источника и ровно два требуемых поля. Проверяется JSON parser, не мнение учителя.'
  task={'id':f'{split}-{i:05d}','split':split,'family':f'{split}:{kind}','skill':kind,'messages':history+[{'role':'user','content':prompt}],'verification':verification,'teacher_target':target,'teacher_rationale':why,'source':'generated_verified_training_pilot','limitations':'Synthetic task curriculum, not evidence of general Russian/agent competence.'}
  rows.append(task)
 return rows
