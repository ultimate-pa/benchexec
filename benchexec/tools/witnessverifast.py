#!/usr/bin/python3

import benchexec.tools.template
import benchexec.result as result
import logging
import re

class Tool(benchexec.tools.template.BaseTool2):
    """
    """

    def executable(self, tool_locator):
        script = tool_locator.find_executable("verifast-validate-witness.sh")
        #conversion = tool_locator.find_executable("instrument_program_cli.py")
        #verifast = tool_locator.find_executable("verifast")
        return script

    def name(self):
        return "witnessverifast"

    def cmdline(self, executable, options, task, rlimits):
        witness_index = options.index('witness')
        if witness_index is not None and len(options) > witness_index + 1:
            witness = options[witness_index + 1]
            options.pop(witness_index + 1)
            options.pop(witness_index)
        else:
            raise UnsupportedFeatureException(f"invalid options: {options}")
        return [executable, *task.input_files_or_empty, witness]

    def determine_result(self, run):
        if run.exit_code.value is not None:
            if run.exit_code.value == 0:
                return result.RESULT_TRUE_PROP
            for line in run.output:
                if "Cannot prove condition" in line:
                    return f"{result.RESULT_FALSE_PROP}(Cannot prove condition)"
                if "Parse error" in line:
                    return f"{result.RESULT_ERROR}(Parse error)"
                if "Duplicate function prototype" in line:
                    return f"{result.RESULT_ERROR}(Duplicate function prototype)"
                if "No such variable, constructor, regular function, predicate, enum element, global variable, or module" in line:
                    return f"{result.RESULT_ERROR}(No such variable, constructor, regular function, predicate, enum element, global variable, or module)"
                if "Non-void function does not return a value" in line:
                    return f"{result.RESULT_ERROR}(Non-void function does not return a value)"
                if "Contract required" in line:
                    return f"{result.RESULT_ERROR}(Contract required)"
                if "Loop invariant required" in line:
                    return f"{result.RESULT_ERROR}(Loop invariant required)"
                if "Type mismatch. Actual:" in line:
                    return f"{result.RESULT_ERROR}(Type mismatch)"
                if "Traceback (most recent call last):" in line:
                    return f"{result.RESULT_ERROR}(Python crash)"
            return result.RESULT_ERROR

    def get_value_from_output(self, output, identifier):
        regex = re.compile(identifier)
        for line in output:
            match = regex.search(line)
            if match and len(match.groups()) > 0:
                return match.group(1)
        logging.debug("Did not find a match with regex %s", identifier)
        return None

