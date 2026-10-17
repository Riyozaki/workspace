"""Explicit deterministic tools. They do NOT pretend to be language-model skill."""
import ast,math,re


class CalculatorError(ValueError):pass


def calculate(expression):
 if not isinstance(expression,str) or len(expression)>180:raise CalculatorError('Выражение слишком длинное')
 try:tree=ast.parse(expression.strip(),mode='eval')
 except (SyntaxError,ValueError):raise CalculatorError('Нужна обычная арифметика: (12 + 8) * 3')
 if sum(1 for _ in ast.walk(tree))>45:raise CalculatorError('Слишком сложное выражение')
 def solve(node):
  if isinstance(node,ast.Expression):return solve(node.body)
  if isinstance(node,ast.Constant) and type(node.value) in (int,float):
   if abs(node.value)>1e9:raise CalculatorError('Слишком большое число')
   return node.value
  if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
   x=solve(node.operand);return x if isinstance(node.op,ast.UAdd) else -x
  if isinstance(node,ast.BinOp):
   a,b=solve(node.left),solve(node.right)
   try:
    if isinstance(node.op,ast.Add):v=a+b
    elif isinstance(node.op,ast.Sub):v=a-b
    elif isinstance(node.op,ast.Mult):v=a*b
    elif isinstance(node.op,ast.Div):v=a/b
    elif isinstance(node.op,ast.FloorDiv):v=a//b
    elif isinstance(node.op,ast.Mod):v=a%b
    elif isinstance(node.op,ast.Pow):
     if abs(b)>6 or abs(a)>1e6:raise CalculatorError('Степень вне безопасного бюджета')
     v=a**b
    else:raise CalculatorError('Оператор не поддерживается')
   except (ArithmeticError,OverflowError) as exc:raise CalculatorError('Недопустимая арифметическая операция') from exc
   if type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1e12:raise CalculatorError('Результат вне бюджета')
   return v
  raise CalculatorError('Имена, вызовы, доступ к файлам и код запрещены')
 result=solve(tree)
 return {'expression':expression.strip(),'value':result,'text':str(int(result)) if result==int(result) else format(result,'.10g'),'source':'bounded Python AST arithmetic; not neural reasoning'}


def extract_expression(text):
 # Parse one complete expression after an explicit command. Never pick the
 # longest numeric substring: that silently dropped unary minus/other operands.
 if not isinstance(text,str):raise CalculatorError('Нужна строка выражения')
 t=text.strip().translate(str.maketrans({'−':'-','–':'-','×':'*','÷':'/'}))
 if re.search(r'\b(?:__\w+|import|eval|exec|open)\b',t,re.I):raise CalculatorError('Код не исполняется')
 prefix=r'^(?:(?:пожалуйста[, ]+)?(?:посчитай|вычисли|сосчитай(?: пожалуйста)?|сколько будет|дай результат|мне нужен результат выражения)|please work out|i need the value of|calculate|compute|evaluate|what is)\b\s*[:=]?\s*'
 t=re.sub(prefix,'',t,flags=re.I).strip().rstrip(' ?=')
 if ',' in t:raise CalculatorError('Для десятичных чисел используйте точку; запятые неоднозначны.')
 if not t:raise CalculatorError('Введите выражение, например: «Посчитай (-3+5)*2».')
 try:calculate(t)
 except CalculatorError as exc:
  raise CalculatorError(str(exc)+' Используйте одно выражение, без дополнительного текста.') from exc
 return t


def search_notes(query,notes):
 words={w for w in re.findall(r'[\w]+',query.casefold()) if len(w)>2}
 stop={'найди','заметках','заметки','запись','поищи','своих','моих','search','notes','note','find','about','what','local','notebook','look','the','for','что','про','мне','написано','моей','сверься'}
 words-=stop;ranked=[]
 for note in notes[:8]:
  text=note.get('title','')+' '+note.get('text','');nw=set(re.findall(r'[\w]+',text.casefold()));score=sum(1 for w in words if any(n.startswith(w[:max(3,len(w)-2)]) for n in nw))
  if score:ranked.append((score,note))
 ranked.sort(key=lambda r:r[0],reverse=True)
 return [{'id':n.get('id','note'),'title':n.get('title','Заметка'),'text':n.get('text','')[:900],'matches':score} for score,n in ranked[:3]]
