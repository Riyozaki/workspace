"""Engineering promotion guard; development is NOT an independent final test."""

def non_regression(before,after):
 return (after['accuracy']>=before['accuracy']-1e-12
         and after['macro_f1']>=before['macro_f1']-1e-12
         and after['wrong_fast_paths']<=before['wrong_fast_paths'])
