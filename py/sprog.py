#! /usr/bin/env python3

import basics
import comp
import cons
import cons_util
import debug
import eval
import error
import parse
import source

import argparse
import readline
import sys
import traceback
import unittest

desc = 'Scheme programming.'

ap = argparse.ArgumentParser(prog='sprog',
                             description=desc)
ap.add_argument('files', nargs='*', default=[])
ap.add_argument('--verbose_compile', help='run with verbose compiler', action='store_true')
ap.add_argument('--verbose_eval', help='run with verbose evaluator', action='store_true')

args = ap.parse_args()

env = eval.Env(debug.stream_tree())

basics.define_basics(env)
basics.define_loops(env)

env.dbg.comp.set_enabled(args.verbose_compile)
env.dbg.eval.set_enabled(args.verbose_eval)

def eval_iterator(i):
    try:
        for ins in comp.compile_iterator(i, env, debuggable=True):
            env.eval(ins)
    finally:
        i.close()

def read_eval_print(track_name):
    print(
        env.eval(
            comp.compile_expr(
                parse.parse_one(source.String(track_name, input('sprog> ') + '\n')),
                env, debuggable=True)).sexpr())

def read_eval_print_loop():
    i = 0
    while True:
        i += 1
        try:
            read_eval_print('REPL#' + str(i))
        except parse.NoValueError:
            continue
        except parse.SingleLineError:
            continue
        except KeyboardInterrupt as e:
            print('')
            return
        except error.Error as e:
            print(e)
        except BaseException as e:
            traceback.print_exc()

readline.parse_and_bind('tab: complete')

if len(args.files):
    for fn in args.files:
        eval_iterator(iter(source.File(fn)))
else:
    read_eval_print_loop()
