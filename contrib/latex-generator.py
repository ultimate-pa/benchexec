#!/usr/bin/env python3

# This file is part of BenchExec, a framework for reliable benchmarking:
# https://github.com/sosy-lab/benchexec
#
# SPDX-FileCopyrightText: 2021 Daniel Dietsch <dietsch@informatik.uni-freiburg.de>
#
# SPDX-License-Identifier: Apache-2.0

import argparse
import multiprocessing
import os
import re
import sys
from decimal import InvalidOperation
from collections import Counter, OrderedDict
from functools import partial

from benchexec import tablegenerator
from benchexec.tablegenerator import util

sys.dont_write_bytecode = True  # prevent creation of .pyc files


def escape(mapping, text):
    regex = re.compile(
        "|".join(
            re.escape(str(key))
            for key in sorted(mapping.keys(), key=lambda item: -len(item))
        )
    )
    return regex.sub(lambda match: mapping[match.group()], text)


def escape_latex(text):
    conv = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\^{}",
        "\\": r"\textbackslash{}",
        "<": r"\textless{}",
        ">": r"\textgreater{}",
    }
    return escape(conv, text)


def replace_status(text):
    text = re.sub(' \(Running on .*\)', '', text)
    text = re.sub('.*TIMEOUT.*', 'TIMEOUT', text)

    conv = {
        "OUT OF MEMORY": r"\OOM",
        "FALSE(valid-ltl)": r"\NOK",
        "TIMEOUT": r"\TOUT",
        "UNKNOWN: OverapproxCex": r"\UNK",
        "false(unreach-call)": r"\NOK",
        "ERROR: TYPE ERROR": "\FAIL",
        "ERROR: EXCEPTION": "\FAIL",
        "unknown": r"\UNK",
        "true": r"\OK",
        "false(termination)": r"\NOK",
        "clang failed": r"\FAIL",
        "kittel failed": r"\FAIL",
        "llvm2kittel failed": r"\FAIL",
        "ERROR (parsing failed)": r"\FAIL",
        "MAYBE": r"\UNK",
        "EXCEPTION": r"\FAIL",
    }
    return escape(conv, text)


def replace_tool_name(text):
    conv = {
        "ULTIMATE Automizer_0.2.1-178dd20e": r"\Tool",
        "ULTIMATE Automizer_0.2.1-4aafbbc3": r"\ultimate",
        "ULTIMATE Automizer_0.2.1-90ca62f3": r"\ultimate",
        "ULTIMATE Automizer_0.2.1-8176aa38": r"\Tool",
        "/storage/repos/bitwise-ltl/cexamples/benchmarking/run_aprove.sh_": r"\aprove",
        "/storage/repos/bitwise-ltl/cexamples/benchmarking/run_kittel.sh_":r"\kittel",
        "ULTIMATE Automizer_0.2.1-67e0c2b1": r"\Tool",
        "ULTIMATE Automizer_0.2.1-89f38710": r"\ultimate",
        "ULTIMATE Automizer_0.2.1-13a2652b": r"\Tool",
        "ULTIMATE Automizer_0.2.1-f2afa94d": r"\Tool",
        "ULTIMATE Automizer_0.2.1-e5ca92de": r"\ultimate",
        "ULTIMATE Automizer_0.2.1-3a54f2e7": r"\Tool",
        "ULTIMATE Automizer_0.2.1-b4afca67": r"\ultimate",
        "CPAchecker_2.0.1-svn" : r"\cpachecker",
        "2LS_0.9.1":r"\twols",
    }
    return escape(conv, text)

def replace_category_name(text):
    conv = {
        "Term.term-mcsema-lift": r"Term. McSema",
        "Term.term-simplify-lift": r"Term. Simplify",
        "Term.term-source-cyrules": r"Term. CyRules",
        "LTL.ltl-mcsema-lift":r"LTL McSema",
        "LTL.ltl-simplify-lift-sbe":r"LTL Simplify",
        "LTL.ltl-simplify-lift":r"LTL Simplify",
        "LTL.ltl-bithacks":r"LTL Bithacks",
        "LTL.ltl-cyrules":r"LTL CyRules",
        "Term.term-source-aprove":r"Term. Aprove",
        
        "Reach Integer cvc4.reach-simple":r"INT \cvc",
        "Reach Integer itp mathsat.reach-simple":r"INT \mathsat itp",
        "Reach Integer mathsat.reach-simple":r"INT \mathsat",
        "Reach Integer.reach-simple":r"INT \smtinterpol+\zzz",
        "Reach Integer z3.reach-simple":r"INT \zzz",
        
        "Reach BV cvc4.reach-simple":r"BV \cvc",
        "Reach BV itp mathsat.reach-simple":r"BV \mathsat itp",
        "Reach BV mathsat.reach-simple":r"BV \mathsat",
        "Reach BV princess.reach-simple":r"BV \princess",
        "Reach BV.reach-simple":r"BV Wolf",
        "Reach BV z3.reach-simple":r"BV \zzz",
        
        "Reach Integer cvc4.reach-bithacks":r"INT \cvc",
        "Reach Integer itp mathsat.reach-bithacks":r"INT \mathsat itp",
        "Reach Integer mathsat.reach-bithacks":r"INT \mathsat",
        "Reach Integer.reach-bithacks":r"INT \smtinterpol+\zzz",
        "Reach Integer z3.reach-bithacks":r"INT \zzz",
        
        "Reach BV cvc4.reach-bithacks":r"BV \cvc",
        "Reach BV itp mathsat.reach-bithacks":r"BV \mathsat itp",
        "Reach BV mathsat.reach-bithacks":r"BV \mathsat",
        "Reach BV princess.reach-bithacks":r"BV \princess",
        "Reach BV.reach-bithacks":r"BV Wolf",
        "Reach BV z3.reach-bithacks":r"BV \zzz",
    }
    return escape(conv, text)

