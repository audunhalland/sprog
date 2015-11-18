
from __future__ import print_function

import cons

import sys

def printstuff(*what):
    #raise Error('hei') # Find out who prints
    def tostring(w):
        if hasattr(w, 'sexpr'):
            return cons.debug_str(w)
        else:
            return str(w)
    print(''.join([tostring(w) for w in what]), file=sys.stderr)

"""
def d(*what):
    printstuff(*['DEBUG '] + [w for w in what])

def e(*what):
    printstuff(*['ERROR '] + [w for w in what])
"""

def point_to_tag(tag):
    return tag[0].line_str + ('~' * (tag[1] - 1)) + '^' if tag else ''

def describe_tag(tag):
    return ':'.join([tag[0].sourcefile.name, str(tag[0].row), str(tag[1])]) if tag else ''

class Stream:
    def __init__(self, name):
        self.name = name
        self.enabled = False

    def d(self, *what):
        if self.enabled:
            printstuff(*['D ' + self.name + ' '] + [w for w in what])

    def e(self, *what):
        if self.enabled:
            printstuff(*['E ' + self.name + ' '] + [w for w in what])

class Printer:
    def __init__(self):
        self.streams = {}

    def __call__(self, name):
        s = self.streams.get(name, None)
        if not s:
            s = Stream(name)
            self.streams[name] = s
        return s

    def enable(self, *names):
        for n in names:
            self(n).enabled = True

class StreamTree:
    def __init__(self, name, parent):
        self.name = name
        self.parent = parent
        self.enabled = False

    def format_name(self):
        names = []
        p = self
        while p:
            if not p.parent:
                break
            names.append(p.name)
            p = p.parent
        if len(names) == 0:
            return ''
        else:
            return '[' + '.'.join(names) + ']'

    def d(self, *what):
        if self.enabled:
            printstuff(*['D' + self.format_name() + ' '] + [w for w in what])

    def e(self, *what):
        if self.enabled:
            printstuff(*['E' + self.format_name() + ' '] + [w for w in what])

    def dump(self, what):
        if self.enabled:
            Dumper(self).run(what)

    def set_enabled(self, enabled):
        self.enabled = enabled
        for c in dir(self):
            if isinstance(c, StreamTree):
                c.set_enabled(enabled)

    def add(self, name):
        child = StreamTree(name, self)
        setattr(self, name, child)
        return child

def stream_tree():
    r = StreamTree('', None)
    r.add('comp')
    r.comp.add('value_defines')
    r.comp.add('stamp_resolver')
    r.add('eval')
    return r

class Dumper:
    """
    Dumper for object trees - for objects implementing the hvtree() method.
    The hvtree() method must return a two sized tuple - containing 'horizontal' and 'vertical' member. Horizontal children should include the object itself
    """

    tag_tab_space = 120

    def __init__(self, dbg, max_depth=None):
        self.reg = {}
        self.dbg = dbg
        self.max_depth = max_depth

    def any_seen(self, lst):
        for obj in lst:
            if id(obj) in self.reg:
                return True
        return False

    def run(self, what, level=0, tag=None):
        def dumpstr(obj):
            s = ''
            if id(obj) in self.reg:
                s += '[SEEN]'
            s += str(obj)
            return s
        if self.max_depth and level == self.max_depth:
            return

        if not what:
            self.dbg.d(' '*(level*4), 'None')
            return
        indent = level*4
        objs, children = what.hvtree()
        main_obj = objs[0]
        other_objs = objs[1:]
        label = dumpstr(main_obj)
        if len(other_objs) > 0:
            label += '(' + ', '.join([dumpstr(x) for x in other_objs]) + ')'
        if tag:
            label += (' ' * (Dumper.tag_tab_space - len(label) - indent)) + '{' + describe_tag(tag) + '}'
        self.dbg.d(' '*indent, label)
        if not self.any_seen(objs):
            for obj in objs:
                self.reg[id(obj)] = None

            if hasattr(children, 'tags'):
                for child, tag in zip(children, children.tags):
                    self.run(child, level+1, tag)
            else:
                for child in children:
                    self.run(child, level+1)
