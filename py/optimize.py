
import comp
import debug
import instr

class PurityGraph:
    def __init__(self, env):
        self.env = env
        self.object_index_alloc = 0
        self.object_index = 0
        self.reg = {}

    def reg_pure(self, func):
        pass
    def push_func(self, func):
        pass

    def draw(self, what):
        h, v = what.hvtree()
        for obj in h:
            if isinstance(obj, instr.Function):
                if obj.purity_level == instr.PURITY_LEVEL_PURE:
                    self.reg_pure(obj)
                elif obj.purity_level == instr.PURITY_LEVEL_SHALLOW_ENV:
                    self.push_func(obj)
                    for child in v:
                        self.draw(child)
                    self.pop_func(obj)
                else:
                    # Can stop searching....
                    self.reg_nonpure()

class PurityOptimizer:
    """
    Optimize individual function defines that are potentially pure.
    Purity can be a recursive definition.
    """

    def __init__(self, env, verbose=False):
        self.env = env

    def run(self, ins):
        graph = PurityGraph(self.env)
        graph.graph(ins)

class CallOptimizer:
    def __init__(self, env, verbose=False):
        self.env = env
        self.verbose = verbose
        self.pure_const_calls = []
        self.reg = {}

    def optimize_call(self, ins, index):
        start_index = index
        # skip PushArgs
        index += 1
        last = index
        const_args = []
        while index < len(ins):
            i = ins[index]
            if isinstance(i, instr.Arg) or isinstance(i, instr.ArgPrepend):
                if isinstance(const_args, list):
                    if index - last == 1:
                        constant = comp.get_load_literal(ins[last])
                        if constant:
                            const_args.append(constant)
                        else:
                            const_args = None
                    else:
                        const_args = None
                index += 1
                last = index
            elif isinstance(i, instr.Call):
                if const_args and index - last == 1:
                    constant = comp.get_load_literal(ins[last])
                    if constant and constant.is_pure():
                        value = self.env.eval(ins[start_index:index+1])
                        ins[start_index:index+1] = [instr.Load(instr.LiteralLocation(value))]
                        self.pure_const_calls.append((constant, const_args))
                        return start_index + 1
                return index + 1
            else:
                index = self.optimize_one(ins, index)
        raise error.Error("call not ended")

    def optimize_one(self, ins, index):
        if isinstance(ins[index], instr.PushArgs):
            return self.optimize_call(ins, index)

        for sub_ins in ins[index].get_ins():
            if id(sub_ins) in self.reg:
                continue
            self.reg[id(sub_ins)] = None
            self.optimize_ins(sub_ins, 0)
        return index + 1

    def optimize_ins(self, ins, index):
        if not ins:
            return 0

        index = 0
        while index < len(ins):
            index = self.optimize_one(ins, index)
        return ins

    def run(self, ins):
        ins = self.optimize_ins(ins, 0)
        if self.verbose:
            for opt in self.pure_const_calls:
                debug.d('optimized', opt)
        return ins