def get_tool_name(results):
    return f'{util.prettylist(results.attributes.get("tool"))}_{util.prettylist(results.attributes.get("version"))}'


def header(t):
    return f"\\header{{{t}}}"

def rheader(t):
    return f"\\rheader{{{t}}}"

def columns(run):
    cols = {}
    for i, c in enumerate(run.columns):
        try:
            cols[c.title] = util.to_decimal(run.values[i])
        except InvalidOperation:
            cols[c.title] = run.values[i]
    return cols


def categorize(key_fun, l):
    bins = {}
    for e in l:
        k = key_fun(e)
        if k in bins:
            bins[k].append(e)
        else:
            bins[k] = [e]
    return bins


def load_results(result_file):
    run_set_result = tablegenerator.RunSetResult.create_from_xml(
        result_file, tablegenerator.parse_results_file(result_file)
    )
    run_set_result.collect_data(False)
    return run_set_result


def main(args=None):
    if args is None:
        args = sys.argv

    parser = argparse.ArgumentParser(
        fromfile_prefix_chars="@",
        description="""Dump LaTeX commands with summary values of the table.
           All the information from the footer of HTML tables is available.
           The output is written to stdout.""",
    )

    parser.add_argument(
        "result",
        metavar="RESULT",
        type=str,
        nargs="+",
        help="XML file(s) with result produced by benchexec",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        nargs=1,
        help="File path to which tables and figures should be written",
    )

    options = parser.parse_args(args[1:])

    pool = multiprocessing.Pool()
    run_set_results = pool.map(partial(load_results), options.result)

    by_blocks = categorize(
        lambda x: replace_category_name(util.prettylist(x.attributes.get("name"))), run_set_results
    )
    print_overview(by_blocks)
    print_overview_2(by_blocks)
    print_details(by_blocks)


def print_details(by_blocks):
    for b, b_results in by_blocks.items():
        by_tools = categorize(lambda x: replace_tool_name(get_tool_name(x)), b_results,)
        by_tools = OrderedDict(sorted(by_tools.items()))

        prefix = os.path.commonprefix(
            [r.task_id.name for r_set in b_results for r in r_set.results]
        )
        print()
        # print("\\begin{table}")
        # print(f"\\caption{{{b}}}")
        print(b)
        fields = f"lll{'rc' * len(by_tools)}"
        print(f"\\begin{{tabular}}{{{fields}}}")
        print("\\toprule")
        tool_mc = [f"\\multicolumn{{2}}{{c}}{{{t}}}" for t in by_tools.keys()]
        sep = " & "
        print(f"Benchmark & Property & Expected & {sep.join(tool_mc)} \\\\")
        print(f" &  & {' & Time & Result' * len(by_tools)} \\\\")
        cmid_rules = "".join(
            [f"\\cmidrule(lr){{{i}-{i + 1}}}" for i in range(4, len(fields), 2)]
        )
        print(cmid_rules)

        benchmarks = [
            escape_latex(str(r.task_id.name[len(prefix) :]))
            for r in next(iter(by_tools.values()))[0].results
        ]
        results = []
        for t, t_results in by_tools.items():
            t_result = []
            for result in t_results:
                for r in result.results:
                    t_result += [
                        (f"{columns(r)['cputime']:.2f}s", replace_status(r.status))
                    ]
            results += [t_result]

        for idx, b in enumerate(benchmarks):
            t_results = [f"{t} & {s}" for t, s in [i[idx] for i in results]]
            print(f"{b} & & & {sep.join(t_results)} \\\\")
        
        print("\\bottomrule")
        print("\\end{tabular}")
        # print("\\end{table}")


