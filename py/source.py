
import comp
import debug
import eval
import parse

import io

class Line:
    def __init__(self, sourcefile, line_str, row):
        self.sourcefile = sourcefile
        self.line_str = line_str
        self.row = row

class CharIterator:
    def __init__(self, source, f):
        self.name = source.name
        self.f = f
        self.line_str = None
        self.row = 0
        self.column = 0
        self.line_obj = None

    def __iter__(self):
        return self

    def __next__(self):
        if not self.line_str:
            self.nextline()
        else:
            self.column += 1
            if self.column == len(self.line_str):
                self.nextline()
        return self.line_str[self.column]

    def nextline(self):
        if self.line_str:
            self.row += 1
        self.line_str = self.f.readline()
        if len(self.line_str) == 0:
            raise StopIteration
        self.column = 0
        self.line_obj = None

    def get_tag(self):
        if not self.line_obj:
            self.line_obj = Line(self, self.line_str, self.row + 1)
        return (self.line_obj, self.column + 1)

    def close(self):
        self.f.close()

class File:
    def __init__(self, name):
        self.name = name

    def __iter__(self):
        return CharIterator(self, open(self.name))

class String:
    def __init__(self, name, s):
        self.name = name
        self.s = s

    def __iter__(self):
        return CharIterator(self, io.StringIO(self.s))
