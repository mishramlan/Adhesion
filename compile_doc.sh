#!/usr/bin/env bash
source venv/bin/activate
source env.sh
python setup.py build
cd docs/
rm -rf source/
sphinx-apidoc -o source/ ../Adhesion
make html
open Adhesion/docs/_build/html/index.html