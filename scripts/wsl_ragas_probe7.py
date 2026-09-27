import inspect

from ragas import Experiment

print(inspect.signature(Experiment.__init__))
print([m for m in dir(Experiment) if "run" in m.lower() or "score" in m.lower()])
print(inspect.signature(Experiment.run))
