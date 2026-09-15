"""Deja importar board/snake_ai/run directo desde los tests, sin repetir
el sys.path.insert en cada archivo."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
