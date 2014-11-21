#!/usr/bin/env python

import sys

def options(ctx):
    ctx.load('compiler_cxx')

def configure(ctx):
    ctx.load('compiler_cxx')

    if sys.platform == 'darwin':
        ctx.env.INCLUDES_llvm = ['/usr/local/opt/llvm/include']
        ctx.env.DEFINES_llvm = ['__STDC_LIMIT_MACROS=1',
                                '__STDC_CONSTANT_MACROS=1']

def build(ctx):
    ctx.program(source = 'src/sprogc.cpp',
                target = 'sprogc',
                use = 'llvm')
