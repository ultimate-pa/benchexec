# This file is part of BenchExec, a framework for reliable benchmarking:
# https://github.com/sosy-lab/benchexec
#
# SPDX-FileCopyrightText: 2007-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import subprocess
import re
import benchexec.util as util
import benchexec.tools.smtlib2
import logging
import json

class Tool(benchexec.tools.smtlib2.Smtlib2Tool):
    """
    Tool info for SMTInterpol.
    """

    def executable(self):
        return util.find_executable("java")

    def version(self, executable):
        stderr = subprocess.run(
            self.cmdline(executable, ["-version"], []),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        ).stderr
        line = next(
            line for line in stderr.splitlines() if line.startswith("SMTInterpol")
        )
        line = line.replace("SMTInterpol", "")
        return line.strip()

    def name(self):
        return "SMTInterpol"

    def cmdline(self, executable, options, tasks, propertyfile=None, rlimits={}):
        assert len(tasks) <= 1, "only one inputfile supported"
        return [executable, "-jar", "smtinterpol.jar"] + options + tasks

    def get_value_from_output(self, output, identifier):
        try:
            val = json.loads(identifier)
        except json.decoder.JSONDecodeError as ex:
            raise AssertionError(f'Invalid JSON: "{identifier}". Should be {{ "Type" : "<FirstMatch>|<LastMatch>", "Expr": "<regexp>" }}')

        mode = val.get('Type','FirstMatch')
        expr = val['Expr']
        if 'FirstMatch' == mode:
            return self._get_value_from_output_regex(mode, output, expr)
        elif 'LastMatch' == mode:
            return self._get_value_from_output_regex(mode, reversed(output), expr)
        else:
            raise AssertionError(f"Unknown column mode {mode}")

    def _get_value_from_output_regex(self, mode, output, expr):
        regex = re.compile(expr)
        i=0
        for line in output:
            i=i+1
            match = regex.search(line)
            if match and len(match.groups()) > 0:
                return match.group(1)
        logging.debug(f"Did not find a match with regex {expr} and mode {mode} in {i} lines")
        return None
    