def get_cmid_rules(f_select,no_columns,length):
    return [f"\\cmidrule{{{i}-{i + length}}}" for i in range(no_columns) if f_select(i)]


def print_overview_2(by_blocks):
    """
    With times, merge Rundef+Tool (i.e., assume that this is a 1-to-1 relation)

    by_blocks: str(Rundef) -> List[RunSetResult]
    """
    headers = []
    rows = {}
    
    # rows: filename -> [(status,cputime)]
    for b, b_results in by_blocks.items():
        by_tools = categorize(lambda x: replace_tool_name(get_tool_name(x)), b_results,)
        by_tools = OrderedDict(sorted(by_tools.items()))
        # by_tools: str(Tool) -> List[RunSetResult]
        for t, t_results in by_tools.items():
            headers +=[f"{t} {b}"]
            for r_result in t_results:
                # result.results: List[RunResults]
                for r in r_result.results:
                    cputime=columns(r)['cputime']
                    rows[r.task_id] = rows.get(r.task_id,[]) + [(replace_status(r.status), cputime)]

    sum_cputime = []
    no_times = len(next(iter(rows.values())))
    for i in range(no_times):
        sum_cputime += [sum( [ k[i][1] for t,k in rows.items() ] )]

    
    # print(f"{r.task_id} {r.status} {columns(r)['cputime']:.2f}s")

    # column definitions
    no_columns = no_times + 1
    print(no_columns)
    str_columns = ["cr@{\\hspace{1em}}" for i in range(0,no_columns)]
    print(f"\\begin{{tabular}}{{l{''.join(str_columns)}}}")
    print("\\toprule")
    
    # print column headers
    blocks = [header(k) for k in headers]
    category_tex = "\n & ".join([f"\\multicolumn{{2}}{{c}}{{{d}}}" for d in blocks])
    print(f" & {category_tex} \\\\")
    print("\\midrule")

    # rows 
    for f, vals in rows.items():
        v = " & ".join(f"{s} & {t:.2f}s" for s,t in vals)
        print(f"{escape_latex(f.name)} & {v} \\\\")
    print("\\midrule")
    
    v = " & & ".join(f"{t:.2f}s" for t in sum_cputime)
    print(f'Sum & & {v} \\\\')
    print("\\bottomrule")
    print("\\end{tabular}")
    print("")

def print_overview(by_blocks):
    counter = {}
    for b, b_results in by_blocks.items():
        by_tools = categorize(lambda x: replace_tool_name(get_tool_name(x)), b_results,)
        by_tools = OrderedDict(sorted(by_tools.items()))
        print(f"Block {b}")
        block_counter = {}
        for t, t_results in by_tools.items():
            print(t)
            by_status = Counter()
            for result in t_results:
                by_status += Counter(
                    {
                        c: len(l)
                        for c, l in categorize(
                            lambda x: replace_status(x.status), result.results
                        ).items()
                    }
                )
            block_counter[t+b] = by_status
        counter[b] = block_counter

    
    # column definitions
    no_columns = sum([len(v) for v in counter.values()])
    is_spacing_column = lambda x : (x % len(by_tools) == len(by_tools) - 1) and x != no_columns - 1 
    columns = ["cc@{\\hspace{1em}}" if is_spacing_column(i) else "c" for i in range(0,no_columns)]
    
    # 1 categories, 1 total count, 1 spacing, then dynamic
    print(f"\\begin{{tabular}}{{l{''.join(columns)}}}")
    print("\\toprule")
    
    # print categories (eg, sets of benchmarks)
    blocks = [header(k) for k in counter.keys()]
    category_tex = "\n & & ".join([f"\\multicolumn{{{len(by_tools)}}}{{c}}{{{d}}}" for d in blocks])
    print(f" & {category_tex} \\\\")
    
    # prepare cmid rules 
    start_rule = lambda x : x % len(by_tools) == 2
    cmid_rules = "".join(get_cmid_rules(start_rule,no_columns,len(by_tools)))
    print(cmid_rules)
    
    # print tool names
    sep = "\n & "
    tool_header = [f"{sep}{rheader(k)}" for v in counter.values() for k in v]
    tool_header = [l + " & " * is_spacing_column(n) for n, l in enumerate(tool_header)]
    print(f"{''.join(tool_header)} \\\\")
    print(cmid_rules)

    # rows 
    categories = sorted({v for t in counter.values() for c in t.values() for v in c})
    for c in categories:
        row_values = [f" & {str(v[c])}" if c in v else ' & -' for t in counter.values() for v in t.values()]
        row_values = [l + (" & " * is_spacing_column(n)) for n, l in enumerate(row_values)]
        print(
            f"{c} {''.join(row_values)}\\\\"
        )
    print("\\bottomrule")
    print("\\end{tabular}")
    print("")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit("Script was interrupted by user.")
