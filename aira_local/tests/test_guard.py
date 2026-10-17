from aira_local.guard import non_regression


def test_rejects_a_corrected_example_if_general_development_regresses():
 before={'accuracy':.805555,'macro_f1':.787,'wrong_fast_paths':0}
 after={'accuracy':.722222,'macro_f1':.725,'wrong_fast_paths':0}
 assert not non_regression(before,after)


def test_guard_checks_quality_and_wrong_actions_not_only_training_fit():
 before={'accuracy':.8,'macro_f1':.79,'wrong_fast_paths':0}
 assert non_regression(before,dict(before))
 assert non_regression(before,{'accuracy':.9,'macro_f1':.85,'wrong_fast_paths':0})
 assert not non_regression(before,{'accuracy':.9,'macro_f1':.85,'wrong_fast_paths':1})
 assert not non_regression(before,{'accuracy':.9,'macro_f1':.78,'wrong_fast_paths':0})
