import pytest
from aira_local.tools import calculate,extract_expression,CalculatorError,search_notes


@pytest.mark.parametrize('expr,value',[('2+2',4),('(18+7)*4',100),('144/12',12),('-3*7',-21),('2**5',32),('7%3',1),('2**-2',.25)])
def test_safe_arithmetic(expr,value):assert calculate(expr)['value']==value


@pytest.mark.parametrize('expr',["__import__('os').system('id')",'open("x")','(1).__class__','[x for x in range(10)]','True+1','10**99','9**9**9','1/0','1e100','float("nan")','x+3'])
def test_arithmetic_rejects_code_and_unbounded_work(expr):
 with pytest.raises(CalculatorError):calculate(expr)


def test_extract():assert calculate(extract_expression('Посчитай (18 + 7) * 4'))['value']==100


def test_notes_not_a_filesystem():
 notes=[{'id':'a','title':'План обучения','text':'Обучение позже на Kaggle'},{'id':'b','title':'Память','text':'Лимит RAM'}]
 assert search_notes('Найди в заметках план обучения',notes)[0]['id']=='a'
 assert search_notes('unicorns',notes)==[]
