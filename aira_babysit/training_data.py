"""Token/loss-mask contract shared by export and GPU trainer; pure-Python tests."""

def encode_record(record,tokenizer,max_length=512):
 messages=record['messages']
 if not messages or messages[-1]['role']!='assistant':raise ValueError('Teacher target must be final assistant turn')
 prompt=tokenizer.apply_chat_template(messages[:-1],tokenize=True,add_generation_prompt=True)
 target=tokenizer(messages[-1]['content'],add_special_tokens=False)['input_ids']
 eos=tokenizer.eos_token_id
 if eos is None or not target:raise ValueError('Missing EOS or empty supervised target')
 target=target+[eos];ids=list(prompt)+list(target)
 if len(ids)>max_length:raise ValueError('Record exceeds frozen context budget; do not silently truncate/drop hard targets')
 labels=[-100]*len(prompt)+target
 assert any(x!=-100 for x in labels)
 return {'input_ids':ids,'attention_mask':[1]*len(ids),'labels':labels}


def pad_batch(rows,pad_id):
 if not rows:raise ValueError('Empty training batch')
 n=max(len(r['input_ids']) for r in rows);out={k:[] for k in ('input_ids','attention_mask','labels')}
 for r in rows:
  p=n-len(r['input_ids']);out['input_ids'].append(r['input_ids']+[pad_id]*p);out['attention_mask'].append(r['attention_mask']+[0]*p);out['labels'].append(r['labels']+[-100]*p)
 return out
