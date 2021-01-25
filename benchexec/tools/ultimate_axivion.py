# BenchExec is a framework for reliable benchmarking.
# This file is part of BenchExec.
#
# Copyright (C) 2007-2015  Dirk Beyer
# All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import functools
import logging
import os
import re
import subprocess
import tempfile

import benchexec.result as result
import benchexec.tools.template
import benchexec.util as util


class UnsupportedFeatureException(benchexec.BenchExecException):
    """
    Raised when a tool or its tool-info module does not support a requested feature.
    """

    pass


class Tool(benchexec.tools.template.BaseTool):
    """
    This is the tool-info module for Axivion Ultimate
    """

    REQUIRED_PATHS = []
    """
    List of path patterns that is used by the default implementation of program_files().
    Not necessary if this method is overwritten.
    """

    @functools.lru_cache()
    def executable(self):
        return util.find_executable("rfgscript")

    @functools.lru_cache()
    def __cafe_cc(self):
        return util.find_executable("cafeCC")

    @functools.lru_cache()
    def version(self, executable):
        """
        Determine a version string for this tool, if available.
        @return the version of Bauhaus and the version of Ultimate
        """

        axivion_version_cmd = [
            executable,
            "-c",
            "import bauhaus.shared; print(bauhaus.shared.get_version_number())",
        ]

        # looks like this: (7, 0, 0, 4283)
        axivion_version_raw = self._version_from_tool(axivion_version_cmd)
        axivion_version_str = "_".join(
            [
                i.replace("(", "").replace(")", "").replace(" ", "")
                for i in axivion_version_raw.split(sep=",")
            ]
        )

        # for final tool info module methods we should integrate an alternate --version command into ultimate axivion
        # that already generates the shared version
        java_path = os.environ["ULTIMATE_JAVA"]
        ult_path = os.environ["ULTIMATE_DIR"]

        ult_version_cmd = [
            java_path,
            "-Xss4m",
            "-jar",
            os.path.join(
                ult_path,
                "plugins/org.eclipse.equinox.launcher_1.5.800.v20200727-1323.jar",
            ),
            "-data",
            "@noDefault",
            "-ultimatedata",
            os.path.join(ult_path, "data"),
            "--version",
        ]
        ult_version_raw = self._version_from_tool(ult_version_cmd)
        match = re.compile(r"^This is Ultimate (.*)$", re.MULTILINE).search(
            ult_version_raw
        )
        return axivion_version_str + "/" + match.group(1)

    def _version_from_tool(self, popen_arg):
        """
        Get version of a tool by executing it with argument "--version"
        and returning stdout.
        @return a (possibly empty) string of output of the tool
        """
        try:
            process = subprocess.Popen(
                popen_arg, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            (stdout, stderr) = process.communicate()
        except OSError as e:
            logging.warning(
                "Cannot run {0} to determine version: {1}".format(popen_arg, e.strerror)
            )
            return ""
        if process.returncode:
            logging.warning(
                "Cannot determine {0} version, exit code {1}".format(
                    popen_arg, process.returncode
                )
            )
            return ""

        return util.decode_to_string(stdout).strip()

    def name(self):
        """
        Return the name of the tool, formatted for humans.
        This function should always be overriden.
        @return a non-empty string
        """
        return "Ultimate Axivion"

    def cmdline(self, executable, options, tasks, propertyfile=None, rlimits={}):
        """
        Compose the command line to execute from the name of the executable,
        the user-specified options, and the inputfile to analyze.
        This method can get overridden, if, for example, some options should
        be enabled or if the order of arguments must be changed.

        All paths passed to this method (executable, tasks, and propertyfile)
        are either absolute or have been made relative to the designated working directory.

        @param executable: the path to the executable of the tool (typically the result of executable())
        @param options: a list of options, in the same order as given in the XML-file.
        @param tasks: a list of tasks, that should be analysed with the tool in one run.
                            A typical run has only one input file, but there can be more than one.
        @param propertyfile: contains a specification for the verifier (optional, not always present).
        @param rlimits: This dictionary contains resource-limits for a run,
                        for example: time-limit, soft-time-limit, hard-time-limit, memory-limit, cpu-core-limit.
                        All entries in rlimits are optional, so check for existence before usage!
        @return a list of strings that represent the command line to execute
        """
        if len(tasks) == 1:
            input_file = tasks[0]
            (input_dir, input_file_name) = os.path.split(input_file)
            temp_dir = str(tempfile.TemporaryDirectory().name)
            ir_file = os.path.join(temp_dir, input_file_name + ".ir")
            axivion_analysis = self.__which("axivion_analysis")

            mini_script = """#!/bin/bash
cat {prop_file}
"{cafe_cc}" -B "{input_dir}" -o "{ir_file}" -n "{temp_dir}" "{input_file}"
"{axivion_analysis}" --ir "{ir_file}"
""".format(
                cafe_cc=self.__cafe_cc(),
                input_dir=input_dir,
                ir_file=ir_file,
                temp_dir=temp_dir,
                input_file=input_file,
                axivion_analysis=axivion_analysis,
                prop_file=propertyfile,
            )

            mini_script_file = tempfile.NamedTemporaryFile(delete=False)
            with open(mini_script_file.name, "w") as f:
                f.write(mini_script)

            os.chmod(mini_script_file.name, 0o777)
            mini_script_file.file.close()
            # Note that we only add options and tasks so that we can see them in the tables.
            # The script ignores them completely
            call = [mini_script_file.name] + options + tasks
            return call + [propertyfile] if propertyfile else call
        raise UnsupportedFeatureException(
            "{} does not support {} input files.".format(self.name(), len(tasks))
        )

    def determine_result(self, returncode, returnsignal, output, isTimeout):
        """
        Parse the output of the tool and extract the verification result.
        If the tool gave a result, this method needs to return one of the
        benchexec.result.RESULT_* strings.
        Otherwise an arbitrary string can be returned that will be shown to the user
        and should give some indication of the failure reason
        (e.g., "CRASH", "OUT_OF_MEMORY", etc.).
        For tools that do not output some true/false result, benchexec.result.RESULT_DONE
        can be returned.

        @param returncode: the exit code of the program, 0 if the program was killed
        @param returnsignal: the signal that killed the program, 0 if program exited itself
        @param output: a list of strings of output lines of the tool (both stdout and stderr)
        @param isTimeout: whether the result is a timeout
        (useful to distinguish between program killed because of error and timeout)
        @return a non-empty string, usually one of the benchexec.result.RESULT_* constants
        """

        if isTimeout and returnsignal == 0:
            return "Timeout({})".format(returncode)
        if isTimeout:
            return "Timeout({}) by {}".format(returncode, returnsignal)
        if returnsignal != 0:
            return "Terminated({}) by {}".format(returncode, returnsignal)

        is_valid_deref = any(["LTL(G valid-deref)" in prp for prp in output])
        is_valid_free = any(["LTL(G valid-free)" in prp for prp in output])
        is_valid_memtrack = any(["LTL(G valid-memtrack)" in prp for prp in output])
        is_valid_memcleanup = any(["LTL(G valid-memcleanup)" in prp for prp in output])

        re_other_errors = re.compile(
            "error:.*possibly released by call to.*is a stack object"
        )

        for idx, line in enumerate(output):
            if "Number of compiler messages:" in line:
                next = self.__try_get(output, idx + 1)
                if next and "Number of errors:" in next:
                    return "cafeCC errors: {}".format(int(next.split(":")[1]))
            if is_valid_deref:
                if "error: Pointer may be NULL at dereference" in line:
                    return result.RESULT_FALSE_DEREF
                if "error: Pointer is NULL at dereference" in line:
                    return result.RESULT_FALSE_DEREF
            if is_valid_free:
                if (
                    "error: Dynamic memory released here possibly already released earlier"
                    in line
                ):
                    return result.RESULT_FALSE_FREE
                if (
                    "error: Dynamic memory possibly used after it was previously released"
                    in line
                ):
                    return result.RESULT_FALSE_FREE
            if is_valid_memtrack:
                if "error: Call allocates possibly leaking memory" in line:
                    return result.RESULT_FALSE_MEMTRACK

            if re_other_errors.match(line):
                return result.RESULT_FALSE_PROP

        if is_valid_memcleanup:
            return result.RESULT_UNKNOWN
        return result.RESULT_TRUE_PROP

    @staticmethod
    def __try_get(l, idx):
        return l[idx] if idx < len(l) else None

    @staticmethod
    def __which(program):
        def is_exe(file_path):
            return os.path.isfile(file_path) and os.access(file_path, os.X_OK)

        file_path, file_name = os.path.split(program)
        if file_path:
            if is_exe(program):
                return program
        else:
            for path in os.environ["PATH"].split(os.pathsep):
                exe_file = os.path.join(path, program)
                if is_exe(exe_file):
                    return exe_file
        return None
