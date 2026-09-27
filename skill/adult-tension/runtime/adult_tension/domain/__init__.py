"""Pure domain layer: no I/O, no system time, no global randomness.

Only standard-library modules without side effects are imported here
(json, hashlib, re, math); tests enforce this.
"""
