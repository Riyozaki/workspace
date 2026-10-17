import numpy as np
from competition50x import data,request_data


def test_identical_validation_decoder():
 a,y=data.load_split('validation');b,z=request_data.load_split('validation')
 np.testing.assert_array_equal(a,b);np.testing.assert_array_equal(y,z)
