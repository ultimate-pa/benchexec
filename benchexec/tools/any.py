"""
BenchExec is a framework for reliable benchmarking.
This file is part of BenchExec.

Copyright (C) 2020 Daniel Dietsch (dietsch@informatik.uni-freiburg.de)
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
import os

import benchexec.result as result
import benchexec.tools.template
import benchexec.util as util


class MissingEnvironmentVariable(benchexec.BenchExecException):
    """
    Raised when an environment variable, e.g., BENCHEXEC_ANYTOOL_EXE, is not set.
    """

    pass


class Tool(benchexec.tools.template.BaseTool2):
    """
    An implementation that can be used for any tool on-the-fly.
    You just need to set the environment variable BENCHEXEC_ANYTOOL_EXE to a path to the actual tool and then all
    options will be passed to the tool.

    The result is RESULT_DONE if the return code is zero, otherwise it is a custom string.
    """

    REQUIRED_PATHS = []

    def executable(self, tool_locator):
        executable = os.environ["BENCHEXEC_ANYTOOL_EXE"]
        if executable:
            return executable
        raise MissingEnvironmentVariable("BENCHEXEC_ANYTOOL_EXE")

    def name(self):
        return os.environ["BENCHEXEC_ANYTOOL_EXE"]

    def cmdline(self, executable, options, task, resource_limits):
        return [executable] + options + [*task.input_files]

    def determine_result(self, run):
        output = run.output
        exit_code = run.exit_code
        if not output:
            if run.was_timeout and not exit_code.signal:
                return "Timeout"
            if run.was_timeout:
                return "Timeout by {}".format(exit_code.signal)
            if exit_code.signal:
                return "Terminated by {}".format(exit_code.signal)
            return result.RESULT_UNKNOWN
        last_line = output[-1:][0]
        if any(s in last_line for s in ["YES", "TRUE", "Termination successfully shown!"]):
            return result.RESULT_TRUE_PROP
        elif any(s in last_line for s in ["FALSE","NO"]):
            return result.RESULT_FALSE_TERMINATION
        else:
            return last_line
