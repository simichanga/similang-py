from __future__ import annotations
from typing import Tuple, Optional, List
from llvmlite import ir

from frontend import ast as A
from middle.types import TypeSystem
from util.env import Environment


class ExpressionLowerer:
    """
    Lowers expressions to LLVM IR values. Single source of truth for conversions.
    Returns tuples: (ir.Value, type_name_str) where type_name_str is one of 'int','float','bool','str'.
    """

    def __init__(self, builder: ir.IRBuilder, module: ir.Module, types: TypeSystem, env: Environment):
        self.builder = builder
        self.module = module
        self.types = types
        self.env = env

    # ---- API ----
    def lower(self, node: A.Expression) -> Tuple[ir.Value, str]:
        meth = getattr(self, f"_lower_{node.type().name.lower()}", None)
        if meth is None:
            raise NotImplementedError(f"Expression lowering not implemented for {node.type().name}")
        return meth(node)

    # ---- literals & identifiers ----
    def _lower_integerliteral(self, node: A.IntegerLiteral) -> Tuple[ir.Constant, str]:
        val = int(node.value)
        irt = self.types.get_ir_type('int')
        return ir.Constant(irt, val), 'int'

    def _lower_floatliteral(self, node: A.FloatLiteral) -> Tuple[ir.Constant, str]:
        val = float(node.value)
        irt = self.types.get_ir_type('float')
        return ir.Constant(irt, val), 'float'

    def _lower_stringliteral(self, node: A.StringLiteral) -> Tuple[ir.Value, str]:
        s = node.value or ""
        # create a global constant array of i8 with trailing null
        data = bytearray((s + '\0').encode('utf8'))
        arr_type = ir.ArrayType(ir.IntType(8), len(data))
        const_arr = ir.Constant(arr_type, data)
        name = f"__str_const_{abs(hash(s)) & 0xffffffff}"
        gv = ir.GlobalVariable(self.module, arr_type, name=name)
        gv.linkage = 'internal'
        gv.global_constant = True
        gv.initializer = const_arr
        # bitcast to i8*
        i8ptr = self.types.get_ir_type('str')
        ptr = self.builder.bitcast(gv, i8ptr)
        return ptr, 'str'

    def _lower_booleanliteral(self, node: A.BooleanLiteral) -> Tuple[ir.Constant, str]:
        v = 1 if node.value else 0
        irt = self.types.get_ir_type('bool')
        return ir.Constant(irt, v), 'bool'

    def _lower_identifierliteral(self, node: A.IdentifierLiteral) -> Tuple[ir.Value, str]:
        ptr, type_name = self.env.lookup(node.value)
        if '[' in type_name:
            # Arrays: return pointer directly, do not load
            return ptr, type_name
        else:
            val = self.builder.load(ptr)
            return val, type_name

    # ---- calls ----
    def _lower_callexpression(self, node: A.CallExpression) -> Tuple[ir.Value, str]:
        if not isinstance(node.function, A.IdentifierLiteral):
            raise NotImplementedError("Only identifier call expressions implemented")
        fname = node.function.value
        # lower args
        args_vals: List[ir.Value] = []
        args_types: List[str] = []
        for arg in node.arguments:
            v, t = self.lower(arg)
            args_vals.append(v)
            args_types.append(t)

        # builtin printf special-case: expects format string + varargs
        if fname == 'printf':
            printf_fn = self.module.get_global('printf') or None
            if printf_fn is None:
                raise RuntimeError("printf not declared in module")
            # assume first arg is format string pointer or global pointer
            fmt_arg = args_vals[0]
            call_args = [fmt_arg]
            for v, t in zip(args_vals[1:], args_types[1:]):
                if t == 'float':
                    # promote float (f32) to double for printf compatibility
                    v = self.builder.fpext(v, ir.DoubleType())
                elif t == 'bool':
                    # zext i1 to i32
                    v = self.builder.zext(v, ir.IntType(32))
                elif t == 'int':
                    # ensure int is i32
                    if v.type.width != 32:
                        v = self.builder.sext(v, ir.IntType(32))
                call_args.append(v)
            ret = self.builder.call(printf_fn, call_args)
            return ret, 'int'

        # user function
        func_sym = self.env.lookup(fname)
        func_ptr, ret_type_name = func_sym
        # function value is stored as function object (not pointer) in env; call expects function
        # ensure types conversions for args (int->float etc.)
        call_args = []
        for v, t, expected in zip(args_vals, args_types, getattr(func_ptr, 'arg_types', [t for t in args_types])):
            # if expected is None, try pass as is
            if expected is None or expected == t:
                call_args.append(v)
            else:
                # allow int->float and float->int (backend will convert)
                if expected == 'float' and t == 'int':
                    call_args.append(self.builder.sitofp(v, ir.FloatType()))
                elif expected == 'int' and t == 'float':
                    call_args.append(self.builder.fptosi(v, ir.IntType(32)))
                else:
                    call_args.append(v)
        result = self.builder.call(func_ptr, call_args)
        return result, ret_type_name or 'int'

    def _as_i32(self, v: ir.Value, tname: str) -> ir.Value:
        """Coerce an index value to i32 for GEP."""
        i32 = ir.IntType(32)
        if tname == 'int':
            return v if isinstance(v.type, ir.IntType) and v.type.width == 32 else self.builder.sext(v, i32)
        if tname == 'bool':
            return self.builder.zext(v, i32)
        if tname == 'float':
            return self.builder.fptosi(v, i32)
        # default: try bitcast/extend if it's already an int of another width
        if isinstance(v.type, ir.IntType):
            return v if v.type.width == 32 else self.builder.sext(v, i32)
        raise RuntimeError("Array index must be int/bool/float (coercible to i32)")

    def _lower_indexexpression(self, node: A.IndexExpression) -> Tuple[ir.Value, str]:
        array_val, array_type_name = self.lower(node.left)
        elem_ir_type = self.types.get_element_type(array_type_name.split('[')[0])
        index_val, _ = self.lower(node.index)

        if not isinstance(array_val.type, ir.PointerType):
            raise RuntimeError("Indexing requires a pointer to an array, got value instead.")

        elem_ptr = self.builder.gep(array_val, [
            ir.Constant(self.types.get_ir_type('int'), 0),
            index_val
        ])

        elem_val = self.builder.load(elem_ptr)
        return elem_val, array_type_name.split('[')[0]

    # ---- postfix (++, --) ----
    def _lower_postfixexpression(self, node: A.PostfixExpression) -> Tuple[ir.Value, str]:
        left = node.left_node
        if not isinstance(left, A.IdentifierLiteral):
            raise RuntimeError("Postfix operator must be applied to identifier")
        sym_ptr, tname = self.env.lookup(left.value)
        orig_val = self.builder.load(sym_ptr)
        if tname == 'int':
            one = ir.Constant(self.types.get_ir_type('int'), 1)
            new = self.builder.add(orig_val, one) if node.operator == '++' else self.builder.sub(orig_val, one)
            self.builder.store(new, sym_ptr)
            return new, 'int'
        elif tname == 'float':
            one = ir.Constant(self.types.get_ir_type('float'), 1.0)
            new = self.builder.fadd(orig_val, one) if node.operator == '++' else self.builder.fsub(orig_val, one)
            self.builder.store(new, sym_ptr)
            return new, 'float'
        else:
            raise RuntimeError("Postfix ++/-- on non-numeric type")

    # ---- prefix (-, !) ----
    def _lower_prefixexpression(self, node: A.PrefixExpression) -> Tuple[ir.Value, str]:
        val, t = self.lower(node.right_node)
        if node.operator == '-':
            if t == 'int':
                neg = self.builder.mul(val, ir.Constant(self.types.get_ir_type('int'), -1))
                return neg, 'int'
            elif t == 'float':
                neg = self.builder.fmul(val, ir.Constant(self.types.get_ir_type('float'), -1.0))
                return neg, 'float'
            else:
                raise RuntimeError("Unary - applied to non-numeric")
        if node.operator == '!':
            # expect bool
            if t != 'bool':
                raise RuntimeError("Unary ! applied to non-bool")
            # bitwise not for i1: xor with 1
            res = self.builder.xor(val, ir.Constant(self.types.get_ir_type('bool'), 1))
            return res, 'bool'
        raise RuntimeError(f"Unknown prefix operator {node.operator}")

    # ---- infix (binary) ----
    def _lower_infixexpression(self, node: A.InfixExpression) -> Tuple[ir.Value, str]:
        left_val, left_t = self.lower(node.left_node)
        right_val, right_t = self.lower(node.right_node)

        # Determine result type using language rules
        res_type = self.types.binary_result_type(left_t, right_t, node.operator)
        if res_type is None:
            raise RuntimeError(f"Type error: cannot apply {node.operator} to {left_t} and {right_t}")

        # Coerce operands for numeric ops
        if res_type == 'int':
            # ensure both i32
            if left_t == 'float':
                left_val = self.builder.fptosi(left_val, ir.IntType(32))
            if right_t == 'float':
                right_val = self.builder.fptosi(right_val, ir.IntType(32))
            # integer arithmetic / comparisons
            match node.operator:
                case '+': return self.builder.add(left_val, right_val), 'int'
                case '-': return self.builder.sub(left_val, right_val), 'int'
                case '*': return self.builder.mul(left_val, right_val), 'int'
                case '/': return self.builder.sdiv(left_val, right_val), 'int'
                case '%': return self.builder.srem(left_val, right_val), 'int'
                case '<' | '<=' | '>' | '>=' | '==' | '!=':
                    cmp = self.builder.icmp_signed(node.operator, left_val, right_val)
                    return cmp, 'bool'
                case _: raise RuntimeError(f"Unsupported integer operator {node.operator}")
        elif res_type == 'float':
            # ensure both float
            if left_t == 'int':
                left_val = self.builder.sitofp(left_val, ir.FloatType())
            if right_t == 'int':
                right_val = self.builder.sitofp(right_val, ir.FloatType())
            match node.operator:
                case '+': return self.builder.fadd(left_val, right_val), 'float'
                case '-': return self.builder.fsub(left_val, right_val), 'float'
                case '*': return self.builder.fmul(left_val, right_val), 'float'
                case '/': return self.builder.fdiv(left_val, right_val), 'float'
                case '%': return self.builder.frem(left_val, right_val), 'float'
                case '<' | '<=' | '>' | '>=' | '==' | '!=':
                    cmp = self.builder.fcmp_ordered(node.operator, left_val, right_val)
                    return cmp, 'bool'
                case _: raise RuntimeError(f"Unsupported float operator {node.operator}")
        elif res_type == 'bool':
            # comparisons for ints/floats or equality on other same-type values
            if (left_t in ('int', 'float')) and (right_t in ('int', 'float')):
                if left_t != right_t:
                    # coerce int->float if needed
                    if left_t == 'int':
                        left_val = self.builder.sitofp(left_val, ir.FloatType())
                        left_t = 'float'
                    if right_t == 'int':
                        right_val = self.builder.sitofp(right_val, ir.FloatType())
                        right_t = 'float'
                # use float compare if floats
                if left_t == 'float':
                    cmp = self.builder.fcmp_ordered(node.operator, left_val, right_val)
                    return cmp, 'bool'
                else:
                    cmp = self.builder.icmp_signed(node.operator, left_val, right_val)
                    return cmp, 'bool'
            # equality on strings not implemented
            raise RuntimeError("Boolean operator on non-comparable types or unsupported equality for strings")
        else:
            raise RuntimeError(f"Unsupported result type {res_type}")
