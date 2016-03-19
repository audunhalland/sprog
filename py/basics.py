
import comp
import cons
import cons_util
import debug
import function
import parse
import source

import code
import operator as op
import sys

def define_basics(env):
    def display(c):
        if isinstance(c, cons.String):
            sys.stdout.write(c.string)
        else:
            sys.stdout.write(c.sexpr())

    def call_void(func, *args):
        func(*args)
        return cons.Void()

    def define_py(name, func, pure=True):
        env.glob_const[name] = function.Generic(name, func, pure)

    def define_py_pred(name, func):
        env.glob_const[name] = function.Generic(name, lambda *a: cons.from_py(func(*a)), pure=True)

    define_py     ('car', lambda x: x.car)
    define_py     ('cdr', lambda x: x.cdr)
    define_py     ('cons', lambda x, y: cons.Pair(x, y))
    define_py     ('display', lambda x: call_void(display, x), pure=False)
    define_py_pred('eq?', lambda x, y: x is y)
    define_py_pred('equal?', lambda x, y: x.equal(y))
    define_py     ('list', lambda *args: cons.from_py(args))
    define_py     ('newline', lambda: cons.String('\n'))
    define_py     ('not', lambda x: cons.from_py(cons.is_false(x)))
    define_py_pred('null?', lambda x: isinstance(x, cons.Null))
    define_py_pred('pair?', lambda x: isinstance(x, cons.Pair))
    define_py_pred('number?', lambda x: isinstance(x, cons.Number))
    define_py     ('python', lambda: call_void(lambda: code.interact(local=locals())))
    define_py_pred('string?', lambda x: isinstance(x, cons.String))
    define_py_pred('symbol?', lambda x: isinstance(x, cons.Symbol))

    env.glob_const['apply'] = function.Apply()

    env.glob_const['+'] = function.PyOp(op.add)
    env.glob_const['-'] = function.PyOp(op.sub)
    env.glob_const['*'] = function.PyOp(op.mul)
    env.glob_const['/'] = function.PyOp(op.truediv)
    env.glob_const['<'] = function.PyOp(op.lt)
    env.glob_const['<='] = function.PyOp(op.le)
    env.glob_const['>'] = function.PyOp(op.gt)
    env.glob_const['>='] = function.PyOp(op.ge)

def define_loops(env):
    'define things like map and for-each'
    dbg = debug.stream_tree()

    def eval_fn(source):
        return env.eval(comp.compile_expr(parse.parse_one(source), env))

    primitive_builtins = [x for x in cons_util.traverse_list(
        eval_fn(source.String('loops.basics',
"""((lambda ()
  (define (all-car l)
    (if (null? l)
        ()
        (cons (car (car l)) (all-car (cdr l)))))
  (define (all-cdr l)
    (if (null? l)
        ()
        (cons (cdr (car l)) (all-cdr (cdr l)))))
  (define (all-null? l)
    (if (null? l)
        true
        (if (null? (car l))
            (all-null? (cdr l))
            false)))
  (define (map fn lsts)
    (if (all-null? lsts)
        ()
        (cons (apply fn (all-car lsts)) (map fn (all-cdr lsts)))))
  (define (for-each fn lsts)
    (if (not (all-null? lsts))
        (begin
          (apply fn (all-car lsts))
          (for-each fn (all-cdr lsts)))))
  (list
    (lambda (fn . lsts) (map fn lsts))
    (lambda (fn . lsts) (for-each fn lsts)))))
        """)))]

    env.glob_const['map'] = primitive_builtins[0]
    env.glob_const['for-each'] = primitive_builtins[1]
