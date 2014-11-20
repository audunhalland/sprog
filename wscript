#!/usr/bin/env python

import sys

def options(ctx):
    ctx.load('compiler_cxx')

def configure(ctx):
    ctx.load('compiler_cxx')

    if sys.platform == 'darwin':
        ctx.env.INCLUDES_llvm = ['/usr/local/opt/llvm/include']

def build(ctx):
    ctx.program(source = 'src/sprogc.cpp',
                target = 'sprogc',
                use = 'llvm')
