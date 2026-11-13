import sys
sys.path.insert(0,'d:/QuantPortfolio')
from backend.quant.mvo import _build_class_constraints
import inspect
src = inspect.getsource(_build_class_constraints)
print('Has max_scale:', 'max_scale' in src)
print('Has effective_max:', 'effective_max' in src)
print('File:', sys.modules['backend.quant.mvo'].__file__)
