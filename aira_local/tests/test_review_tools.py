import pytest
from aira_local.tools import extract_expression,calculate,CalculatorError
from aira_local.router import BudgetRouter


@pytest.mark.parametrize('prompt,value',[
 ('Посчитай -3+5',2),('-3*7',-21),('Сколько будет −3 × 7?',-21),
 ('Calculate 1e3 + 2',1002),('Вычисли 8 ÷ 2',4),('What is (2+3)*4?',20),
 ('42',42),('Пожалуйста, посчитай: 144/12',12),('Дай результат: (12+8)*3',60),
 ('Мне нужен результат выражения -4+2',-2),
])
def test_single_complete_expression_preserves_sign_and_operands(prompt,value):
 assert calculate(extract_expression(prompt))['value']==value


@pytest.mark.parametrize('prompt',['Посчитай 2+2 и 3+3','Compute 2+2 then multiply by 5','Посчитай 1,5 + 2,5','Дата 2026-10-17 и 2+2',"open('file')",'2+2 apples'])
def test_ambiguous_or_non_math_text_is_rejected(prompt):
 with pytest.raises(CalculatorError):extract_expression(prompt)


def test_invalid_router_checkpoint_fails_cleanly(tmp_path):
 p=tmp_path/'bad.json';p.write_text('{"kind":"linear","seed":0,"threshold":0.9,"dimension":512,"labels":["chat","calculator","notes"],"params":{"w":[1],"b":[0,0,0]}}')
 with pytest.raises(ValueError):BudgetRouter.load(p)


def test_checkpoint_write_is_atomic_and_roundtrips(tmp_path,monkeypatch):
 m=BudgetRouter();p=tmp_path/'checkpoint.json';m.save(p);old=p.read_bytes()
 def fail_replace(self,target):raise OSError('simulated write failure')
 monkeypatch.setattr(type(p),'replace',fail_replace)
 with pytest.raises(OSError):m.save(p)
 assert p.read_bytes()==old;assert not list(tmp_path.glob('*.tmp'))
