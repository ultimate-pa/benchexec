#!/usr/bin/env python3
"""
BenchExec is a framework for reliable benchmarking.
This file is part of BenchExec.

Copyright (C) 2007-2015  Dirk Beyer
All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import sys
sys.dont_write_bytecode = True # prevent creation of .pyc files

"""
Main script of BenchExec for executing a whole benchmark (suite).

This script can be called from the command line.
For integrating from within Python instantiate the benchexec.BenchExec class
and either call "instance.start()" or "benchexec.main(instance)".
"""

import benchexec

benchexec.main()
