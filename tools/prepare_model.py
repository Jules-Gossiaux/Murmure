"""Prepare the default local model without starting the desktop UI."""

from murmure.engine import Engine
from murmure.storage import data_directory

engine = Engine(data_directory())
print(engine.load("base", print), flush=True)
print("Model ready", flush=True)
