import pytest
from aira_babysit.training_data import encode_record,pad_batch


class TokenizerFixture:
 eos_token_id=255
 def apply_chat_template(self,messages,tokenize=True,add_generation_prompt=True):return list(range(sum(len(x['content']) for x in messages)))+[1,2,3]
 def __call__(self,text,add_special_tokens=False):return {'input_ids':[ord(x)%200 for x in text]}


def test_only_final_teacher_target_is_supervised_even_with_bad_student_history():
 record={'messages':[{'role':'user','content':'Hello'},{'role':'assistant','content':'BAD CLICHE'},{'role':'user','content':'2+2'},{'role':'assistant','content':'4'}]}
 r=encode_record(record,TokenizerFixture());assert r['labels'][-2:]==[ord('4'),255];assert all(x==-100 for x in r['labels'][:-2])


def test_padding_cannot_train_on_pad_or_prompt():
 t=TokenizerFixture();a=encode_record({'messages':[{'role':'user','content':'x'},{'role':'assistant','content':'4'}]},t);b=encode_record({'messages':[{'role':'user','content':'longer'},{'role':'assistant','content':'answer'}]},t)
 batch=pad_batch([a,b],0);assert len(batch['labels'][0])==len(batch['labels'][1]);assert batch['labels'][0][-1]==-100;assert batch['attention_mask'][0][-1]==0


def test_oversized_records_are_not_silently_dropped_or_target_truncated():
 with pytest.raises(ValueError,match='context'):encode_record({'messages':[{'role':'user','content':'x'*300},{'role':'assistant','content':'yes'}]},TokenizerFixture(),max_length=10)


def test_bad_targets_and_missing_eos_fail():
 with pytest.raises(ValueError):encode_record({'messages':[{'role':'user','content':'no target'}]},TokenizerFixture())
 t=TokenizerFixture();t.eos_token_id=None
 with pytest.raises(ValueError):encode_record({'messages':[{'role':'user','content':'x'},{'role':'assistant','content':'4'}]},t)
