"""Files the builder copies to the site verbatim, shipped as package data.

A package rather than a bare directory so `importlib.resources` can address it, which is what
makes the read work from an installed wheel as well as from a checkout.
"""
