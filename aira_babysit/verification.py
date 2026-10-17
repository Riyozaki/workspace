"""Independent fixed checks. Student output is data, never code or a policy edit."""
import json,re


def verify(task,text):
 spec=task['verification'];s=str(text).strip()
 if spec['kind']=='integer_exact':
  ok=bool(re.fullmatch(r'-?\d+',s)) and s==spec['expected'];reason='exact integer and output format' if ok else 'wrong integer or extra/missing text'
 elif spec['kind']=='json_exact':
  try:value=json.loads(s);ok=type(value) is dict and value==spec['expected'] and set(value)==set(spec['expected']) and type(value.get('age')) is int
  except (ValueError,TypeError):ok=False
  reason='exact grounded JSON' if ok else 'invalid JSON, invented fields or wrong source values'
 else:raise ValueError('Unsupported verifier')
 return {'pass':bool(ok),'reason':reason,'verifier':spec['kind'],'quality_scope':'verified synthetic task only'}


def teacher_record(task,student_answer):
 if not verify(task,task['teacher_target'])['pass']:raise RuntimeError('Teacher target failed its fixed verifier')
 return {'task_id':task['id'],'family':task['family'],'skill':task['skill'],'messages':task['messages']+[{'role':'assistant','content':task['teacher_target']}],'student_answer':student_answer,'teacher_rationale':task['teacher_rationale'],'teacher_provider':'verified_offline','teacher_is_strong_llm':False,'verified':True,'verification':task['verification'],'source':'programmatically verified synthetic pilot; not general teacher intelligence'}
