#! /usr/bin/env python3

import basics
import comp
import cons
import debug
import error
import eval
import parse
import source

import io
import sys
import unittest

dbg = debug.stream_tree()
#dbg.comp.set_enabled(True)

class test_parse(unittest.TestCase):
    def parse(self, src):
        return parse.parse_one(iter(source.String(self.id(), src)))

    def assertParseEqual(self, src, c):
        value = self.parse(src)
        self.assertEqual(value.__class__, c.__class__)
        self.assertEqual(value.sexpr(), c.sexpr())

    def test_null(self):
        self.assertParseEqual('()', cons.Null())

    def test_list_one(self):
        self.assertParseEqual('(1)', cons.lst(cons.Number(1)))

    def test_list_simple(self):
        self.assertParseEqual('(1 2)', cons.lst(cons.Number(1), cons.Number(2)))

    def test_list_recurse(self):
        self.assertParseEqual('(1 (2) 3)', cons.lst(cons.Number(1),
                                                    cons.lst(cons.Number(2)),
                                                    cons.Number(3)))
        self.assertParseEqual('((1))', cons.lst(cons.lst(cons.Number(1))))
        self.assertParseEqual('(1 (2 ()) 3)', cons.lst(cons.Number(1),
                                                       cons.lst(cons.Number(2),
                                                                cons.Null()),
                                                       cons.Number(3)))

    def test_list_dot(self):
        self.assertParseEqual('(1 . 2)', cons.Pair(cons.Number(1), cons.Number(2)))

    def test_list_ws(self):
        self.assertParseEqual('(1 )', cons.lst(cons.Number(1)))
        self.assertParseEqual('( 1)', cons.lst(cons.Number(1)))
        self.assertParseEqual('( 1 )', cons.lst(cons.Number(1)))
        self.assertParseEqual('( 1 . 2 )', cons.Pair(cons.Number(1), cons.Number(2)))

    def test_literal(self):
        self.assertParseEqual('hello', cons.Symbol('hello'))
        self.assertParseEqual('"hello"', cons.String('hello'))
        self.assertParseEqual('2', cons.Number(2))

    def test_error(self):
        self.assertRaises(parse.NoValueError, self.parse, '')
        self.assertRaises(parse.NoValueError, self.parse, '#| comment |#')
        self.assertRaises(parse.EOFError, self.parse, '(list')
        self.assertRaises(parse.EOFError, self.parse, '#| comment')
        self.assertRaises(parse.EOFError, self.parse, '"string')

    def test_number(self):
        self.assertParseEqual('-2', cons.Number(-2))
        self.assertParseEqual('-0', cons.Number(0))
        self.assertParseEqual('0.1', cons.Number(0.1))
        self.assertParseEqual('-0.1', cons.Number(-0.1))

    def test_string(self):
        self.assertParseEqual('"hei"', cons.String('hei'))
        self.assertParseEqual('"and\\nor"', cons.String('and\nor'))
        self.assertRaises(error.Error, self.parse, '"\escape"')

