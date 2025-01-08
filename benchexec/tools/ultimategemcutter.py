# This file is part of BenchExec, a framework for reliable benchmarking:
# https://github.com/sosy-lab/benchexec
#
# SPDX-FileCopyrightText: 2016-2021 Daniel Dietsch <dietsch@informatik.uni-freiburg.de>
# SPDX-FileCopyrightText: 2016-2020 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

from benchexec.tools import ultimate


class Tool(ultimate.UltimateTool):
    """
    This is the tool info module for ULTIMATE GemCutter.

    You can download the latest release from GitHub or build the latest development snapshot by following the
    instructions at https://github.com/ultimate-pa/ultimate/wiki/Usage

    Please report any issues to our issue tracker at https://github.com/ultimate-pa/ultimate/issues

    Latest release: https://github.com/ultimate-pa/ultimate/releases/latest
    Git repository: https://github.com/ultimate-pa/ultimate.git
    """

    def name(self):
        return "ULTIMATE GemCutter"
