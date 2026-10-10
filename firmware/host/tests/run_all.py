"""Run both legacy function tests and unittest cases with the standard library."""
import importlib.util
import inspect
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root.parent))
scratch = tempfile.TemporaryDirectory(prefix="syren-test-fixtures-")
fixture_root = Path(scratch.name) / "fixtures"
shutil.copytree(root / "fixtures", fixture_root)
suite = unittest.TestSuite()
for path in sorted(root.glob('test_*.py')):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if hasattr(module, "FIXTURES"):
        module.FIXTURES = fixture_root
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    for name, function in inspect.getmembers(module, inspect.isfunction):
        if name.startswith('test_'):
            suite.addTest(unittest.FunctionTestCase(function))
result = unittest.TextTestRunner(verbosity=2).run(suite)
scratch.cleanup()
sys.exit(not result.wasSuccessful())