class test_eval(unittest.TestCase):
    def eval_iterator(self, i, stdout_capture=None, with_basics=True, with_loops=False):
        env = eval.Env(dbg)
        if with_basics:
            basics.define_basics(env)
        if with_loops:
            basics.define_loops(env)
        result = None
        stdout = sys.stdout
        ins = comp.compile_module(i, env, debuggable=True)
        if stdout_capture:
            sys.stdout = stdout_capture

        result = env.eval_noexcept(ins)

        if stdout_capture:
            sys.stdout = stdout
        return result

    def eval_src(self, src, **kw):
        return self.eval_iterator(iter(source.String(self.id(), src)), **kw)

    def assertDisplayEqual(self, source, display, **kw):
        output = io.StringIO()
        result = self.eval_src(source, stdout_capture=output, **kw)
        self.assertEqual(output.getvalue(), display)

    def assertValueEqual(self, source, value, **kw):
        result = self.eval_src(source, **kw)
        return result.equal(value)

    def test_map1(self):
        self.assertDisplayEqual("(display (map + '(1 2) '(1 2) '(1 2)))",
                                '(3 6)', with_loops=True)
    def test_map2(self):
        self.assertDisplayEqual("(display (map car '((1) (2))))",
                                '(1 2)', with_loops=True)

    def test_closure1(self):
        self.assertDisplayEqual("""
        (define (test x) (lambda () x))
        (define testa (test "A"))
        (display (testa))""",
                                'A')

    def test_closure2(self):
        self.assertDisplayEqual("""
        (define (test x)
          (lambda (y)
            (lambda ()
              (list x y))))
        (display (((test 1) 2)))""",
                                '(1 2)')

    def test_and1(self):
        self.assertDisplayEqual("(display (and true))", "true")

    def test_and2(self):
        self.assertDisplayEqual("(display (and false true))", "false")

    def test_and3(self):
        self.assertDisplayEqual("""
        (define v false)
        (define (alternate) (set! v (not v)) v)
        (display (and (alternate) 1))
        (display (and (alternate) 1))
        (display (and (alternate) (alternate)))
        (display (and (alternate) (alternate)))""",
                                '1falsefalsefalse')

    def test_or1(self):
        self.assertDisplayEqual("(display (or true))", "true")

    def test_or2(self):
        self.assertDisplayEqual("(display (or false true))", "true")

    def test_or3(self):
        self.assertDisplayEqual("""
        (define v false)
        (define (alternate) (set! v (not v)) v)
        (display (or (alternate) 1))
        (display (or (alternate) 1))""",
                                "true1")

    def test_begin1(self):
        self.assertDisplayEqual('(begin (display 1) (display 2))', '12')

    def test_begin2(self):
        self.assertDisplayEqual("""
        (define (test pos-f neg-f lst)
          (if (pair? lst)
            (begin
              ((if (< (car lst) 0) neg-f pos-f) (car lst))
              (test pos-f neg-f (cdr lst)))))
        (test
          (lambda (x) (display "p"))
          (lambda (x) (display "n"))
          (list -2 -1 0 1 2))""",
                                'nnppp')

    def test_begin_block1(self):
        """Contains begins that cannot exist at the same time because of if,
        so memory location can be shared"""
        self.assertDisplayEqual("""
        (define (test op later x)
          (if (> x 0)
            (begin
              (define xx (op x))
              (later (lambda (x)
                (display x)
                (display xx))))
            (begin
              (define xxx (op (op x)))
              (later (lambda (x)
                (display x)
                (display xxx))))))
        (define (double x) (* x 2))
        (define (later fn) (fn 42))
        (test double later -2)
        (test double later 2)""",
                                '42-8424')

    def test_begin_block2(self):
        """Contains sequential begins, that cannot share memory location"""
        self.assertDisplayEqual("""
        (define (test fn-collector)
           (define var 5)
           (begin
             (define v2 (* var 2))
             (fn-collector (lambda () v2)))
           (begin
             (define v3 (* var 3))
             (fn-collector (lambda () v3))))
        (define fn-lst ())
        (test (lambda (fn)
          ; reverse ordered
          (set! fn-lst (cons fn fn-lst))))
        (for-each (lambda (fn) (display (fn)) (display " ")) fn-lst)""",
                                '15 10 ', with_loops=True)

    def test_begin_block3(self):
        """Test that temporary locals are reused (how to test?? function should have 2 locals.)"""
        self.assertDisplayEqual("""
        ((lambda (x)
          (define v (+ x 3))
          (display v)
          (begin
            (define v2 (+ x 4))
            (display v2))) 1)""",
                                 '45')

    def test_undefined1(self):
        with self.assertRaises(error.Error):
            self.eval_src('foo')

    def test_undefined2(self):
        with self.assertRaises(error.Error):
            self.eval_src('((lambda (a) (+ a b)) 1)')

    def test_misplaced_define1(self):
        with self.assertRaises(error.Error):
            self.eval_src('((lambda (a) (+ a 1)) (define a 3))')

    def test_pure_rec(self):
        self.assertDisplayEqual("""
        (define (traverse c)
          (if (pair? c)
              (traverse-pair c)
              (if (not (null? c))
                  (display c))))
        (define (traverse-pair c)
          (traverse-car c)
          (traverse-cdr c))
        (define (traverse-car c)
          (traverse (car c)))
        (define (traverse-cdr c)
          (traverse (cdr c)))
        (traverse (list 1 (list 2 3)))""",
                                '123')

    def test_function_void(self):
        self.assertValueEqual('((lambda ()))', cons.Void())

    def test_function_error1(self):
        with self.assertRaises(error.Error):
            self.eval_src('((lambda (a . b)))')

if __name__ == '__main__':
    unittest.main()
